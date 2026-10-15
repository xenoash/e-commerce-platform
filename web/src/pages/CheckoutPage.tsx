import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { ApiProblem, unwrap, type Order } from "../api/client";
import { useCart, useCartMutations, usePaymentMethods } from "../api/hooks";
import { AddressForm } from "../components/AddressForm";
import { TotalsTable } from "../components/CartPanel";
import { Button, Card, Money, ProblemNotice } from "../components/ui";
import { keepKeyAfter, newIdempotencyKey } from "../lib/idempotency";
import { displayLineAmount } from "../lib/labels";
import { useSession } from "../lib/session-context";

const TEST_TOKENS = [
  { token: "tok_success", label: "Approved" },
  { token: "tok_3ds", label: "Asks for 3-D Secure" },
  { token: "tok_decline", label: "Declined" },
  { token: "tok_insufficient_funds", label: "Insufficient funds" },
  { token: "tok_timeout", label: "Gateway times out (settled later)" },
];

const DEMO_SHIPPING = {
  name: "Sara Al-Harbi",
  phone: "+966512345678",
  email: "sara@example.com",
  street: "Tahlia Street",
  building_number: "2468",
  district: "Al Olaya",
  city: "Riyadh",
  postal_code: "12241",
};

const DEMO_BUSINESS_CONTACT = {
  ...DEMO_SHIPPING,
  name: "Khalid Al-Otaibi",
  phone: "+966555555555",
  email: "procurement@acme.example.com",
  street: "Olaya Street",
  building_number: "7788",
  district: "Al Wurud",
  postal_code: "12251",
};

const DEMO_BILLING = {
  ...DEMO_BUSINESS_CONTACT,
  company_name: "Acme Arabia Trading Co.",
  vat_number: "310175397400003",
  cr_number: "1010123456",
};

const MISSING_LABELS: Record<string, string> = {
  items: "Add at least one item",
  shipping_address: "Add a shipping address",
  payment_method: "Choose a payment method",
  billing_address: "Add billing details with a VAT number",
  available_items: "Fix unavailable items in your cart",
  applicable_coupon: "Remove the coupon that no longer applies",
};

export function CheckoutPage() {
  const { session, api, rememberOrder } = useSession();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const cart = useCart().data;
  const methods = usePaymentMethods().data ?? [];
  const { setShipping, setBilling, setPaymentMethod } = useCartMutations();
  const [token, setToken] = useState("tok_success");
  const [poNumber, setPoNumber] = useState("");
  const keyRef = useRef<string | null>(null);

  const placeOrder = useMutation({
    mutationFn: async () => {
      keyRef.current ??= newIdempotencyKey();
      const method = methods.find((item) => item.method === cart!.payment_method?.method);
      return unwrap(
        api.POST("/api/v1/carts/{cart_id}/checkout", {
          params: { path: { cart_id: cart!.id }, header: { "Idempotency-Key": keyRef.current } },
          body: {
            payment_token: method?.requires_token ? token : null,
            expected_total: cart!.totals.total,
            po_number: poNumber,
          },
        }),
      );
    },
    onSuccess: (order: Order) => {
      rememberOrder(order.id);
      queryClient.invalidateQueries({ queryKey: ["cart", session.store] });
      const redirect = order.payment?.next_action?.url;
      if (redirect) window.location.assign(redirect);
      else navigate(`/${session.store}/orders/${order.id}`);
    },
    onError: (error) => {
      if (!keepKeyAfter(error)) keyRef.current = null;
      if (error instanceof ApiProblem && error.code === "CART_TOTAL_CHANGED") {
        queryClient.invalidateQueries({ queryKey: ["cart", session.store] });
      }
    },
  });

  if (!cart || cart.items.length === 0) {
    return (
      <Card>
        <p className="text-sm text-muted">Your cart is empty.</p>
        <Link to={`/${session.store}`} className="mt-3 inline-block text-sm font-semibold text-accent">
          Back to the shop
        </Link>
      </Card>
    );
  }

  const needsBilling = cart.invoice_kind === "standard" || session.customerKind === "business";
  const selected = methods.find((item) => item.method === cart.payment_method?.method);
  const readiness = cart.checkout_readiness;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <div className="space-y-6">
        <Link to={`/${session.store}`} className="text-sm text-muted hover:text-ink">
          Back to the shop
        </Link>
        <Card>
          <AddressForm
            title="Shipping address"
            initial={cart.shipping_address ?? (session.customerKind === "business" ? DEMO_BUSINESS_CONTACT : DEMO_SHIPPING)}
            saved={Boolean(cart.shipping_address)}
            busy={setShipping.isPending}
            error={setShipping.error}
            onSubmit={(address) => setShipping.mutate({ cartId: cart.id, address })}
          />
        </Card>
        {needsBilling ? (
          <Card>
            <AddressForm
              title="Billing details"
              business
              initial={cart.billing_address ?? DEMO_BILLING}
              saved={Boolean(cart.billing_address)}
              busy={setBilling.isPending}
              error={setBilling.error}
              onSubmit={(address) => setBilling.mutate({ cartId: cart.id, address })}
            />
            <p className="mt-3 text-xs text-muted">
              A VAT number makes this a standard tax invoice. ZATCA clears it before it is shared with you.
            </p>
          </Card>
        ) : null}
        <Card className="space-y-3">
          <h2 className="text-lg font-bold">Payment</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            {methods.map((method) => (
              <label
                key={method.method}
                className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm ${
                  cart.payment_method?.method === method.method ? "border-accent bg-accent/8" : "border-line"
                }`}
              >
                <input
                  type="radio"
                  name="payment-method"
                  checked={cart.payment_method?.method === method.method}
                  onChange={() => setPaymentMethod.mutate({ cartId: cart.id, method: method.method })}
                />
                {method.display_name}
              </label>
            ))}
          </div>
          <ProblemNotice error={setPaymentMethod.error} />
          {selected?.requires_token ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-muted">Sandbox card outcome</span>
              <select
                value={token}
                onChange={(event) => setToken(event.target.value)}
                className="w-full rounded-lg border border-line bg-paper px-3 py-2"
              >
                {TEST_TOKENS.map((option) => (
                  <option key={option.token} value={option.token}>
                    {option.label} ({option.token})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {needsBilling ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-muted">Purchase order number (optional)</span>
              <input
                value={poNumber}
                onChange={(event) => setPoNumber(event.target.value)}
                className="w-full rounded-lg border border-line bg-paper px-3 py-2"
              />
            </label>
          ) : null}
        </Card>
      </div>
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <Card className="space-y-4">
          <h2 className="text-lg font-bold">Order summary</h2>
          <ul className="space-y-1 text-sm">
            {cart.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-2">
                <span className="truncate">
                  {item.quantity} × {item.product.name}
                </span>
                <Money amount={displayLineAmount(item, cart.totals.prices_include_vat)} currency={cart.currency} />
              </li>
            ))}
          </ul>
          <TotalsTable totals={cart.totals} currency={cart.currency} />
          {!readiness.ready ? (
            <ul className="space-y-1 rounded-lg bg-warn/10 p-3 text-xs text-warn">
              {readiness.missing.map((item) => (
                <li key={item}>{MISSING_LABELS[item] ?? item}</li>
              ))}
            </ul>
          ) : null}
          <ProblemNotice error={placeOrder.error} />
          <Button className="w-full py-3" disabled={!readiness.ready} busy={placeOrder.isPending} onClick={() => placeOrder.mutate()}>
            Place order · <Money amount={cart.totals.total} currency={cart.currency} />
          </Button>
          <p className="text-center text-xs text-muted">
            Retries reuse the same Idempotency-Key, so you are never charged twice.
          </p>
        </Card>
      </aside>
    </div>
  );
}

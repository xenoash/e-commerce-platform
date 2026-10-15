import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router";

import { ApiProblem, unwrap, type Order } from "../api/client";
import { useCart, useCartMutations, usePaymentMethods } from "../api/hooks";
import { AddressForm } from "../components/AddressForm";
import { TotalsTable } from "../components/CartPanel";
import { Button, Card, Money, ProblemNotice } from "../components/ui";
import { keepKeyAfter, newIdempotencyKey } from "../lib/idempotency";
import { useI18n } from "../i18n/context";
import { displayLineAmount, methodLabel, productName } from "../lib/labels";
import { useSession } from "../lib/session-context";

const TEST_TOKENS = ["tok_success", "tok_3ds", "tok_decline", "tok_insufficient_funds", "tok_timeout"] as const;

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
  const i18n = useI18n();
  const { t, has, lang } = i18n;

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
        <p className="text-sm text-muted">{t("checkout.empty")}</p>
        <Link to={`/${session.store}`} className="mt-3 inline-block text-sm font-semibold text-accent">
          {t("checkout.back")}
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
          {t("checkout.back")}
        </Link>
        <Card>
          <AddressForm
            title={t("checkout.shipping")}
            submitLabel={t("checkout.saveShipping")}
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
              title={t("checkout.billing")}
              submitLabel={t("checkout.saveBilling")}
              business
              initial={cart.billing_address ?? DEMO_BILLING}
              saved={Boolean(cart.billing_address)}
              busy={setBilling.isPending}
              error={setBilling.error}
              onSubmit={(address) => setBilling.mutate({ cartId: cart.id, address })}
            />
            <p className="mt-3 text-xs text-muted">{t("checkout.billingNote")}</p>
          </Card>
        ) : null}
        <Card className="space-y-3">
          <h2 className="text-lg font-bold">{t("checkout.payment")}</h2>
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
                {methodLabel(i18n, method.method, method.display_name)}
              </label>
            ))}
          </div>
          <ProblemNotice error={setPaymentMethod.error} />
          {selected?.requires_token ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-muted">{t("checkout.sandboxOutcome")}</span>
              <select
                value={token}
                onChange={(event) => setToken(event.target.value)}
                className="w-full rounded-lg border border-line bg-paper px-3 py-2"
              >
                {TEST_TOKENS.map((option) => (
                  <option key={option} value={option}>
                    {t(`token.${option}`)} ({option})
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {needsBilling ? (
            <label className="block text-sm">
              <span className="mb-1 block text-xs font-semibold text-muted">{t("checkout.poNumber")}</span>
              <input
                dir="ltr"
                value={poNumber}
                onChange={(event) => setPoNumber(event.target.value)}
                className="w-full rounded-lg border border-line bg-paper px-3 py-2 rtl:text-right"
              />
            </label>
          ) : null}
        </Card>
      </div>
      <aside className="lg:sticky lg:top-20 lg:self-start">
        <Card className="space-y-4">
          <h2 className="text-lg font-bold">{t("checkout.summary")}</h2>
          <ul className="space-y-1 text-sm">
            {cart.items.map((item) => (
              <li key={item.id} className="flex justify-between gap-2">
                <span className="truncate">
                  {item.quantity} × {productName(lang, item.product)}
                </span>
                <Money amount={displayLineAmount(item, cart.totals.prices_include_vat)} currency={cart.currency} />
              </li>
            ))}
          </ul>
          <TotalsTable totals={cart.totals} currency={cart.currency} />
          {!readiness.ready ? (
            <ul className="space-y-1 rounded-lg bg-warn/10 p-3 text-xs text-warn">
              {readiness.missing.map((item) => (
                <li key={item}>{has(`missing.${item}`) ? t(`missing.${item}` as const) : item}</li>
              ))}
            </ul>
          ) : null}
          <ProblemNotice error={placeOrder.error} />
          <Button className="w-full py-3" disabled={!readiness.ready} busy={placeOrder.isPending} onClick={() => placeOrder.mutate()}>
            {t("checkout.placeOrder")} · <Money amount={cart.totals.total} currency={cart.currency} />
          </Button>
          <p className="text-center text-xs text-muted">{t("checkout.retryNote")}</p>
        </Card>
      </aside>
    </div>
  );
}

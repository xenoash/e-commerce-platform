import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import type { Cart } from "../api/client";
import { useCartMutations, useSuggestions } from "../api/hooks";
import { displayLineAmount } from "../lib/labels";
import { useSession } from "../lib/session-context";
import { Suggestions } from "./Suggestions";
import { Badge, Button, Card, Money, ProblemNotice, ProductArt } from "./ui";

function Row({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex justify-between ${className}`}>
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function TotalsTable({ totals, currency }: { totals: Cart["totals"]; currency: string }) {
  return (
    <dl className="space-y-1.5 text-sm">
      <Row label="Subtotal">
        <Money amount={totals.subtotal} currency={currency} />
      </Row>
      {Number(totals.discount) > 0 ? (
        <Row label="Discount" className="text-ok">
          -<Money amount={totals.discount} currency={currency} />
        </Row>
      ) : null}
      <Row label="Shipping">{Number(totals.shipping) === 0 ? "Free" : <Money amount={totals.shipping} currency={currency} />}</Row>
      <Row label={`VAT ${Number(totals.vat_rate)}%${totals.prices_include_vat ? " (included)" : ""}`}>
        <Money amount={totals.vat} currency={currency} />
      </Row>
      <div className="flex justify-between border-t border-line pt-2 text-base font-bold">
        <dt>Total</dt>
        <dd>
          <Money amount={totals.total} currency={currency} />
        </dd>
      </div>
    </dl>
  );
}

function CouponForm({ cart }: { cart: Cart }) {
  const { applyCoupon, removeCoupon } = useCartMutations();
  const [code, setCode] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (code.trim()) applyCoupon.mutate({ cartId: cart.id, code: code.trim() }, { onSuccess: () => setCode("") });
  }

  if (cart.coupon) {
    return (
      <div className="rounded-lg border border-line p-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono font-semibold">{cart.coupon.code}</span>
          {cart.coupon.applicable ? <Badge tone="ok">applied</Badge> : <Badge tone="warn">not applicable</Badge>}
          <Button variant="danger" className="ml-auto" onClick={() => removeCoupon.mutate({ cartId: cart.id })}>
            Remove
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted">{cart.coupon.reason?.detail ?? cart.coupon.description}</p>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <input
          value={code}
          onChange={(event) => setCode(event.target.value.toUpperCase())}
          placeholder="Coupon code"
          aria-label="Coupon code"
          className="min-w-0 flex-1 rounded-lg border border-line bg-paper px-3 py-2 font-mono text-sm uppercase outline-none focus:border-accent"
        />
        <Button variant="quiet" type="submit" busy={applyCoupon.isPending}>
          Apply
        </Button>
      </div>
      <ProblemNotice error={applyCoupon.error} />
    </form>
  );
}

export function CartPanel({ cart }: { cart: Cart | null | undefined }) {
  const { session } = useSession();
  const { setQuantity, removeItem } = useCartMutations();
  const suggestions = useSuggestions(cart ?? undefined);
  const lineError = setQuantity.error ?? removeItem.error;

  if (!cart || cart.items.length === 0) {
    return (
      <Card>
        <h2 className="text-lg font-bold">Your cart</h2>
        <p className="mt-2 text-sm text-muted">Your cart is empty. Add something you like.</p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Your cart</h2>
        <span className="font-mono text-xs text-muted">v{cart.version}</span>
      </div>
      <ul className="divide-y divide-line">
        {cart.items.map((item) => (
          <li key={item.id} className="flex gap-3 py-3">
            <ProductArt sku={item.product.sku} name={item.product.name} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{item.product.name}</p>
              <p className="text-xs text-muted">
                <Money amount={item.unit_price} currency={cart.currency} /> each
                {!item.available ? <span className="ml-2 text-bad">unavailable</span> : null}
              </p>
              <div className="mt-1 flex items-center gap-2">
                <div className="flex items-center rounded-lg border border-line">
                  <button
                    aria-label={`Decrease ${item.product.name}`}
                    className="px-2 py-0.5 disabled:opacity-40"
                    disabled={item.quantity <= 1 || setQuantity.isPending}
                    onClick={() => setQuantity.mutate({ cartId: cart.id, itemId: item.id, quantity: item.quantity - 1 })}
                  >
                    −
                  </button>
                  <span className="w-7 text-center text-sm tabular">{item.quantity}</span>
                  <button
                    aria-label={`Increase ${item.product.name}`}
                    className="px-2 py-0.5 disabled:opacity-40"
                    disabled={setQuantity.isPending}
                    onClick={() => setQuantity.mutate({ cartId: cart.id, itemId: item.id, quantity: item.quantity + 1 })}
                  >
                    +
                  </button>
                </div>
                <Button variant="danger" onClick={() => removeItem.mutate({ cartId: cart.id, itemId: item.id })}>
                  Remove
                </Button>
              </div>
            </div>
            <div className="text-right text-sm">
              <Money
                amount={displayLineAmount(item, cart.totals.prices_include_vat)}
                currency={cart.currency}
                className="font-semibold"
              />
              {Number(item.discount) > 0 ? (
                <p className="text-xs text-ok">
                  -<Money amount={item.discount} currency={cart.currency} />
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
      <ProblemNotice error={lineError} />
      {cart.warnings.length ? (
        <ul className="space-y-1 rounded-lg bg-warn/10 p-3 text-xs text-warn">
          {cart.warnings.map((warning, index) => (
            <li key={`${warning.code}-${index}`}>{warning.detail}</li>
          ))}
        </ul>
      ) : null}
      <CouponForm cart={cart} />
      <Suggestions cart={cart} suggestions={suggestions.data?.suggestions ?? []} />
      <TotalsTable totals={cart.totals} currency={cart.currency} />
      <Link
        to={`/${session.store}/checkout`}
        className="block rounded-lg bg-accent px-4 py-3 text-center text-sm font-semibold text-accent-ink hover:opacity-90"
      >
        Checkout
      </Link>
    </Card>
  );
}

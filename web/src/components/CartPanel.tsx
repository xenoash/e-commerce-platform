import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";

import type { Cart } from "../api/client";
import { useCartMutations, useSuggestions } from "../api/hooks";
import { useI18n, type I18n } from "../i18n/context";
import { codeMessage } from "../i18n/problems";
import { displayLineAmount, productName } from "../lib/labels";
import { moneyText } from "../lib/money";
import { useSession } from "../lib/session-context";
import { Suggestions } from "./Suggestions";
import { Badge, Button, Card, Money, ProblemNotice, ProductArt } from "./ui";

function Row({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <div className={`flex justify-between gap-3 ${className}`}>
      <dt className="text-muted">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

export function TotalsTable({ totals, currency }: { totals: Cart["totals"]; currency: string }) {
  const { t } = useI18n();
  const rate = Number(totals.vat_rate);
  return (
    <dl className="space-y-1.5 text-sm">
      <Row label={t("totals.subtotal")}>
        <Money amount={totals.subtotal} currency={currency} />
      </Row>
      {Number(totals.discount) > 0 ? (
        <Row label={t("totals.discount")} className="text-ok">
          <Money amount={totals.discount} currency={currency} negative />
        </Row>
      ) : null}
      <Row label={t("totals.shipping")}>
        {Number(totals.shipping) === 0 ? t("totals.free") : <Money amount={totals.shipping} currency={currency} />}
      </Row>
      <Row label={t(totals.prices_include_vat ? "totals.vatIncluded" : "totals.vat", { rate })}>
        <Money amount={totals.vat} currency={currency} />
      </Row>
      <div className="flex justify-between gap-3 border-t border-line pt-2 text-base font-bold">
        <dt>{t("totals.total")}</dt>
        <dd>
          <Money amount={totals.total} currency={currency} />
        </dd>
      </div>
    </dl>
  );
}

function warningText(i18n: I18n, cart: Cart, warning: Cart["warnings"][number]) {
  const item = cart.items.find((candidate) => candidate.id === warning.item_id);
  const name = item ? productName(i18n.lang, item.product) : "";
  switch (warning.code) {
    case "PRICE_CHANGED":
      return i18n.t("warning.PRICE_CHANGED", { name, price: moneyText(warning.current_price ?? "0") });
    case "OUT_OF_STOCK":
      return i18n.tp("warning.OUT_OF_STOCK", warning.available ?? 0, { name });
    case "ITEM_UNAVAILABLE":
      return i18n.t("warning.ITEM_UNAVAILABLE", { name });
    case "COUPON_NOT_APPLICABLE":
      return i18n.t("warning.COUPON_NOT_APPLICABLE", {
        reason: codeMessage(i18n, warning.reason ?? "COUPON_NOT_APPLICABLE", cart.coupon?.reason?.data, warning.detail),
      });
    default:
      return warning.detail;
  }
}

function CouponForm({ cart }: { cart: Cart }) {
  const i18n = useI18n();
  const { t } = i18n;
  const { applyCoupon, removeCoupon } = useCartMutations();
  const [code, setCode] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    if (code.trim()) applyCoupon.mutate({ cartId: cart.id, code: code.trim() }, { onSuccess: () => setCode("") });
  }

  if (cart.coupon) {
    const reason = cart.coupon.reason;
    return (
      <div className="rounded-lg border border-line p-3 text-sm">
        <div className="flex items-center justify-between gap-2">
          <span dir="ltr" className="font-mono font-semibold">
            {cart.coupon.code}
          </span>
          {cart.coupon.applicable ? <Badge tone="ok">{t("cart.applied")}</Badge> : <Badge tone="warn">{t("cart.notApplicable")}</Badge>}
          <Button variant="danger" className="ms-auto" onClick={() => removeCoupon.mutate({ cartId: cart.id })}>
            {t("cart.remove")}
          </Button>
        </div>
        <p className="mt-1 text-xs text-muted">
          {reason ? codeMessage(i18n, reason.code, reason.data, reason.detail) : cart.coupon.description}
        </p>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <div className="flex gap-2">
        <input
          value={code}
          dir="ltr"
          onChange={(event) => setCode(event.target.value.toUpperCase())}
          placeholder={t("cart.couponPlaceholder")}
          aria-label={t("cart.couponPlaceholder")}
          className="min-w-0 flex-1 rounded-lg border border-line bg-paper px-3 py-2 font-mono text-sm uppercase outline-none placeholder:font-sans placeholder:normal-case focus:border-accent"
        />
        <Button variant="quiet" type="submit" busy={applyCoupon.isPending}>
          {t("cart.apply")}
        </Button>
      </div>
      <ProblemNotice error={applyCoupon.error} />
    </form>
  );
}

export function CartPanel({ cart }: { cart: Cart | null | undefined }) {
  const { session } = useSession();
  const i18n = useI18n();
  const { t, lang } = i18n;
  const { setQuantity, removeItem } = useCartMutations();
  const suggestions = useSuggestions(cart ?? undefined);
  const lineError = setQuantity.error ?? removeItem.error;

  if (!cart || cart.items.length === 0) {
    return (
      <Card>
        <h2 className="text-lg font-bold">{t("cart.title")}</h2>
        <p className="mt-2 text-sm text-muted">{t("cart.empty")}</p>
      </Card>
    );
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">{t("cart.title")}</h2>
        <span dir="ltr" className="font-mono text-xs text-muted">
          v{cart.version}
        </span>
      </div>
      <ul className="divide-y divide-line">
        {cart.items.map((item) => {
          const name = productName(lang, item.product);
          return (
            <li key={item.id} className="flex gap-3 py-3">
              <ProductArt sku={item.product.sku} name={item.product.name} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{name}</p>
                <p className="text-xs text-muted">
                  {t("cart.each", { price: moneyText(item.unit_price, cart.currency) })}
                  {!item.available ? <span className="ms-2 text-bad">{t("cart.unavailable")}</span> : null}
                </p>
                <div className="mt-1 flex items-center gap-2">
                  <div dir="ltr" className="flex items-center rounded-lg border border-line">
                    <button
                      aria-label={t("cart.decrease", { name })}
                      className="px-2 py-0.5 disabled:opacity-40"
                      disabled={item.quantity <= 1 || setQuantity.isPending}
                      onClick={() => setQuantity.mutate({ cartId: cart.id, itemId: item.id, quantity: item.quantity - 1 })}
                    >
                      −
                    </button>
                    <span className="w-7 text-center text-sm tabular">{item.quantity}</span>
                    <button
                      aria-label={t("cart.increase", { name })}
                      className="px-2 py-0.5 disabled:opacity-40"
                      disabled={setQuantity.isPending}
                      onClick={() => setQuantity.mutate({ cartId: cart.id, itemId: item.id, quantity: item.quantity + 1 })}
                    >
                      +
                    </button>
                  </div>
                  <Button variant="danger" onClick={() => removeItem.mutate({ cartId: cart.id, itemId: item.id })}>
                    {t("cart.remove")}
                  </Button>
                </div>
              </div>
              <div className="text-end text-sm">
                <Money
                  amount={displayLineAmount(item, cart.totals.prices_include_vat)}
                  currency={cart.currency}
                  className="font-semibold"
                />
                {Number(item.discount) > 0 ? (
                  <p className="text-xs text-ok">
                    <Money amount={item.discount} currency={cart.currency} negative />
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      <ProblemNotice error={lineError} />
      {cart.warnings.length ? (
        <ul className="space-y-1 rounded-lg bg-warn/10 p-3 text-xs text-warn">
          {cart.warnings.map((warning, index) => (
            <li key={`${warning.code}-${index}`}>{warningText(i18n, cart, warning)}</li>
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
        {t("cart.checkout")}
      </Link>
    </Card>
  );
}

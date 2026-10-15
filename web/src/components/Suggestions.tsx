import type { Cart, Suggestion } from "../api/client";
import { useCartMutations } from "../api/hooks";
import { useI18n, type I18n } from "../i18n/context";
import { productName } from "../lib/labels";
import { moneyText } from "../lib/money";
import { Button, Money, ProductArt } from "./ui";

function headline(i18n: I18n, suggestion: Suggestion) {
  if (i18n.lang === "en") return suggestion.headline;
  const key = `suggestion.${suggestion.reason_code}`;
  if (!i18n.has(key)) return suggestion.headline;
  const data = suggestion.data as Record<string, string>;
  return i18n.t(key, {
    remaining: data.remaining ? moneyText(data.remaining) : "",
    coupon: data.coupon_code ?? "",
  });
}

export function Suggestions({ cart, suggestions }: { cart: Cart; suggestions: Suggestion[] }) {
  const i18n = useI18n();
  const { addItem } = useCartMutations();
  if (!suggestions.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted">{i18n.t("cart.suggestions")}</p>
      {suggestions.map((suggestion, index) =>
        suggestion.product && suggestion.action ? (
          <div key={`${suggestion.strategy}-${suggestion.product.id}`} className="flex items-center gap-3 rounded-lg border border-line p-2">
            <ProductArt sku={suggestion.product.sku} name={suggestion.product.name} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{productName(i18n.lang, suggestion.product)}</p>
              <p className="text-xs text-muted">{headline(i18n, suggestion)}</p>
            </div>
            <div className="text-end">
              <Money amount={suggestion.product.price} currency={cart.currency} className="text-sm" />
              <Button
                variant="quiet"
                className="mt-1 px-2 py-1 text-xs"
                busy={addItem.isPending && addItem.variables?.productId === suggestion.action.product_id}
                onClick={() => addItem.mutate({ productId: suggestion.action!.product_id, quantity: suggestion.action!.quantity })}
              >
                {i18n.t("shop.add")}
              </Button>
            </div>
          </div>
        ) : (
          <p key={`${suggestion.strategy}-${index}`} className="rounded-lg bg-accent/10 px-3 py-2 text-sm text-accent">
            {headline(i18n, suggestion)}
          </p>
        ),
      )}
    </div>
  );
}

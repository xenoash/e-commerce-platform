import type { Cart, Suggestion } from "../api/client";
import { useCartMutations } from "../api/hooks";
import { Button, Money, ProductArt } from "./ui";

export function Suggestions({ cart, suggestions }: { cart: Cart; suggestions: Suggestion[] }) {
  const { addItem } = useCartMutations();
  if (!suggestions.length) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted">You might also like</p>
      {suggestions.map((suggestion, index) =>
        suggestion.product && suggestion.action ? (
          <div key={`${suggestion.strategy}-${suggestion.product.id}`} className="flex items-center gap-3 rounded-lg border border-line p-2">
            <ProductArt sku={suggestion.product.sku} name={suggestion.product.name} size="sm" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{suggestion.product.name}</p>
              <p className="text-xs text-muted">{suggestion.headline}</p>
            </div>
            <div className="text-right">
              <Money amount={suggestion.product.price} currency={cart.currency} className="text-sm" />
              <Button
                variant="quiet"
                className="mt-1 px-2 py-1 text-xs"
                busy={addItem.isPending && addItem.variables?.productId === suggestion.action.product_id}
                onClick={() => addItem.mutate({ productId: suggestion.action!.product_id, quantity: suggestion.action!.quantity })}
              >
                Add
              </Button>
            </div>
          </div>
        ) : (
          <p key={`${suggestion.strategy}-${index}`} className="rounded-lg bg-accent/10 px-3 py-2 text-sm text-accent">
            {suggestion.headline}
          </p>
        ),
      )}
    </div>
  );
}

import type { Product } from "../api/client";
import { useCart, useCartMutations, useProducts } from "../api/hooks";
import { CartPanel } from "../components/CartPanel";
import { Badge, Button, Money, ProblemNotice, ProductArt } from "../components/ui";
import { useI18n } from "../i18n/context";
import { productName } from "../lib/labels";

function StockLabel({ product }: { product: Product }) {
  const { t, tp } = useI18n();
  if (!product.in_stock) return <Badge tone="bad">{t("shop.soldOut")}</Badge>;
  if (product.stock_level !== null && product.stock_level <= 5) {
    return <Badge tone="warn">{tp("shop.onlyLeft", product.stock_level)}</Badge>;
  }
  if (product.kind === "service") return <Badge>{t("shop.service")}</Badge>;
  return null;
}

export function StorePage() {
  const products = useProducts();
  const cart = useCart();
  const { addItem } = useCartMutations();
  const { t, lang } = useI18n();

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section>
        <h1 className="mb-4 text-2xl font-bold tracking-tight">{t("shop.title")}</h1>
        <ProblemNotice error={products.error ?? addItem.error} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {products.data?.results.map((product) => (
            <article key={product.id} className="flex flex-col rounded-2xl border border-line bg-surface p-3">
              <ProductArt sku={product.sku} name={product.name} />
              <div className="mt-3 flex items-start justify-between gap-2">
                <h2 className="font-semibold leading-tight">{productName(lang, product)}</h2>
                <StockLabel product={product} />
              </div>
              <p dir="ltr" className="mt-1 font-mono text-xs text-muted rtl:text-right">
                {product.sku}
              </p>
              <div className="mt-auto flex items-center justify-between gap-3 pt-3">
                <Money amount={product.price} className="font-bold" />
                <Button
                  disabled={!product.in_stock}
                  busy={addItem.isPending && addItem.variables?.productId === product.id}
                  onClick={() => addItem.mutate({ productId: product.id })}
                >
                  {t("shop.add")}
                </Button>
              </div>
            </article>
          ))}
        </div>
      </section>
      <aside id="cart" className="lg:sticky lg:top-20 lg:self-start">
        <CartPanel cart={cart.data} />
      </aside>
    </div>
  );
}

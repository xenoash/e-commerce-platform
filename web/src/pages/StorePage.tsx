import type { Product } from "../api/client";
import { useCart, useCartMutations, useProducts } from "../api/hooks";
import { CartPanel } from "../components/CartPanel";
import { Badge, Button, Money, ProblemNotice, ProductArt } from "../components/ui";

function stockLabel(product: Product) {
  if (!product.in_stock) return <Badge tone="bad">Sold out</Badge>;
  if (product.stock_level !== null && product.stock_level <= 5) return <Badge tone="warn">Only {product.stock_level} left</Badge>;
  if (product.kind === "service") return <Badge>Service</Badge>;
  return null;
}

export function StorePage() {
  const products = useProducts();
  const cart = useCart();
  const { addItem } = useCartMutations();

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
      <section>
        <h1 className="mb-4 text-2xl font-bold tracking-tight">Shop</h1>
        <ProblemNotice error={products.error ?? addItem.error} />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {products.data?.results.map((product) => (
            <article key={product.id} className="flex flex-col rounded-2xl border border-line bg-surface p-3">
              <ProductArt sku={product.sku} name={product.name} />
              <div className="mt-3 flex items-start justify-between gap-2">
                <h2 className="font-semibold leading-tight">{product.name}</h2>
                {stockLabel(product)}
              </div>
              <p className="mt-1 font-mono text-xs text-muted">{product.sku}</p>
              <div className="mt-auto flex items-center justify-between gap-3 pt-3">
                <Money amount={product.price} className="font-bold" />
                <Button
                  disabled={!product.in_stock}
                  busy={addItem.isPending && addItem.variables?.productId === product.id}
                  onClick={() => addItem.mutate({ productId: product.id })}
                >
                  Add
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

import { Link } from "react-router";

import { ThemeToggle } from "../components/ThemeToggle";
import { Badge } from "../components/ui";
import { DEMO_STORES } from "../lib/stores";

const HIGHLIGHTS = [
  "Two tenants in one database, isolated by Postgres row-level security",
  "Coupons with constraints, upsell suggestions and live VAT totals",
  "Card payments with 3-D Secure, cash on delivery and B2B pay on invoice",
  "ZATCA-signed simplified and standard tax invoices with QR codes",
];

export function HomePage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold uppercase tracking-widest text-accent">E-commerce Platform</p>
        <ThemeToggle />
      </div>
      <h1 className="mt-2 text-4xl font-bold tracking-tight sm:text-5xl">One platform, many stores.</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted">
        Pick a store to shop as a guest or sign in with a demo account. Everything you see comes from the cart API.
      </p>
      <ul className="mt-6 grid gap-2 text-sm sm:grid-cols-2">
        {HIGHLIGHTS.map((item) => (
          <li key={item} className="flex gap-2">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-accent" />
            {item}
          </li>
        ))}
      </ul>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {DEMO_STORES.map((store) => (
          <Link
            key={store.handle}
            to={`/${store.handle}`}
            className="group rounded-2xl border border-line bg-surface p-6 transition hover:-translate-y-0.5 hover:shadow-lg"
          >
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">{store.name}</h2>
              <Badge tone="info">{store.audience}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted">{store.tagline}</p>
            <p className="mt-4 font-mono text-xs text-muted">X-Store: {store.handle}</p>
            <span className="mt-4 inline-block text-sm font-semibold text-accent group-hover:underline">Enter store</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

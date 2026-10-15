import { Link } from "react-router";

import { LanguageToggle } from "../components/LanguageToggle";
import { ThemeToggle } from "../components/ThemeToggle";
import { Badge } from "../components/ui";
import { useI18n } from "../i18n/context";
import { DEMO_STORES } from "../lib/stores";

const HIGHLIGHTS = [
  "home.highlight.tenancy",
  "home.highlight.cart",
  "home.highlight.payments",
  "home.highlight.zatca",
] as const;

export function HomePage() {
  const { t, lang } = useI18n();
  return (
    <div className="mx-auto max-w-4xl px-4 py-12">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="text-sm font-semibold uppercase tracking-widest text-accent">{t("app.name")}</p>
        <div className="flex gap-2">
          <LanguageToggle />
          <ThemeToggle />
        </div>
      </div>
      <h1 className="mt-2 text-4xl font-bold tracking-tight sm:text-5xl">{t("home.title")}</h1>
      <p className="mt-4 max-w-2xl text-lg text-muted">{t("home.lead")}</p>
      <ul className="mt-6 grid gap-2 text-sm sm:grid-cols-2">
        {HIGHLIGHTS.map((key) => (
          <li key={key} className="flex gap-2">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-accent" />
            {t(key)}
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
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-xl font-bold">{store.name[lang]}</h2>
              <Badge tone="info">{store.audience}</Badge>
            </div>
            <p className="mt-2 text-sm text-muted">{store.tagline[lang]}</p>
            <p dir="ltr" className="mt-4 font-mono text-xs text-muted rtl:text-right">
              X-Store: {store.handle}
            </p>
            <span className="mt-4 inline-block text-sm font-semibold text-accent group-hover:underline">{t("home.enter")}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

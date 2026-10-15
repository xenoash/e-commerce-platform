import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";

import { apiFor, unwrap } from "../api/client";
import { useCart, useStoreSettings } from "../api/hooks";
import { useI18n } from "../i18n/context";
import { useSession } from "../lib/session-context";
import { demoStore, type DemoAccount } from "../lib/stores";
import { LanguageToggle } from "./LanguageToggle";
import { ThemeToggle } from "./ThemeToggle";
import { Badge, Button, ProblemNotice } from "./ui";

export function Layout({ children }: { children: ReactNode }) {
  const { session, api, update, signOut } = useSession();
  const store = demoStore(session.store)!;
  const settings = useStoreSettings().data;
  const cart = useCart().data;
  const queryClient = useQueryClient();
  const [menuOpen, setMenuOpen] = useState(false);
  const { t, lang } = useI18n();

  const signIn = useMutation({
    mutationFn: async (account: DemoAccount) => {
      const signedIn = await unwrap(api.POST("/api/v1/auth/token", { body: { email: account.email, password: account.password } }));
      const cartApi = apiFor({ store: session.store, token: signedIn.token });
      const activeCart = await unwrap(cartApi.POST("/api/v1/carts"));
      return { signedIn, activeCart };
    },
    onSuccess: ({ signedIn, activeCart }) => {
      queryClient.removeQueries({ queryKey: ["cart", session.store] });
      update({
        token: signedIn.token,
        customerName: signedIn.customer.name,
        customerKind: signedIn.customer.kind,
        cartId: activeCart.id,
        cartToken: undefined,
      });
      setMenuOpen(false);
    },
  });

  const itemCount = cart?.items.reduce((sum, item) => sum + item.quantity, 0) ?? 0;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur print:hidden">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
          <Link to="/" className="text-sm text-muted hover:text-ink">
            {t("nav.allStores")}
          </Link>
          <Link to={`/${store.handle}`} className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight">{store.name[lang]}</span>
            <Badge tone="info">{store.audience}</Badge>
          </Link>
          {settings ? (
            <span className="hidden text-xs text-muted sm:inline">
              {t(settings.prices_include_vat ? "nav.pricesInclude" : "nav.pricesExclude", { rate: Number(settings.vat_rate) })}
            </span>
          ) : null}
          <div className="ms-auto flex flex-wrap items-center justify-end gap-3">
            <LanguageToggle />
            <ThemeToggle />
            {session.token ? (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-muted">
                  {t("nav.account")} <span className="font-semibold text-ink">{session.customerName}</span>
                </span>
                <Button variant="quiet" onClick={signOut}>
                  {t("nav.signOut")}
                </Button>
              </div>
            ) : (
              <div className="relative">
                <Button variant="quiet" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen}>
                  {t("nav.signIn")}
                </Button>
                {menuOpen ? (
                  <div className="absolute end-0 mt-2 w-72 rounded-xl border border-line bg-surface p-3 shadow-xl">
                    <p className="mb-2 text-xs text-muted">{t("nav.demoAccounts")}</p>
                    {store.accounts.map((account) => (
                      <Button
                        key={account.email}
                        variant="quiet"
                        className="mb-2 w-full justify-start"
                        busy={signIn.isPending}
                        onClick={() => signIn.mutate(account)}
                      >
                        {account.label[lang]}
                      </Button>
                    ))}
                    <ProblemNotice error={signIn.error} />
                  </div>
                ) : null}
              </div>
            )}
            <a href="#cart" className="relative rounded-lg border border-line bg-surface px-3 py-2 text-sm font-semibold">
              {t("nav.cart")}
              <span className="ms-2 rounded-full bg-accent px-2 py-0.5 text-xs text-accent-ink tabular">{itemCount}</span>
            </a>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 print:max-w-none print:p-0">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-10 text-xs text-muted print:hidden">
        {t("footer.note")}
      </footer>
    </div>
  );
}

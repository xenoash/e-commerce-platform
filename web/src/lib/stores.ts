export type DemoAccount = { email: string; password: string; label: string };

export type DemoStore = {
  handle: string;
  name: string;
  tagline: string;
  audience: "B2C" | "B2B";
  accounts: DemoAccount[];
};

export const DEMO_STORES: DemoStore[] = [
  {
    handle: "oud-and-amber",
    name: "Oud & Amber",
    tagline: "Perfume boutique. Prices include VAT, cards with 3-D Secure, cash on delivery.",
    audience: "B2C",
    accounts: [{ email: "sara@example.com", password: "demo-pass-123", label: "Sara (shopper)" }],
  },
  {
    handle: "riyadh-office-supply",
    name: "Riyadh Office Supply",
    tagline: "Office supplies for businesses. Prices exclude VAT, pay on invoice, standard tax invoices.",
    audience: "B2B",
    accounts: [{ email: "procurement@acme.example.com", password: "demo-pass-123", label: "Acme Arabia (business)" }],
  },
];

export function demoStore(handle: string | undefined) {
  return DEMO_STORES.find((store) => store.handle === handle);
}

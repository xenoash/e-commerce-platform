import type { Lang } from "../i18n/context";

type Localized = Record<Lang, string>;

export type DemoAccount = { email: string; password: string; label: Localized };

export type DemoStore = {
  handle: string;
  name: Localized;
  tagline: Localized;
  audience: "B2C" | "B2B";
  accounts: DemoAccount[];
};

export const DEMO_STORES: DemoStore[] = [
  {
    handle: "oud-and-amber",
    name: { en: "Oud & Amber", ar: "عود وعنبر" },
    tagline: {
      en: "Perfume boutique. Prices include VAT, cards with 3-D Secure, cash on delivery.",
      ar: "متجر عطور. الأسعار تشمل الضريبة، والدفع بالبطاقة مع التحقق ثلاثي الأبعاد أو عند الاستلام.",
    },
    audience: "B2C",
    accounts: [
      { email: "sara@example.com", password: "demo-pass-123", label: { en: "Sara (shopper)", ar: "سارة (حساب فردي)" } },
    ],
  },
  {
    handle: "riyadh-office-supply",
    name: { en: "Riyadh Office Supply", ar: "الرياض للمستلزمات المكتبية" },
    tagline: {
      en: "Office supplies for businesses. Prices exclude VAT, pay on invoice, standard tax invoices.",
      ar: "مستلزمات مكتبية للشركات. الأسعار لا تشمل الضريبة، مع الدفع الآجل بفاتورة وفواتير ضريبية قياسية.",
    },
    audience: "B2B",
    accounts: [
      {
        email: "procurement@acme.example.com",
        password: "demo-pass-123",
        label: { en: "Acme Arabia (business)", ar: "أكمي العربية (حساب شركة)" },
      },
    ],
  },
];

export function demoStore(handle: string | undefined) {
  return DEMO_STORES.find((store) => store.handle === handle);
}

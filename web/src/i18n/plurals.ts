import type { Lang } from "./context";

type Forms = Partial<Record<Intl.LDMLPluralRule, string>> & { other: string };

export const PLURALS = {
  "shop.onlyLeft": {
    en: { one: "Only {count} left", other: "Only {count} left" },
    ar: {
      zero: "نفد المخزون",
      one: "بقيت قطعة واحدة",
      two: "بقيت قطعتان",
      few: "بقيت {count} قطع",
      many: "بقيت {count} قطعة",
      other: "بقيت {count} قطعة",
    },
  },
  "warning.OUT_OF_STOCK": {
    en: { zero: "{name} is sold out.", one: "Only 1 {name} left.", other: "Only {count} of {name} left." },
    ar: {
      zero: "نفد مخزون {name}.",
      one: "بقيت قطعة واحدة فقط من {name}.",
      two: "بقيت قطعتان فقط من {name}.",
      few: "بقيت {count} قطع فقط من {name}.",
      many: "بقيت {count} قطعة فقط من {name}.",
      other: "بقيت {count} قطعة فقط من {name}.",
    },
  },
  "cart.itemCount": {
    en: { one: "{count} item", other: "{count} items" },
    ar: {
      zero: "لا توجد منتجات",
      one: "منتج واحد",
      two: "منتجان",
      few: "{count} منتجات",
      many: "{count} منتجاً",
      other: "{count} منتج",
    },
  },
} satisfies Record<string, Record<Lang, Forms>>;

export type PluralKey = keyof typeof PLURALS;

export function pluralForm(lang: Lang, key: PluralKey, count: number): string {
  const forms: Forms = PLURALS[key][lang];
  if (count === 0 && forms.zero) return forms.zero;
  const rule = new Intl.PluralRules(lang).select(count);
  return forms[rule] ?? forms.other;
}

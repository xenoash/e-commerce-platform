import { createContext, useContext } from "react";

import { ar } from "./ar";
import { en, type MessageKey } from "./en";
import { pluralForm, type PluralKey } from "./plurals";

export type Lang = "en" | "ar";
export type Vars = Record<string, string | number>;

export const LANG_STORAGE_KEY = "ecommerce-demo:lang";
const CATALOGUES = { en, ar };

export function fill(template: string, vars: Vars = {}) {
  return template.replace(/\{(\w+)\}/g, (match, name: string) => (name in vars ? String(vars[name]) : match));
}

export function translator(lang: Lang) {
  const catalogue = CATALOGUES[lang];
  const t = (key: MessageKey, vars?: Vars) => fill(catalogue[key], vars);
  const has = (key: string): key is MessageKey => key in catalogue;
  const tp = (key: PluralKey, count: number, vars?: Vars) => fill(pluralForm(lang, key, count), { count, ...vars });
  return { t, tp, has };
}

export function readLang(): Lang {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored === "en" || stored === "ar") return stored;
  } catch {
    return "en";
  }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("ar") ? "ar" : "en";
}

export function applyLang(lang: Lang) {
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch {
    return;
  }
}

export type I18n = ReturnType<typeof translator> & { lang: Lang; setLang: (lang: Lang) => void };

export const I18nContext = createContext<I18n | null>(null);

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}

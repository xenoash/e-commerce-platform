import type { I18n } from "../i18n/context";

const CARD_GATEWAYS = new Set(["fakepay", "tap"]);

export function methodLabel(i18n: Pick<I18n, "t" | "has" | "lang">, method: string, displayName?: string) {
  if (i18n.lang === "en" && displayName) return displayName;
  const key = `method.${method}`;
  return i18n.has(key) ? i18n.t(key) : (displayName ?? method);
}

export function paymentLabel(i18n: Pick<I18n, "t" | "has" | "lang">, method: string, gateway: string) {
  const label = methodLabel(i18n, method);
  return CARD_GATEWAYS.has(gateway) ? i18n.t("order.via", { method: label, gateway }) : label;
}

export function displayLineAmount(line: { net: string; total: string }, pricesIncludeVat: boolean) {
  return pricesIncludeVat ? line.total : line.net;
}

export function productName(lang: "en" | "ar", product: { name: string; name_ar?: string }) {
  return lang === "ar" && product.name_ar ? product.name_ar : product.name;
}

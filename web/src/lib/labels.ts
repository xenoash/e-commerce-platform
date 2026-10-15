const METHOD_LABELS: Record<string, string> = {
  card: "Card",
  apple_pay: "Apple Pay",
  cod: "Cash on delivery",
  net_terms: "Pay on invoice",
};

const CARD_GATEWAYS = new Set(["fakepay", "tap"]);

export function paymentLabel(method: string, gateway: string) {
  const label = METHOD_LABELS[method] ?? method;
  return CARD_GATEWAYS.has(gateway) ? `${label} via ${gateway}` : label;
}

export function displayLineAmount(line: { net: string; total: string }, pricesIncludeVat: boolean) {
  return pricesIncludeVat ? line.total : line.net;
}

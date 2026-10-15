const formatters = new Map<string, Intl.NumberFormat>();

export function formatMoney(amount: string | number, currency = "SAR") {
  let formatter = formatters.get(currency);
  if (!formatter) {
    formatter = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    formatters.set(currency, formatter);
  }
  return `${currency} ${formatter.format(Number(amount))}`;
}

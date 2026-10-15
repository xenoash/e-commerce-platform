import { formatMoney } from "./money";

describe("formatMoney", () => {
  it("formats decimal strings with two places and grouping", () => {
    expect(formatMoney("1234.5")).toBe("SAR 1,234.50");
    expect(formatMoney("0.10", "SAR")).toBe("SAR 0.10");
  });
});

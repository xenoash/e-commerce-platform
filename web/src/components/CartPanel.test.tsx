import { render, screen } from "@testing-library/react";

import type { Cart } from "../api/client";
import { TotalsTable } from "./CartPanel";

const totals: Cart["totals"] = {
  prices_include_vat: true,
  vat_rate: "15.00",
  subtotal: "545.00",
  discount: "50.00",
  shipping: "0.00",
  taxable_amount: "430.43",
  vat: "64.57",
  total: "495.00",
};

describe("TotalsTable", () => {
  it("shows the discount, free shipping and VAT included in the total", () => {
    render(<TotalsTable totals={totals} currency="SAR" />);
    expect(screen.getByText("Discount").nextSibling).toHaveTextContent("-SAR 50.00");
    expect(screen.getByText("Free")).toBeInTheDocument();
    expect(screen.getByText("VAT 15% (included)").nextSibling).toHaveTextContent("SAR 64.57");
    expect(screen.getByText("Total").nextSibling).toHaveTextContent("SAR 495.00");
  });

  it("hides the discount row when nothing is discounted", () => {
    render(<TotalsTable totals={{ ...totals, discount: "0.00", prices_include_vat: false }} currency="SAR" />);
    expect(screen.queryByText("Discount")).not.toBeInTheDocument();
    expect(screen.getByText("VAT 15%")).toBeInTheDocument();
  });
});

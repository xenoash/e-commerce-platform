import { ApiProblem } from "../api/client";
import { ar } from "./ar";
import { applyLang, translator } from "./context";
import { en } from "./en";
import { describeProblem } from "./problems";

const problem = (status: number, body: Record<string, unknown>) =>
  new ApiProblem(status, { type: "urn:test", title: "t", status, code: "X", ...body });

describe("catalogues", () => {
  it("translate every key into Arabic", () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort());
    expect(Object.values(ar).every((text) => text.trim().length > 0)).toBe(true);
  });

  it("keep Arabic copy free of em dashes and the borrowed word for demo", () => {
    const arabic = Object.values(ar).join("\n");
    expect(arabic).not.toMatch(/—/);
    expect(arabic).not.toMatch(/ديمو/);
  });
});

describe("Arabic plurals", () => {
  const { tp } = translator("ar");

  it.each([
    [1, "بقيت قطعة واحدة"],
    [2, "بقيت قطعتان"],
    [3, "بقيت 3 قطع"],
    [11, "بقيت 11 قطعة"],
    [100, "بقيت 100 قطعة"],
  ])("uses the right form for %i", (count, expected) => {
    expect(tp("shop.onlyLeft", count)).toBe(expected);
  });

  it("puts the tanween on an alef for 11 to 99", () => {
    expect(tp("cart.itemCount", 11)).toBe("11 منتجاً");
  });

  it("keeps English to singular and plural", () => {
    expect(translator("en").tp("cart.itemCount", 1)).toBe("1 item");
    expect(translator("en").tp("cart.itemCount", 3)).toBe("3 items");
  });
});

describe("problem translation", () => {
  it("translates by code and formats money from the problem's data", () => {
    const error = problem(422, { code: "COUPON_MIN_SUBTOTAL_NOT_MET", remaining: "305.00", detail: "Add 305.00 more" });
    expect(describeProblem(error, translator("ar")).message).toBe("تبقى \u2066SAR 305.00\u2069 لاستخدام هذه القسيمة.");
    expect(describeProblem(error, translator("en")).message).toBe("Add \u2066SAR 305.00\u2069 more to use this coupon.");
  });

  it("prefers the specific reason behind COUPON_NOT_APPLICABLE", () => {
    const error = problem(409, { code: "COUPON_NOT_APPLICABLE", reason: "COUPON_USAGE_LIMIT_REACHED" });
    expect(describeProblem(error, translator("ar")).message).toBe("استُنفدت مرات استخدام هذه القسيمة.");
  });

  it("labels field errors in the shopper's language", () => {
    const error = problem(400, {
      code: "VALIDATION_FAILED",
      errors: [{ field: "postal_code", code: "invalid_postal_code", message: "A postal code has 5 digits." }],
    });
    expect(describeProblem(error, translator("ar")).fields).toEqual(["الرمز البريدي: 5 أرقام"]);
  });

  it("falls back to the server detail for codes it does not know", () => {
    const error = problem(409, { code: "SOMETHING_NEW", detail: "A new rule." });
    expect(describeProblem(error, translator("ar")).message).toBe("A new rule.");
  });

  it("explains network failures", () => {
    expect(describeProblem(new TypeError("Failed to fetch"), translator("ar")).message).toBe("تعذر الاتصال بالخادم.");
  });
});

describe("document direction", () => {
  it("switches to right-to-left for Arabic and remembers it", () => {
    applyLang("ar");
    expect(document.documentElement.dir).toBe("rtl");
    expect(document.documentElement.lang).toBe("ar");
    applyLang("en");
    expect(document.documentElement.dir).toBe("ltr");
    expect(localStorage.getItem("ecommerce-demo:lang")).toBe("en");
  });
});

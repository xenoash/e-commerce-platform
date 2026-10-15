import { ApiProblem } from "../api/client";
import { keepKeyAfter, newIdempotencyKey } from "./idempotency";

const problem = (status: number, code: string) =>
  new ApiProblem(status, { type: "urn:test", title: "t", status, code });

describe("checkout idempotency keys", () => {
  it("are unique and long enough for the API", () => {
    const first = newIdempotencyKey();
    expect(first).not.toBe(newIdempotencyKey());
    expect(first.length).toBeGreaterThanOrEqual(8);
  });

  it("are kept when the outcome is unknown, so a retry cannot double charge", () => {
    expect(keepKeyAfter(new TypeError("Failed to fetch"))).toBe(true);
    expect(keepKeyAfter(problem(503, "TIMEOUT"))).toBe(true);
    expect(keepKeyAfter(problem(409, "REQUEST_IN_PROGRESS"))).toBe(true);
  });

  it("are replaced after a definitive rejection that created nothing", () => {
    expect(keepKeyAfter(problem(409, "CART_TOTAL_CHANGED"))).toBe(false);
    expect(keepKeyAfter(problem(422, "PAYMENT_TOKEN_REQUIRED"))).toBe(false);
  });
});

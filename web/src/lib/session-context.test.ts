import { orderAccessToken } from "./session-context";

describe("orderAccessToken", () => {
  it("keeps a guest's order readable after the cart token is gone", () => {
    const session = { store: "s", orderTokens: { "order-1": "ctk_old" } };
    expect(orderAccessToken(session, "order-1")).toBe("ctk_old");
  });

  it("falls back to the current cart token for orders it has not seen", () => {
    expect(orderAccessToken({ store: "s", cartToken: "ctk_now" }, "order-2")).toBe("ctk_now");
    expect(orderAccessToken({ store: "s" }, "order-2")).toBeUndefined();
  });
});

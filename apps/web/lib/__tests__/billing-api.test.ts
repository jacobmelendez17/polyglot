/** Billing client — request shapes + price formatting. */
import { billing, priceText } from "../billing-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("billing client", () => {
  it("reads entitlements", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ tier: "free_beta", status: "active", entitled: true, free_max_level: 1,
               current_period_end: null, canceled_at: null }));
    const e = await billing.entitlements();
    expect(e.entitled).toBe(true);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/entitlements");
  });

  it("starts checkout with a plan", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ url: "/x" }));
    await billing.checkout("annual");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/billing/checkout");
    expect(JSON.parse(init.body).plan).toBe("annual");
  });

  it("formats prices from cents", () => {
    expect(priceText(700, "usd")).toBe("$7.00");
    expect(priceText(6000, "usd")).toBe("$60.00");
  });
});

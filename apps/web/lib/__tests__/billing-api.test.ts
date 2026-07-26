/**
 * Billing + dev client. Thin wrappers, so these pin the request shapes the
 * backend expects.
 */
import { dev, subscription } from "../billing-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("subscription client", () => {
  it("fetches subscription state", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ status: "free", full_access: false, max_free_level: 1,
               access_until: null, cancel_at_period_end: false,
               price_interval: null, prices: {} }),
    );
    const ent = await subscription.get();
    expect(ent.status).toBe("free");
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/subscription");
  });

  it("posts the interval to checkout", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ url: "http://stripe" }));
    await subscription.checkout("year");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/subscription/checkout");
    expect(JSON.parse(init.body)).toEqual({ interval: "year" });
  });
});

describe("dev client", () => {
  it("sends enabled + scale to set-mode", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ dev_mode: true, srs_scale: 0.0001,
               srs_scale_description: "fast", presets: {} }),
    );
    await dev.setMode(true, "fast");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/dev/mode");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ enabled: true, scale: "fast" });
  });

  it("posts to unlock-all with an optional level", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ ok: true, detail: { unlocked: 5 } }));
    await dev.unlockAll(3);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/dev/unlock-all");
    expect(JSON.parse(init.body)).toEqual({ up_to_level: 3 });
  });

  it("posts to make-reviews-due", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ ok: true, detail: { made_due: 12 } }));
    const r = await dev.makeReviewsDue();
    expect(r.detail.made_due).toBe(12);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/dev/make-reviews-due");
  });
});

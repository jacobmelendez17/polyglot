/** Feedback + onboarding clients — pin the request shapes. */
import { feedback, onboarding } from "../feedback-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("feedback client", () => {
  it("submits with category, body, route, browser", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ id: "t1", state: "unanswered" }));
    await feedback.submit("bug", "broken", "/dashboard", "Firefox");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/feedback");
    expect(JSON.parse(init.body)).toEqual({
      category: "bug", body: "broken", route: "/dashboard", browser: "Firefox",
    });
  });

  it("lists with a state filter", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ total: 0, limit: 50, offset: 0, tickets: [],
               counts: { unanswered: 0, answered: 0, pinned: 0 } }),
    );
    await feedback.list("unanswered");
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("state=unanswered");
  });

  it("responds to a ticket", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ id: "t1", state: "answered" }));
    await feedback.respond("t1", "thanks");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/admin/feedback/t1/respond");
    expect(JSON.parse(init.body)).toEqual({ response: "thanks" });
  });
});

describe("onboarding client", () => {
  it("marks onboarding complete", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ completed: true }));
    await onboarding.complete();
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/onboarding/complete");
    expect(init.method).toBe("POST");
  });
});

/** Community journals client — request shapes. */
import { communityJournals } from "../community-journal-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("community journals client", () => {
  it("shares an entry", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ id: "e1", shared: true }));
    await communityJournals.share("e1");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/community-journals/e1/share");
    expect(init.method).toBe("POST");
  });

  it("reads the feed", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson([]));
    await communityJournals.feed();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/community/journals");
  });

  it("posts feedback with a body", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ id: "f1", author: "x", body: "nice", hidden: false, created_at: null }));
    await communityJournals.postFeedback("e1", "nice");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/community/journals/e1/feedback");
    expect(JSON.parse(init.body)).toEqual({ body: "nice" });
  });
});

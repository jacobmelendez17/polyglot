/** Forums client — pins the request shapes the backend expects. */
import { forums } from "../forums-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("forums client", () => {
  it("fetches categories", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson([]));
    await forums.categories();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/forums/categories");
  });

  it("posts a new thread to the category", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ id: "t1" }));
    await forums.createThread("grammar-help", "Title", "Body");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/forums/categories/grammar-help/threads");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ title: "Title", body: "Body" });
  });

  it("posts a reply to the thread", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ id: "r1" }));
    await forums.createReply("t1", "my answer");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/forums/threads/t1/replies");
    expect(JSON.parse(init.body)).toEqual({ body: "my answer" });
  });

  it("reports with a target and reason", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ reported: true, already: false, auto_hidden: false }),
    );
    await forums.report("thread", "t1", "spam");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/forums/report");
    expect(JSON.parse(init.body)).toEqual({
      target_type: "thread", target_id: "t1", reason: "spam",
    });
  });

  it("sends a moderation action", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ hidden: true, deleted: false }));
    await forums.moderate("reply", "r1", "hide");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/forums/moderation/act");
    expect(JSON.parse(init.body)).toEqual({
      target_type: "reply", target_id: "r1", action: "hide",
    });
  });
});

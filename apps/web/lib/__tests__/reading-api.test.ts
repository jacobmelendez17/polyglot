/** Reading client — request shapes. */
import { reading } from "../reading-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("reading client", () => {
  it("lists the library", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson([]));
    await reading.library();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/reading");
  });

  it("looks up a word (url-encoded)", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ word: "gato", found: false }));
    await reading.lookup("gató?");
    const url = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(url).toContain("/api/v1/reading/lookup?word=gat");
    expect(url).toContain("%3F"); // '?' encoded, not treated as a query separator
  });

  it("adds an annotation with a server-checked range", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ id: "a1", start: 3, end: 7, quote: "gato", note: "cat" }));
    await reading.addAnnotation("t1", 3, 7, "cat");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/reading/t1/annotations");
    expect(JSON.parse(init.body)).toEqual({ start: 3, end: 7, note: "cat" });
  });
});

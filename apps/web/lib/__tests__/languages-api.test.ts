/** Languages client — request shapes. */
import { languages } from "../languages-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("languages client", () => {
  it("lists languages", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson([]));
    await languages.list();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/languages");
  });

  it("reads the active language", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ code: "es-MX", name: "Spanish", native_name: "Español" }));
    const l = await languages.active();
    expect(l.code).toBe("es-MX");
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/language");
  });

  it("sets the active language via PUT", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ code: "tl-PH", name: "Tagalog", native_name: "Tagalog" }));
    await languages.setActive("tl-PH");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/language");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ code: "tl-PH" });
  });
});

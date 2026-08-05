/** Account client — request shapes. */
import { account } from "../account-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("account client", () => {
  it("gets settings", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ theme: "system" }));
    await account.getSettings();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/settings");
  });

  it("patches settings with a partial body", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ theme: "dark" }));
    await account.updateSettings({ theme: "dark" });
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/settings");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body)).toEqual({ theme: "dark" });
  });

  it("patches profile", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ display_name: "Ana" }));
    await account.updateProfile({ display_name: "Ana" });
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/profile");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body).display_name).toBe("Ana");
  });
});

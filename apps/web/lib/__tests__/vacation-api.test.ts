/** Vacation client — request shapes. */
import { vacation } from "../vacation-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("vacation client", () => {
  it("reads state", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ paused: false, since: null, days: 0 }));
    await vacation.state();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/vacation");
  });

  it("pauses", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ paused: true, since: "x", days: 0 }));
    await vacation.pause();
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/vacation/pause");
    expect(init.method).toBe("POST");
  });

  it("resumes", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ resumed: true, shifted: 3, shift_seconds: 100, paused: false, since: null, days: 0 }),
    );
    const r = await vacation.resume();
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/me/vacation/resume");
    expect(r.shifted).toBe(3);
  });
});

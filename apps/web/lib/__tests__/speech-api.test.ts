/** Speaking client — request shapes; confirms only a transcript is sent. */
import { speaking } from "../speech-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("speaking client", () => {
  it("starts a session", async () => {
    global.fetch = jest.fn().mockResolvedValue(okJson({ prompts: [] }));
    await speaking.start();
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/practice/speaking/start");
    expect(init.method).toBe("POST");
  });

  it("submits a transcript for scoring (no audio)", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ score: 100, passed: true, expected: "gato", heard: "gato",
               words: [], missed: [], extra: [], xp_awarded: 20,
               practice_stage: 1, perfect: false, already_scored: false }),
    );
    await speaking.score({
      item_type: "vocabulary", item_id: "v1", transcript: "gato", idempotency_key: "k1",
    });
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/me/practice/speaking/score");
    const body = JSON.parse(init.body);
    expect(body.transcript).toBe("gato");
    // the payload is text only — there is no audio field
    expect(body).not.toHaveProperty("audio");
  });
});

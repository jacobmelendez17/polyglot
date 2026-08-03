/** Testing client — request shapes; confirms the answer index is never requested. */
import { testing } from "../testing-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("testing client", () => {
  it("starts a map", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ attempt_id: "a1", map: "cefr", questions: [] }));
    await testing.start("cefr");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/tests/cefr/start");
    expect(init.method).toBe("POST");
  });

  it("submits an answer by index", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ correct: true, correct_index: 2, explanation: "", xp_awarded: 20,
               already_answered: false }));
    await testing.answer("a1", "q1", 2, "key1");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toContain("/api/v1/tests/attempts/a1/answer");
    const body = JSON.parse(init.body);
    expect(body).toEqual({ question_id: "q1", chosen_index: 2, idempotency_key: "key1" });
  });

  it("completes an attempt", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ map: "cefr", score: 3, total: 3, answered: 3, percentage: 100 }));
    const r = await testing.complete("a1");
    expect(r.percentage).toBe(100);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/tests/attempts/a1/complete");
  });
});

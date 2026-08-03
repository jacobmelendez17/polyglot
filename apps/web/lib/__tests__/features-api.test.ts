/** Features client + label helper. */
import { featureLabel, features } from "../features-api";

const okJson = (data: unknown) => ({ ok: true, status: 200, json: async () => data });

describe("features client", () => {
  it("lists features", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      okJson({ completed_levels: 1, features: [] }));
    const r = await features.list();
    expect(r.completed_levels).toBe(1);
    expect((global.fetch as jest.Mock).mock.calls[0][0]).toContain("/api/v1/features");
  });

  it("labels known and unknown feature keys", () => {
    expect(featureLabel("verb_conjugation")).toBe("verb conjugation");
    expect(featureLabel("some_new_thing")).toBe("some new thing"); // underscores → spaces
  });
});

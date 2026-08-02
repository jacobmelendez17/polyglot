/** Analytics helper — safe no-op when Plausible isn't present. */
import { AnalyticsEvent, track } from "../analytics";

describe("analytics track()", () => {
  afterEach(() => {
    delete (window as unknown as { plausible?: unknown }).plausible;
  });

  it("no-ops when plausible isn't loaded", () => {
    expect(() => track("signup")).not.toThrow();
  });

  it("forwards the event and props when plausible is present", () => {
    const spy = jest.fn();
    (window as unknown as { plausible: unknown }).plausible = spy;
    track(AnalyticsEvent.LessonComplete, { level: 1 });
    expect(spy).toHaveBeenCalledWith("lesson_complete", { props: { level: 1 } });
  });

  it("swallows errors from a broken plausible", () => {
    (window as unknown as { plausible: unknown }).plausible = () => {
      throw new Error("boom");
    };
    expect(() => track("demo_click")).not.toThrow();
  });
});

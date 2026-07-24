/**
 * relativeTime formats every review/cooldown timestamp in the item UI, so its
 * edge cases (null, garbage, exactly one unit, past vs future) are worth
 * pinning down.
 */
import { relativeTime } from "../items-api";

const NOW = new Date("2026-07-22T12:00:00Z");

describe("relativeTime", () => {
  it("renders a dash when there is no timestamp", () => {
    expect(relativeTime(null, NOW)).toBe("—");
  });

  it("renders a dash for an unparseable value", () => {
    expect(relativeTime("not a date", NOW)).toBe("—");
  });

  it("counts forward for future reviews", () => {
    expect(relativeTime("2026-07-22T16:00:00Z", NOW)).toBe("in 4 hrs");
    expect(relativeTime("2026-07-25T12:00:00Z", NOW)).toBe("in 3 days");
  });

  it("counts backward for past events", () => {
    expect(relativeTime("2026-07-22T08:00:00Z", NOW)).toBe("4 hrs ago");
    expect(relativeTime("2026-07-19T12:00:00Z", NOW)).toBe("3 days ago");
  });

  it("singularises a single unit", () => {
    expect(relativeTime("2026-07-22T13:00:00Z", NOW)).toBe("in 1 hr");
    expect(relativeTime("2026-07-23T12:00:00Z", NOW)).toBe("in 1 day");
  });

  it("never renders zero minutes", () => {
    expect(relativeTime("2026-07-22T12:00:10Z", NOW)).toBe("in 1 min");
  });
});

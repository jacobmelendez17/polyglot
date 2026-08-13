/** item-extras (slice 44): review-time rounding + word count. */
import { countWords, shortDate, timeUntilReview } from "../item-extras";

const NOW = Date.parse("2026-08-13T12:00:00Z");
const at = (mins: number) => new Date(NOW + mins * 60000).toISOString();

describe("timeUntilReview", () => {
  it("says available when due or past", () => {
    expect(timeUntilReview(at(-10), NOW)).toBe("review available now");
    expect(timeUntilReview(at(0), NOW)).toBe("review available now");
  });
  it("shows exact minutes in the last five", () => {
    expect(timeUntilReview(at(4), NOW)).toBe("4 minutes until next review");
    expect(timeUntilReview(at(1), NOW)).toBe("1 minute until next review");
  });
  it("collapses to 'less than an hour' between 5 and 60 minutes", () => {
    expect(timeUntilReview(at(30), NOW)).toBe("less than an hour until next review");
  });
  it("rounds by hour, day, week, month", () => {
    expect(timeUntilReview(at(180), NOW)).toBe("3 hours until next review");
    expect(timeUntilReview(at(60 * 24 * 2), NOW)).toBe("2 days until next review");
    expect(timeUntilReview(at(60 * 24 * 8), NOW)).toBe("1 week until next review");
    expect(timeUntilReview(at(60 * 24 * 60), NOW)).toBe("2 months until next review");
  });
  it("handles a missing timestamp", () => {
    expect(timeUntilReview(null, NOW)).toBe("no review scheduled");
  });
});

describe("countWords", () => {
  it("counts whitespace-separated words", () => {
    expect(countWords("")).toBe(0);
    expect(countWords("  hola   mundo test  ")).toBe(3);
  });
});

describe("shortDate", () => {
  it("returns a dash for missing dates", () => {
    expect(shortDate(null)).toBe("—");
  });
  it("formats a real date", () => {
    expect(shortDate("2026-08-13T12:00:00Z")).toMatch(/2026/);
  });
});

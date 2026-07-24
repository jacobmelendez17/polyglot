/**
 * Client layout helpers. These mirror the server rules in domain/widgets.py —
 * if they drift, a dragged card jumps back after the save lands, so the same
 * behaviours are pinned on both sides.
 */
import {
  addWidget, availableToAdd, clampSpan, moveAnnouncement, moveWidget,
  removeWidget, reorderWidget, setSpan,
  type CatalogEntry, type LayoutEntry,
} from "../widget-layout";

const catalog: CatalogEntry[] = [
  { key: "welcome", title: "Welcome", description: "", default: true, span: 6, min_span: 3, max_span: 6 },
  { key: "xp", title: "XP", description: "", default: true, span: 1, min_span: 1, max_span: 2 },
  { key: "leech", title: "Tricky items", description: "", default: true, span: 2, min_span: 1, max_span: 3 },
  { key: "forecast", title: "Review forecast", description: "", default: false, span: 2, min_span: 2, max_span: 6 },
];

const layout = (...keys: string[]): LayoutEntry[] =>
  keys.map((key) => ({ key, span: catalog.find((c) => c.key === key)?.span ?? 2 }));

const keys = (entries: LayoutEntry[]) => entries.map((e) => e.key);

describe("moveWidget", () => {
  it("shifts a widget by one place", () => {
    expect(keys(moveWidget(layout("welcome", "xp", "leech"), "leech", -1)))
      .toEqual(["welcome", "leech", "xp"]);
  });

  it("clamps at the ends instead of wrapping", () => {
    const start = layout("welcome", "xp");
    expect(keys(moveWidget(start, "welcome", -3))).toEqual(["welcome", "xp"]);
    expect(keys(moveWidget(start, "xp", 3))).toEqual(["welcome", "xp"]);
  });

  it("returns the same array when nothing moves, so React can skip the render", () => {
    const start = layout("welcome", "xp");
    expect(moveWidget(start, "welcome", -1)).toBe(start);
    expect(moveWidget(start, "xp", 0)).toBe(start);
    expect(moveWidget(start, "ghost", 1)).toBe(start);
  });

  it("does not mutate the input", () => {
    const start = layout("welcome", "xp", "leech");
    const snapshot = keys(start);
    moveWidget(start, "leech", -2);
    expect(keys(start)).toEqual(snapshot);
  });
});

describe("reorderWidget", () => {
  it("drops a widget at an index", () => {
    expect(keys(reorderWidget(layout("welcome", "xp", "leech"), "leech", 0)))
      .toEqual(["leech", "welcome", "xp"]);
  });

  it("keeps the other widgets in order", () => {
    expect(keys(reorderWidget(layout("welcome", "xp", "leech", "forecast"), "xp", 3)))
      .toEqual(["welcome", "leech", "forecast", "xp"]);
  });

  it("ignores an unknown key", () => {
    const start = layout("welcome", "xp");
    expect(reorderWidget(start, "ghost", 0)).toBe(start);
  });
});

describe("addWidget / removeWidget", () => {
  it("appends a new widget at its default span", () => {
    const next = addWidget(layout("welcome"), catalog[3]);
    expect(keys(next)).toEqual(["welcome", "forecast"]);
    expect(next[1].span).toBe(2);
  });

  it("will not add the same widget twice", () => {
    const start = layout("welcome");
    expect(addWidget(start, catalog[0])).toBe(start);
  });

  it("ignores an undefined catalog entry", () => {
    const start = layout("welcome");
    expect(addWidget(start, undefined)).toBe(start);
  });

  it("removes a widget", () => {
    expect(keys(removeWidget(layout("welcome", "xp"), "xp"))).toEqual(["welcome"]);
  });

  it("allows removing everything", () => {
    expect(removeWidget(removeWidget(layout("welcome", "xp"), "xp"), "welcome"))
      .toEqual([]);
  });
});

describe("spans", () => {
  it("clamps to the widget's own limits", () => {
    expect(clampSpan(catalog[1], 6)).toBe(2);   // xp maxes at 2
    expect(clampSpan(catalog[0], 1)).toBe(3);   // welcome needs at least 3
  });

  it("leaves the span alone when the widget is unknown", () => {
    expect(clampSpan(undefined, 4)).toBe(4);
  });

  it("setSpan clamps rather than storing what was asked for", () => {
    const next = setSpan(layout("xp"), "xp", 6, catalog);
    expect(next[0].span).toBe(2);
  });
});

describe("availableToAdd", () => {
  it("is the catalog minus what is already shown", () => {
    const options = availableToAdd(layout("welcome", "xp"), catalog);
    expect(options.map((o) => o.key)).toEqual(["leech", "forecast"]);
  });

  it("is empty once everything is on the dashboard", () => {
    const all = layout(...catalog.map((c) => c.key));
    expect(availableToAdd(all, catalog)).toEqual([]);
  });
});

describe("moveAnnouncement", () => {
  it("reads as a sentence, one-indexed", () => {
    expect(moveAnnouncement("XP", 2, 7)).toBe("XP moved to position 3 of 7");
  });
});

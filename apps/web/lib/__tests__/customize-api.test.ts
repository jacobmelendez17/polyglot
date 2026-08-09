/** Customize grouping helper. */
import { groupItems, itemKey, type SelectableItem } from "../customize-api";

const mk = (t: string, type: string, pos: string): SelectableItem => ({
  item_type: type, item_id: t, term: t, translation: t + "-en", part_of_speech: pos,
});

const ITEMS = [
  mk("gato", "vocabulary", "noun"),
  mk("correr", "vocabulary", "verb"),
  mk("rápido", "vocabulary", "adjective"),
  mk("ser-estar", "grammar", "grammar"),
];

describe("groupItems", () => {
  it("groups by type", () => {
    const g = groupItems(ITEMS, "type");
    expect(g.map((x) => x.name)).toEqual(["vocabulary", "grammar"]);
    expect(g[0].items).toHaveLength(3);
    expect(g[1].items).toHaveLength(1);
  });

  it("groups by theme (part of speech), sorted", () => {
    const g = groupItems(ITEMS, "theme");
    expect(g.map((x) => x.name)).toEqual(["adjective", "grammar", "noun", "verb"]);
  });

  it("random returns one shuffled group with every item, stable for a seed", () => {
    const a = groupItems(ITEMS, "random", 7);
    const b = groupItems(ITEMS, "random", 7);
    expect(a[0].items.map(itemKey).sort()).toEqual(ITEMS.map(itemKey).sort());
    expect(a[0].items.map(itemKey)).toEqual(b[0].items.map(itemKey)); // deterministic
  });

  it("drops empty groups", () => {
    const g = groupItems([mk("x", "vocabulary", "noun")], "type");
    expect(g.map((x) => x.name)).toEqual(["vocabulary"]);
  });
});

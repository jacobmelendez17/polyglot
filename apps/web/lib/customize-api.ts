// Customize Lessons client + the pure filter/grouping used by the page.
import { request } from "./http";

export interface SelectableItem {
  item_type: string;
  item_id: string;
  term: string;
  translation: string;
  part_of_speech: string;
}
export interface SelectableLevel {
  level: number;
  title: string;
  items: SelectableItem[];
}

export const customize = {
  selectable: () => request<{ levels: SelectableLevel[] }>("/api/v1/lessons/selectable"),
};

export type GroupMode = "type" | "theme" | "random";

export function itemKey(i: SelectableItem): string {
  return `${i.item_type}:${i.item_id}`;
}

// Split a level's items into named groups for the active filter. Pure + deterministic
// (random uses a seeded shuffle) so the UI can animate items into stable buckets.
export function groupItems(items: SelectableItem[], mode: GroupMode, seed = 1): {
  name: string; items: SelectableItem[];
}[] {
  if (mode === "type") {
    const vocab = items.filter((i) => i.item_type === "vocabulary");
    const grammar = items.filter((i) => i.item_type === "grammar");
    return [
      { name: "vocabulary", items: vocab },
      { name: "grammar", items: grammar },
    ].filter((g) => g.items.length > 0);
  }
  if (mode === "theme") {
    const by = new Map<string, SelectableItem[]>();
    for (const i of items) {
      const key = i.part_of_speech || "other";
      (by.get(key) ?? by.set(key, []).get(key)!).push(i);
    }
    return [...by.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([name, items]) => ({ name, items }));
  }
  // random: one shuffled group (seeded so re-render is stable)
  const arr = [...items];
  let s = seed;
  for (let n = arr.length - 1; n > 0; n--) {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    const j = s % (n + 1);
    [arr[n], arr[j]] = [arr[j], arr[n]];
  }
  return [{ name: "shuffled", items: arr }];
}

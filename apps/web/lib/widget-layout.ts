// Pure layout helpers, mirroring apps/api/app/domain/widgets.py.
//
// The server is authoritative — every PUT comes back normalized — but the UI
// has to reorder optimistically or dragging a card would feel like submitting a
// form. These functions keep the optimistic result identical to what the server
// will store, so the card never jumps after the save lands.

export interface CatalogEntry {
  key: string;
  title: string;
  description: string;
  default: boolean;
  span: number;
  min_span: number;
  max_span: number;
}

export interface LayoutEntry {
  key: string;
  span: number;
}

export interface Layout {
  version: number;
  widgets: LayoutEntry[];
}

export const GRID_COLUMNS = 6;

export function clampSpan(entry: CatalogEntry | undefined, span: number): number {
  if (!entry) return span;
  return Math.max(entry.min_span, Math.min(span, entry.max_span));
}

/** Move a widget by `delta` places. Clamped at both ends — never wraps. */
export function moveWidget(
  widgets: LayoutEntry[], key: string, delta: number,
): LayoutEntry[] {
  const index = widgets.findIndex((w) => w.key === key);
  if (index === -1 || delta === 0) return widgets;
  const target = Math.max(0, Math.min(widgets.length - 1, index + delta));
  if (target === index) return widgets;
  const next = [...widgets];
  const [entry] = next.splice(index, 1);
  next.splice(target, 0, entry);
  return next;
}

/** Drag-and-drop's move: put `key` at `toIndex`. */
export function reorderWidget(
  widgets: LayoutEntry[], key: string, toIndex: number,
): LayoutEntry[] {
  const index = widgets.findIndex((w) => w.key === key);
  if (index === -1) return widgets;
  return moveWidget(widgets, key, toIndex - index);
}

export function addWidget(
  widgets: LayoutEntry[], entry: CatalogEntry | undefined,
): LayoutEntry[] {
  if (!entry || widgets.some((w) => w.key === entry.key)) return widgets;
  return [...widgets, { key: entry.key, span: entry.span }];
}

export function removeWidget(widgets: LayoutEntry[], key: string): LayoutEntry[] {
  return widgets.filter((w) => w.key !== key);
}

export function setSpan(
  widgets: LayoutEntry[], key: string, span: number, catalog: CatalogEntry[],
): LayoutEntry[] {
  const entry = catalog.find((c) => c.key === key);
  return widgets.map((w) =>
    w.key === key ? { ...w, span: clampSpan(entry, span) } : w,
  );
}

export function availableToAdd(
  widgets: LayoutEntry[], catalog: CatalogEntry[],
): CatalogEntry[] {
  const present = new Set(widgets.map((w) => w.key));
  return catalog.filter((c) => !present.has(c.key));
}

/** Announcement text for the screen-reader live region during a keyboard move. */
export function moveAnnouncement(
  title: string, index: number, total: number,
): string {
  return `${title} moved to position ${index + 1} of ${total}`;
}

"""Dashboard widget catalog and layout rules — pure functions (PLANNING §15).

A layout is an ordered list of visible widgets. Order is the list order; a
widget the learner removed is simply absent. That makes "add", "remove", and
"move" ordinary list operations, and it makes the stored JSON small and
readable.

Everything here is deterministic and DB-free. The service layer persists the
result; the rules live here so a bad layout can never be written:

  * unknown keys are dropped rather than stored (a stale client can't wedge
    someone's dashboard by writing a widget that no longer exists)
  * duplicates collapse to the first occurrence
  * spans are clamped to what each widget can actually render at
  * an empty layout is legal — removing everything is a choice, not an error
"""
from __future__ import annotations

from dataclasses import dataclass, field

LAYOUT_VERSION = 1

# The grid is 6 columns wide on desktop (matches the dashboard's md:grid-cols-6).
GRID_COLUMNS = 6
MAX_WIDGETS = 24


@dataclass(frozen=True)
class Widget:
    """One entry in the catalog of things a dashboard can show."""

    key: str
    title: str
    description: str
    default: bool
    span: int                  # preferred width in grid columns
    min_span: int = 1
    max_span: int = GRID_COLUMNS

    def clamp(self, span: int | None) -> int:
        if span is None:
            return self.span
        return max(self.min_span, min(int(span), self.max_span))

    def to_dict(self) -> dict:
        return {
            "key": self.key, "title": self.title, "description": self.description,
            "default": self.default, "span": self.span,
            "min_span": self.min_span, "max_span": self.max_span,
        }


# The catalog is the single source of truth for what a dashboard can show.
# Every key here has a matching component in the web app's widget registry; a
# key with no component would render an empty hole, so the two lists are kept
# in step deliberately rather than by convention.
CATALOG: tuple[Widget, ...] = (
    Widget("welcome", "Welcome", "A greeting and what's waiting for you today.",
           default=True, span=6, min_span=3),
    Widget("progression", "Progression", "How your items are spread across SRS stages.",
           default=True, span=3, min_span=2),
    Widget("forecast", "Review forecast", "Reviews arriving over the next seven days.",
           default=True, span=2, min_span=2),
    Widget("xp", "XP", "Total experience earned.",
           default=True, span=1, max_span=2),
    Widget("fluent", "Fluent items", "How many items have reached Fluent.",
           default=True, span=2, max_span=3),
    Widget("leech", "Tricky items", "Items that keep tripping you up.",
           default=True, span=2, max_span=3),
    Widget("practice", "Practice", "A shortcut into extra drilling.",
           default=True, span=2, max_span=3),
    Widget("next_review", "Next review", "When your next review lands.",
           default=False, span=2, max_span=3),
    Widget("stage_detail", "SRS stages", "A count for every one of the nine stages.",
           default=False, span=3, min_span=2),
    Widget("lessons_ready", "Lessons ready", "Items waiting to be learned.",
           default=False, span=2, max_span=3),
)

CATALOG_BY_KEY: dict[str, Widget] = {w.key: w for w in CATALOG}


@dataclass(frozen=True)
class LayoutEntry:
    key: str
    span: int

    def to_dict(self) -> dict:
        return {"key": self.key, "span": self.span}


@dataclass(frozen=True)
class Layout:
    entries: tuple[LayoutEntry, ...] = field(default_factory=tuple)
    version: int = LAYOUT_VERSION

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(e.key for e in self.entries)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "widgets": [e.to_dict() for e in self.entries],
        }


def default_layout() -> Layout:
    return Layout(
        entries=tuple(LayoutEntry(w.key, w.span) for w in CATALOG if w.default)
    )


def normalize(raw: object) -> Layout:
    """Turn anything a client sent — or anything already in the database — into
    a layout we are willing to render.

    Never raises. A layout that cannot be understood degrades to the defaults,
    because a learner opening their dashboard to an exception would be a much
    worse outcome than a layout reset.
    """
    widgets = None
    if isinstance(raw, dict):
        widgets = raw.get("widgets")
    elif isinstance(raw, list):
        widgets = raw
    if not isinstance(widgets, list):
        return default_layout()

    seen: set[str] = set()
    entries: list[LayoutEntry] = []
    for item in widgets[:MAX_WIDGETS * 4]:      # bound the work on hostile input
        if isinstance(item, str):
            key, span = item, None
        elif isinstance(item, dict):
            key, span = item.get("key"), item.get("span")
        else:
            continue
        if not isinstance(key, str):
            continue
        widget = CATALOG_BY_KEY.get(key)
        if widget is None or key in seen:
            continue
        try:
            clamped = widget.clamp(span if isinstance(span, (int, float)) else None)
        except (TypeError, ValueError):
            clamped = widget.span
        seen.add(key)
        entries.append(LayoutEntry(key, clamped))
        if len(entries) >= MAX_WIDGETS:
            break
    return Layout(entries=tuple(entries))


def add_widget(layout: Layout, key: str) -> Layout:
    """Append a widget. Adding one that's already there is a no-op, not an error."""
    widget = CATALOG_BY_KEY.get(key)
    if widget is None or key in layout.keys or len(layout.entries) >= MAX_WIDGETS:
        return layout
    return Layout(entries=(*layout.entries, LayoutEntry(key, widget.span)))


def remove_widget(layout: Layout, key: str) -> Layout:
    return Layout(entries=tuple(e for e in layout.entries if e.key != key))


def move_widget(layout: Layout, key: str, delta: int) -> Layout:
    """Shift a widget by `delta` places. Movement past either end is clamped, so
    holding the arrow key at the top of the list does nothing rather than
    wrapping the widget around to the bottom."""
    entries = list(layout.entries)
    index = next((i for i, e in enumerate(entries) if e.key == key), None)
    if index is None or delta == 0:
        return layout
    target = max(0, min(len(entries) - 1, index + delta))
    if target == index:
        return layout
    entry = entries.pop(index)
    entries.insert(target, entry)
    return Layout(entries=tuple(entries))


def reorder(layout: Layout, key: str, to_index: int) -> Layout:
    """Drag-and-drop's move: put `key` at `to_index`."""
    index = next((i for i, e in enumerate(layout.entries) if e.key == key), None)
    if index is None:
        return layout
    return move_widget(layout, key, to_index - index)


def set_span(layout: Layout, key: str, span: int) -> Layout:
    widget = CATALOG_BY_KEY.get(key)
    if widget is None:
        return layout
    return Layout(entries=tuple(
        LayoutEntry(e.key, widget.clamp(span)) if e.key == key else e
        for e in layout.entries
    ))


def available_to_add(layout: Layout) -> tuple[Widget, ...]:
    present = set(layout.keys)
    return tuple(w for w in CATALOG if w.key not in present)


def catalog_dicts() -> list[dict]:
    return [w.to_dict() for w in CATALOG]

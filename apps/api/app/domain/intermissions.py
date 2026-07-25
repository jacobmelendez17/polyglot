"""Intermission triggers — pure functions (spec §17).

An intermission is a short reading that appears between lessons: a culture note,
a pronunciation tip, a regional quirk. They are informational only — there is
nothing to answer, and viewing one is the whole interaction.

Each intermission carries a `trigger` JSON blob saying when it should appear.
This module decides whether a given trigger matches the moment the learner is
in. It is deliberately small and total: an unrecognised trigger kind never
matches rather than raising, because a malformed row written by an admin should
mean "this one doesn't show" and not "lessons are broken".

Supported trigger kinds:

    {"kind": "level_start",     "level": 1}
    {"kind": "lesson_complete", "level": 1, "lesson": 2}
    {"kind": "items_learned",   "count": 25}
    {"kind": "srs_stage",       "stage": 5}

`level`/`lesson` may be omitted to match any level/lesson.
"""
from __future__ import annotations

from dataclasses import dataclass

TRIGGER_KINDS = ("level_start", "lesson_complete", "items_learned", "srs_stage")

EVENTS = ("level_start", "lesson_complete", "progress")

# How many intermissions may appear at once. Two short readings between lessons
# is a pause; six is a wall, and a learner will start dismissing them unread.
MAX_PER_EVENT = 2


@dataclass(frozen=True)
class TriggerContext:
    """Where the learner is right now."""

    event: str
    level: int | None = None
    lesson: int | None = None
    items_learned: int = 0
    highest_stage: int = 0


@dataclass(frozen=True)
class Candidate:
    """An intermission we might show, reduced to what the decision needs."""

    id: str
    trigger: dict
    title: str
    order_hint: int = 0


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def matches(trigger: object, ctx: TriggerContext) -> bool:
    """Does this trigger fire in this context?

    Returns False for anything unrecognised rather than raising — a bad row
    should be invisible, not fatal.
    """
    if not isinstance(trigger, dict):
        return False
    kind = trigger.get("kind")
    if kind not in TRIGGER_KINDS:
        return False

    if kind == "level_start":
        if ctx.event != "level_start":
            return False
        want = _as_int(trigger.get("level"))
        return want is None or want == ctx.level

    if kind == "lesson_complete":
        if ctx.event != "lesson_complete":
            return False
        want_level = _as_int(trigger.get("level"))
        want_lesson = _as_int(trigger.get("lesson"))
        if want_level is not None and want_level != ctx.level:
            return False
        return want_lesson is None or want_lesson == ctx.lesson

    # The threshold kinds fire on any event, because "you have learned 25 words"
    # is true from the moment it is true, not only at a lesson boundary.
    if kind == "items_learned":
        want = _as_int(trigger.get("count"))
        return want is not None and ctx.items_learned >= want

    if kind == "srs_stage":
        want = _as_int(trigger.get("stage"))
        return want is not None and ctx.highest_stage >= want

    return False


def select_due(
    candidates: list[Candidate],
    ctx: TriggerContext,
    seen_ids: set[str] | frozenset[str],
    limit: int = MAX_PER_EVENT,
) -> list[Candidate]:
    """The intermissions to show right now, oldest curriculum order first.

    Already-seen intermissions never reappear: they are readings, not reviews.
    """
    due = [
        c for c in candidates
        if c.id not in seen_ids and matches(c.trigger, ctx)
    ]
    due.sort(key=lambda c: (c.order_hint, c.title))
    return due[:max(0, limit)]


def describe(trigger: object) -> str:
    """Human-readable trigger, for the admin list."""
    if not isinstance(trigger, dict):
        return "never (malformed trigger)"
    kind = trigger.get("kind")
    level, lesson = _as_int(trigger.get("level")), _as_int(trigger.get("lesson"))
    if kind == "level_start":
        return f"starting level {level}" if level else "starting any level"
    if kind == "lesson_complete":
        where = f"level {level}" if level else "any level"
        which = f"lesson {lesson}" if lesson else "any lesson"
        return f"finishing {which} of {where}"
    if kind == "items_learned":
        return f"after learning {_as_int(trigger.get('count'))} items"
    if kind == "srs_stage":
        return f"on reaching SRS stage {_as_int(trigger.get('stage'))}"
    return "never (unknown trigger)"

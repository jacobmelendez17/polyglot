"""SRS engine — pure, deterministic functions (PLANNING §5, §10).

No database, no clock, no randomness without injection. Everything here is
unit-testable in isolation; the service layer wires it to the DB.

Stages (1..9):
    1 Beginner 1  → 4h        6 Familiar 2    → 2wk
    2 Beginner 2  → 8h        7 Intermediate  → 1mo
    3 Beginner 3  → 1d        8 Advanced      → 4mo
    4 Beginner 4  → 2d        9 Fluent        → (out of queue)
    5 Familiar 1  → 1wk
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from enum import IntEnum


class Stage(IntEnum):
    beginner_1 = 1
    beginner_2 = 2
    beginner_3 = 3
    beginner_4 = 4
    familiar_1 = 5
    familiar_2 = 6
    intermediate = 7
    advanced = 8
    fluent = 9


MIN_STAGE = Stage.beginner_1
MAX_STAGE = Stage.fluent
FAMILIAR_THRESHOLD = Stage.familiar_1  # penalty factor doubles at/above this

STAGE_NAMES: dict[int, str] = {
    1: "Beginner 1", 2: "Beginner 2", 3: "Beginner 3", 4: "Beginner 4",
    5: "Familiar 1", 6: "Familiar 2", 7: "Intermediate", 8: "Advanced", 9: "Fluent",
}

# Interval to the NEXT review, keyed by the stage the item just reached.
# Stage 9 (Fluent) has no interval: the item leaves the review queue.
INTERVALS: dict[int, dt.timedelta] = {
    1: dt.timedelta(hours=4),
    2: dt.timedelta(hours=8),
    3: dt.timedelta(days=1),
    4: dt.timedelta(days=2),
    5: dt.timedelta(weeks=1),
    6: dt.timedelta(weeks=2),
    7: dt.timedelta(days=30),
    8: dt.timedelta(days=120),
}

# Leech items are reviewed more often (PLANNING §13: "slowed down SRS").
LEECH_INTERVAL_MULTIPLIER = 0.5


def penalty_factor(stage: int) -> int:
    """1 below Familiar 1, 2 at Familiar 1 and above (PLANNING §10)."""
    return 2 if stage >= FAMILIAR_THRESHOLD else 1


def incorrect_adjustment_count(wrong_answer_count: int) -> int:
    """ceil(number_of_wrong_answers / 2) — the spec's formula."""
    return math.ceil(wrong_answer_count / 2)


def apply_srs(stage: int, wrong_answer_count: int) -> int:
    """The core transition. Promotion needs a clean pair (zero wrong attempts).

        new_stage = stage - (ceil(wrong / 2) * penalty_factor)

    Never drops below Beginner 1; never exceeds Fluent.
    """
    if stage < MIN_STAGE or stage > MAX_STAGE:
        raise ValueError(f"stage out of range: {stage}")
    if wrong_answer_count < 0:
        raise ValueError("wrong_answer_count must be >= 0")

    if wrong_answer_count == 0:
        return min(stage + 1, int(MAX_STAGE))

    drop = incorrect_adjustment_count(wrong_answer_count) * penalty_factor(stage)
    return max(int(MIN_STAGE), stage - drop)


def next_review_at(
    stage: int, now: dt.datetime, *, is_leech: bool = False
) -> dt.datetime | None:
    """When this item should next surface. None once Fluent (leaves the queue)."""
    interval = INTERVALS.get(stage)
    if interval is None:
        return None
    if is_leech:
        interval = dt.timedelta(seconds=interval.total_seconds() * LEECH_INTERVAL_MULTIPLIER)
    return now + interval


@dataclass(frozen=True)
class SrsOutcome:
    stage_before: int
    stage_after: int
    promoted: bool
    penalty: int
    wrong_answer_count: int
    next_review_at: dt.datetime | None


def resolve_pair(
    *, stage_before: int, wrong_answer_count: int, now: dt.datetime, is_leech: bool = False
) -> SrsOutcome:
    """Apply a completed meaning+reading pair to an item's SRS state."""
    stage_after = apply_srs(stage_before, wrong_answer_count)
    return SrsOutcome(
        stage_before=stage_before,
        stage_after=stage_after,
        promoted=stage_after > stage_before,
        penalty=penalty_factor(stage_before) if wrong_answer_count else 0,
        wrong_answer_count=wrong_answer_count,
        next_review_at=next_review_at(stage_after, now, is_leech=is_leech),
    )


def stage_name(stage: int) -> str:
    return STAGE_NAMES.get(stage, f"Stage {stage}")


def is_fluent(stage: int) -> bool:
    return stage >= MAX_STAGE


# --- Prompt kind by stage (PLANNING §10) ---------------------------------

def prompt_kind_for_stage(stage: int) -> str:
    """Beginner 1-4: direct translation. Familiar: short-phrase cloze.
    Intermediate/Advanced: larger-sentence cloze."""
    if stage <= 4:
        return "translation"
    if stage <= 6:
        return "cloze_short"
    return "cloze_long"

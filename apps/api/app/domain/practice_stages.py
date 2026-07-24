"""Practice stages (Uno..Cinco) and Perfect status — pure functions.

PLANNING §5.5 / spec §10. An item carries exactly ONE SRS stage, but it also
carries a separate practice stage per category:

    sentences · listening · speaking

Each runs 0..5. Stage 5 means that category is finished. When all three are
finished — and the item is Fluent in the SRS — the item is "Perfect".

Two rules make this more than a counter:

  1. **24-hour cooldown.** A stage can only advance once per day per category,
     so a learner cannot grind an item from Uno to Cinco in one sitting. That
     is the whole point of a spaced system; without the gate the stages measure
     persistence in a single session rather than retention over days.
  2. **Correct answers only.** A wrong answer holds the stage. Practice is
     low-stakes: it never demotes, and it never touches the SRS stage.

Everything here is deterministic — no clock, no DB, no randomness. `now` is
always injected so the cooldown is testable to the second.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

# The three trackable practice categories (matches the practice_category enum).
PRACTICE_CATEGORIES: tuple[str, ...] = ("sentences", "listening", "speaking")

MIN_PRACTICE_STAGE = 0
MAX_PRACTICE_STAGE = 5

# Minimum wall-clock time between two stage-ups in the same category.
STAGE_COOLDOWN = dt.timedelta(hours=24)

# Fallback stage names when a language row has none. Spanish per spec §10.
DEFAULT_STAGE_NAMES: tuple[str, ...] = ("Uno", "Dos", "Tres", "Cuatro", "Cinco")

# The SRS stage at which an item counts as Fluent (domain.srs.Stage.fluent).
FLUENT_SRS_STAGE = 9


def _utc(value: dt.datetime | None) -> dt.datetime | None:
    """Treat naive timestamps as UTC.

    Some columns in this schema are naive `DateTime` while the services work in
    aware UTC. Comparing the two raises TypeError, so every datetime crossing
    into this module is normalised here rather than at each call site.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def clamp_stage(stage: int) -> int:
    return max(MIN_PRACTICE_STAGE, min(int(stage or 0), MAX_PRACTICE_STAGE))


# --- cooldown ------------------------------------------------------------

def next_available_at(stage_reached_at: dt.datetime | None) -> dt.datetime | None:
    """When the next stage-up becomes possible. None if it is possible now."""
    reached = _utc(stage_reached_at)
    if reached is None:
        return None
    return reached + STAGE_COOLDOWN


def cooldown_active(
    stage_reached_at: dt.datetime | None, now: dt.datetime,
) -> bool:
    available = next_available_at(stage_reached_at)
    if available is None:
        return False
    current = _utc(now)
    assert current is not None  # `now` is never None
    return current < available


def cooldown_remaining(
    stage_reached_at: dt.datetime | None, now: dt.datetime,
) -> dt.timedelta:
    """How long is left on the cooldown. Zero when it has expired."""
    available = next_available_at(stage_reached_at)
    current = _utc(now)
    if available is None or current is None or current >= available:
        return dt.timedelta(0)
    return available - current


# --- stage progression ---------------------------------------------------

@dataclass(frozen=True)
class StageOutcome:
    """The result of one practice answer against one category's stage."""

    stage_before: int
    stage_after: int
    advanced: bool
    held_by_cooldown: bool
    held_by_wrong_answer: bool
    complete: bool
    # Timestamp to persist as `stage_reached_at` (None = leave unchanged).
    reached_at: dt.datetime | None
    # When the NEXT stage-up becomes possible (None = right now).
    next_available_at: dt.datetime | None

    def to_dict(self) -> dict:
        return {
            "stage_before": self.stage_before,
            "stage_after": self.stage_after,
            "advanced": self.advanced,
            "held_by_cooldown": self.held_by_cooldown,
            "complete": self.complete,
            "next_available_at": (
                self.next_available_at.isoformat() if self.next_available_at else None
            ),
        }


def resolve_stage(
    current: int,
    *,
    correct: bool,
    stage_reached_at: dt.datetime | None,
    now: dt.datetime,
) -> StageOutcome:
    """Apply one practice answer to one category's practice stage.

    Advances by exactly one stage when the answer is correct, the category is
    not already at Cinco, and the 24-hour cooldown has expired. Otherwise the
    stage is held and the reason is reported so the UI can explain itself.
    """
    stage = clamp_stage(current)
    on_cooldown = cooldown_active(stage_reached_at, now)
    at_cap = stage >= MAX_PRACTICE_STAGE

    if not correct or at_cap or on_cooldown:
        return StageOutcome(
            stage_before=stage,
            stage_after=stage,
            advanced=False,
            held_by_cooldown=bool(on_cooldown and correct and not at_cap),
            held_by_wrong_answer=not correct,
            complete=at_cap,
            reached_at=None,
            next_available_at=None if at_cap else next_available_at(stage_reached_at),
        )

    moment = _utc(now)
    new_stage = stage + 1
    return StageOutcome(
        stage_before=stage,
        stage_after=new_stage,
        advanced=True,
        held_by_cooldown=False,
        held_by_wrong_answer=False,
        complete=new_stage >= MAX_PRACTICE_STAGE,
        reached_at=moment,
        next_available_at=(
            None if new_stage >= MAX_PRACTICE_STAGE else next_available_at(moment)
        ),
    )


# --- naming --------------------------------------------------------------

def stage_label(stage: int, names: list[str] | tuple[str, ...] | None = None) -> str:
    """"Stage Uno" .. "Stage Cinco", localised from `languages.stage_names`.

    Stage 0 has no name — the learner has not started that category yet.
    """
    stage = clamp_stage(stage)
    if stage == 0:
        return "Not started"
    pool = tuple(names) if names else DEFAULT_STAGE_NAMES
    if stage <= len(pool):
        return f"Stage {pool[stage - 1]}"
    return f"Stage {stage}"


# --- category + item completion -----------------------------------------

def category_complete(stage: int) -> bool:
    """A single category is finished at Cinco."""
    return clamp_stage(stage) >= MAX_PRACTICE_STAGE


def completed_categories(stages: dict[str, int]) -> list[str]:
    return [c for c in PRACTICE_CATEGORIES if category_complete(stages.get(c, 0))]


def all_categories_complete(stages: dict[str, int]) -> bool:
    """Every tracked category at Cinco. Missing categories count as 0."""
    return all(category_complete(stages.get(c, 0)) for c in PRACTICE_CATEGORIES)


def qualifies_for_perfect(stages: dict[str, int], srs_stage: int) -> bool:
    """Perfect = all three practice categories at Cinco AND Fluent in the SRS.

    The SRS half matters: finishing the drills without the item surviving the
    four-month interval would make "Perfect" a measure of effort rather than of
    knowing the word.
    """
    return all_categories_complete(stages) and int(srs_stage or 0) >= FLUENT_SRS_STAGE


def perfect_progress(stages: dict[str, int], srs_stage: int) -> dict:
    """A UI-ready breakdown of what Perfect still needs."""
    done = completed_categories(stages)
    fluent = int(srs_stage or 0) >= FLUENT_SRS_STAGE
    return {
        "categories_complete": len(done),
        "categories_total": len(PRACTICE_CATEGORIES),
        "completed_categories": done,
        "remaining_categories": [c for c in PRACTICE_CATEGORIES if c not in done],
        "srs_fluent": fluent,
        "perfect": len(done) == len(PRACTICE_CATEGORIES) and fluent,
    }

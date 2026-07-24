"""Practice stages Uno..Cinco: the 24-hour gate, the cap, and Perfect status.

Pure functions, injected clock — every assertion here is exact to the second.
"""
import datetime as dt

import pytest

from app.domain.practice_stages import (
    DEFAULT_STAGE_NAMES,
    FLUENT_SRS_STAGE,
    MAX_PRACTICE_STAGE,
    PRACTICE_CATEGORIES,
    STAGE_COOLDOWN,
    all_categories_complete,
    category_complete,
    clamp_stage,
    cooldown_active,
    cooldown_remaining,
    next_available_at,
    perfect_progress,
    qualifies_for_perfect,
    resolve_stage,
    stage_label,
)

NOW = dt.datetime(2026, 7, 22, 12, 0, tzinfo=dt.timezone.utc)


# --- progression ---------------------------------------------------------

def test_first_stage_needs_no_cooldown():
    out = resolve_stage(0, correct=True, stage_reached_at=None, now=NOW)
    assert out.stage_after == 1
    assert out.advanced and not out.held_by_cooldown
    assert out.reached_at == NOW
    assert out.next_available_at == NOW + STAGE_COOLDOWN


def test_wrong_answer_holds_the_stage():
    out = resolve_stage(2, correct=False, stage_reached_at=None, now=NOW)
    assert out.stage_after == 2
    assert not out.advanced
    assert out.held_by_wrong_answer
    assert out.reached_at is None


def test_wrong_answer_never_demotes():
    """Practice is low-stakes: it can only ever move a stage upward."""
    for stage in range(0, MAX_PRACTICE_STAGE + 1):
        out = resolve_stage(stage, correct=False, stage_reached_at=None, now=NOW)
        assert out.stage_after == stage


def test_second_stage_up_inside_24h_is_blocked():
    reached = NOW - dt.timedelta(hours=23, minutes=59)
    out = resolve_stage(1, correct=True, stage_reached_at=reached, now=NOW)
    assert out.stage_after == 1
    assert out.held_by_cooldown
    assert out.next_available_at == reached + STAGE_COOLDOWN


def test_stage_up_exactly_at_24h_is_allowed():
    reached = NOW - STAGE_COOLDOWN
    out = resolve_stage(1, correct=True, stage_reached_at=reached, now=NOW)
    assert out.stage_after == 2
    assert out.advanced and not out.held_by_cooldown


def test_cannot_grind_all_five_stages_in_one_session():
    """The point of the gate: five correct answers in a row is still Stage Uno."""
    stage, reached = 0, None
    for _ in range(5):
        out = resolve_stage(stage, correct=True, stage_reached_at=reached, now=NOW)
        stage = out.stage_after
        reached = out.reached_at or reached
    assert stage == 1


def test_five_days_of_practice_reaches_cinco():
    stage, reached = 0, None
    for day in range(5):
        moment = NOW + dt.timedelta(days=day)
        out = resolve_stage(stage, correct=True, stage_reached_at=reached, now=moment)
        stage = out.stage_after
        reached = out.reached_at or reached
    assert stage == MAX_PRACTICE_STAGE
    assert category_complete(stage)


def test_stage_caps_at_cinco():
    out = resolve_stage(
        MAX_PRACTICE_STAGE, correct=True,
        stage_reached_at=NOW - dt.timedelta(days=10), now=NOW,
    )
    assert out.stage_after == MAX_PRACTICE_STAGE
    assert out.complete
    assert not out.advanced
    assert out.next_available_at is None      # nothing left to wait for


def test_naive_timestamps_are_treated_as_utc():
    """The stage_reached_at column is naive; comparing it must not explode."""
    naive = (NOW - dt.timedelta(hours=1)).replace(tzinfo=None)
    out = resolve_stage(1, correct=True, stage_reached_at=naive, now=NOW)
    assert out.held_by_cooldown is True


def test_clamp_handles_bad_stored_values():
    assert clamp_stage(-3) == 0
    assert clamp_stage(99) == MAX_PRACTICE_STAGE
    assert clamp_stage(None) == 0


# --- cooldown reporting --------------------------------------------------

def test_cooldown_remaining_counts_down():
    reached = NOW - dt.timedelta(hours=20)
    assert cooldown_remaining(reached, NOW) == dt.timedelta(hours=4)
    assert cooldown_active(reached, NOW)


def test_cooldown_expired_reports_zero():
    reached = NOW - dt.timedelta(days=3)
    assert cooldown_remaining(reached, NOW) == dt.timedelta(0)
    assert not cooldown_active(reached, NOW)


def test_no_prior_stage_has_no_cooldown():
    assert next_available_at(None) is None
    assert not cooldown_active(None, NOW)


# --- naming --------------------------------------------------------------

@pytest.mark.parametrize(
    "stage,expected",
    [(0, "Not started"), (1, "Stage Uno"), (3, "Stage Tres"), (5, "Stage Cinco")],
)
def test_spanish_stage_labels(stage, expected):
    assert stage_label(stage, list(DEFAULT_STAGE_NAMES)) == expected


def test_labels_are_localised_per_language():
    tagalog = ["Isa", "Dalawa", "Tatlo", "Apat", "Lima"]
    assert stage_label(2, tagalog) == "Stage Dalawa"


def test_missing_names_fall_back_to_spanish():
    assert stage_label(4, None) == "Stage Cuatro"
    assert stage_label(4, []) == "Stage Cuatro"


# --- perfect status ------------------------------------------------------

def test_perfect_requires_every_category():
    stages = {"sentences": 5, "listening": 5, "speaking": 4}
    assert not all_categories_complete(stages)
    assert not qualifies_for_perfect(stages, FLUENT_SRS_STAGE)


def test_perfect_requires_fluent_srs():
    stages = dict.fromkeys(PRACTICE_CATEGORIES, 5)
    assert all_categories_complete(stages)
    assert not qualifies_for_perfect(stages, FLUENT_SRS_STAGE - 1)
    assert qualifies_for_perfect(stages, FLUENT_SRS_STAGE)


def test_missing_category_rows_count_as_zero():
    assert not all_categories_complete({"sentences": 5})


def test_perfect_progress_reports_what_is_left():
    out = perfect_progress({"sentences": 5, "listening": 2}, srs_stage=7)
    assert out["categories_complete"] == 1
    assert out["categories_total"] == 3
    assert out["remaining_categories"] == ["listening", "speaking"]
    assert out["srs_fluent"] is False
    assert out["perfect"] is False


def test_perfect_progress_when_everything_is_done():
    out = perfect_progress(dict.fromkeys(PRACTICE_CATEGORIES, 5), FLUENT_SRS_STAGE)
    assert out["perfect"] is True
    assert out["remaining_categories"] == []

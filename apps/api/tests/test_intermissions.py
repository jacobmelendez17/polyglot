"""Intermission triggers and the immersion unlock rule — pure functions."""
import pytest

from app.domain.immersion import (
    IMMERSION_UNLOCK_LEVEL,
    can_enable,
    immersion_unlocked,
    levels_remaining,
)
from app.domain.intermissions import (
    MAX_PER_EVENT,
    Candidate,
    TriggerContext,
    describe,
    matches,
    select_due,
)


def ctx(**kw) -> TriggerContext:
    base = {"event": "level_start", "level": 1, "lesson": None,
            "items_learned": 0, "highest_stage": 0}
    return TriggerContext(**{**base, **kw})


# --- level_start ----------------------------------------------------------

def test_level_start_fires_on_the_named_level():
    trigger = {"kind": "level_start", "level": 2}
    assert matches(trigger, ctx(event="level_start", level=2))
    assert not matches(trigger, ctx(event="level_start", level=1))


def test_level_start_without_a_level_fires_on_any():
    trigger = {"kind": "level_start"}
    assert matches(trigger, ctx(event="level_start", level=7))


def test_level_start_does_not_fire_on_other_events():
    trigger = {"kind": "level_start", "level": 1}
    assert not matches(trigger, ctx(event="lesson_complete", level=1))


# --- lesson_complete ------------------------------------------------------

def test_lesson_complete_matches_level_and_lesson():
    trigger = {"kind": "lesson_complete", "level": 1, "lesson": 3}
    assert matches(trigger, ctx(event="lesson_complete", level=1, lesson=3))
    assert not matches(trigger, ctx(event="lesson_complete", level=1, lesson=2))
    assert not matches(trigger, ctx(event="lesson_complete", level=2, lesson=3))


def test_lesson_complete_can_wildcard_the_lesson():
    trigger = {"kind": "lesson_complete", "level": 1}
    assert matches(trigger, ctx(event="lesson_complete", level=1, lesson=4))


# --- thresholds -----------------------------------------------------------

def test_items_learned_fires_at_or_above_the_threshold():
    trigger = {"kind": "items_learned", "count": 25}
    assert not matches(trigger, ctx(items_learned=24))
    assert matches(trigger, ctx(items_learned=25))
    assert matches(trigger, ctx(items_learned=200))


def test_threshold_triggers_fire_on_any_event():
    """"You have learned 25 words" is true whenever it is true."""
    trigger = {"kind": "items_learned", "count": 10}
    for event in ("level_start", "lesson_complete", "progress"):
        assert matches(trigger, ctx(event=event, items_learned=10))


def test_srs_stage_fires_at_or_above():
    trigger = {"kind": "srs_stage", "stage": 5}
    assert not matches(trigger, ctx(highest_stage=4))
    assert matches(trigger, ctx(highest_stage=5))


def test_threshold_without_a_number_never_fires():
    assert not matches({"kind": "items_learned"}, ctx(items_learned=999))
    assert not matches({"kind": "srs_stage"}, ctx(highest_stage=9))


# --- malformed input ------------------------------------------------------

@pytest.mark.parametrize("trigger", [
    None, 42, "level_start", [], {}, {"kind": "nonsense"}, {"kind": None},
])
def test_a_malformed_trigger_is_invisible_not_fatal(trigger):
    """A bad row written by an admin should mean 'this one doesn't show'."""
    assert matches(trigger, ctx()) is False


def test_numeric_strings_are_tolerated():
    assert matches({"kind": "level_start", "level": "2"},
                   ctx(event="level_start", level=2))


def test_booleans_are_not_treated_as_numbers():
    assert not matches({"kind": "items_learned", "count": True}, ctx(items_learned=1))


# --- selection ------------------------------------------------------------

def make(id_: str, trigger: dict, title: str = "t", order: int = 0) -> Candidate:
    return Candidate(id=id_, trigger=trigger, title=title, order_hint=order)


def test_seen_intermissions_never_come_back():
    """They are readings, not reviews."""
    pool = [make("a", {"kind": "level_start", "level": 1})]
    assert select_due(pool, ctx(), seen_ids={"a"}) == []
    assert len(select_due(pool, ctx(), seen_ids=set())) == 1


def test_selection_is_capped_so_the_learner_is_not_buried():
    pool = [make(str(i), {"kind": "level_start", "level": 1}) for i in range(10)]
    assert len(select_due(pool, ctx(), seen_ids=set())) == MAX_PER_EVENT


def test_selection_respects_the_order_hint():
    pool = [
        make("b", {"kind": "level_start", "level": 1}, title="b", order=2),
        make("a", {"kind": "level_start", "level": 1}, title="a", order=1),
    ]
    assert [c.id for c in select_due(pool, ctx(), seen_ids=set())] == ["a", "b"]


def test_selection_falls_back_to_title_for_a_stable_order():
    pool = [
        make("z", {"kind": "level_start", "level": 1}, title="zebra"),
        make("a", {"kind": "level_start", "level": 1}, title="apple"),
    ]
    assert [c.id for c in select_due(pool, ctx(), seen_ids=set())] == ["a", "z"]


def test_a_limit_of_zero_returns_nothing():
    pool = [make("a", {"kind": "level_start", "level": 1})]
    assert select_due(pool, ctx(), seen_ids=set(), limit=0) == []


# --- descriptions ---------------------------------------------------------

def test_descriptions_read_as_english():
    assert describe({"kind": "level_start", "level": 3}) == "starting level 3"
    assert describe({"kind": "items_learned", "count": 25}) == "after learning 25 items"
    assert "lesson 2" in describe({"kind": "lesson_complete", "level": 1, "lesson": 2})


def test_a_malformed_trigger_describes_itself_as_broken():
    assert "malformed" in describe("nope")
    assert "unknown" in describe({"kind": "whatever"})


# --- immersion ------------------------------------------------------------

def test_immersion_unlocks_at_level_ten():
    assert not immersion_unlocked(IMMERSION_UNLOCK_LEVEL - 1)
    assert immersion_unlocked(IMMERSION_UNLOCK_LEVEL)
    assert immersion_unlocked(IMMERSION_UNLOCK_LEVEL + 5)


def test_levels_remaining_counts_down_and_stops_at_zero():
    assert levels_remaining(0) == IMMERSION_UNLOCK_LEVEL
    assert levels_remaining(IMMERSION_UNLOCK_LEVEL) == 0
    assert levels_remaining(IMMERSION_UNLOCK_LEVEL + 3) == 0


def test_turning_immersion_off_never_requires_the_unlock():
    """If the rule ever changed, someone already in immersion must be able out."""
    assert can_enable(0, requested=False) is True
    assert can_enable(0, requested=True) is False
    assert can_enable(IMMERSION_UNLOCK_LEVEL, requested=True) is True

"""Unit tests for the pure deck-unlock logic (slice 43)."""
from app.domain.deck_unlock import (
    BUILTIN_DECKS,
    FAMILIAR_STAGE,
    evaluate,
    unlockable_categories,
)


def _by_id(states):
    return {s.id: s for s in states}


def test_always_on_decks_unlocked_with_no_progress():
    states = _by_id(evaluate({}))
    for always in ("vocabulary", "grammar", "intermissions"):
        assert states[always].unlocked is True
        assert states[always].threshold == 0
        assert states[always].need == 0


def test_verbs_deck_unlocks_at_twenty():
    assert _by_id(evaluate({"pos:verb": 19}))["verbs"].unlocked is False
    assert _by_id(evaluate({"pos:verb": 19}))["verbs"].need == 1
    assert _by_id(evaluate({"pos:verb": 20}))["verbs"].unlocked is True
    assert _by_id(evaluate({"pos:verb": 25}))["verbs"].need == 0


def test_irregular_verbs_deck_unlocks_at_five():
    assert _by_id(evaluate({"regularity:irregular": 4}))["irregular_verbs"].unlocked is False
    s = _by_id(evaluate({"regularity:irregular": 5}))["irregular_verbs"]
    assert s.unlocked is True and s.have == 5 and s.need == 0


def test_progress_is_reported_for_locked_decks():
    s = _by_id(evaluate({"pos:noun": 12}))["nouns"]
    assert s.unlocked is False
    assert s.have == 12
    assert s.need == s.threshold - 12


def test_unrelated_counts_do_not_unlock_a_deck():
    # nouns shouldn't unlock the verbs deck
    assert _by_id(evaluate({"pos:noun": 100}))["verbs"].unlocked is False


def test_unlockable_categories_excludes_always_on():
    cats = unlockable_categories()
    assert "" not in cats
    assert "pos:verb" in cats and "regularity:irregular" in cats


def test_catalog_ids_are_unique():
    ids = [d.id for d in BUILTIN_DECKS]
    assert len(ids) == len(set(ids))


def test_familiar_stage_constant():
    assert FAMILIAR_STAGE == 5

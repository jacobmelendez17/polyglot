"""Feature-unlock schedule — the pure rules."""
from app.domain.feature_unlock import (
    FEATURE_UNLOCK,
    feature_states,
    is_unlocked,
    unlock_level,
    unlocked_features,
)


def test_reviews_and_reading_available_from_level_one():
    assert is_unlocked("reviews", completed_levels=1)
    assert is_unlocked("reading", completed_levels=1)
    assert not is_unlocked("reviews", completed_levels=0)


def test_listening_and_immersion_gates():
    assert not is_unlocked("listening", completed_levels=1)
    assert is_unlocked("listening", completed_levels=2)
    assert not is_unlocked("immersion", completed_levels=9)
    assert is_unlocked("immersion", completed_levels=10)


def test_unknown_feature_is_locked_forever():
    assert not is_unlocked("time_travel", completed_levels=999)
    assert unlock_level("time_travel") == 10**6


def test_unlocked_set_grows_monotonically():
    assert unlocked_features(1) <= unlocked_features(3) <= unlocked_features(10)
    assert "reviews" in unlocked_features(1)
    assert "listening" not in unlocked_features(1)
    assert unlocked_features(10) == set(FEATURE_UNLOCK)  # everything open by level 10


def test_feature_states_ordered_by_unlock_level():
    states = feature_states(2)
    levels = [s["unlock_level"] for s in states]
    assert levels == sorted(levels)


def test_feature_states_levels_remaining():
    by = {s["feature"]: s for s in feature_states(2)}
    assert by["reviews"]["unlocked"] and by["reviews"]["levels_remaining"] == 0
    assert not by["speaking"]["unlocked"] and by["speaking"]["levels_remaining"] == 1
    assert by["testing_cefr"]["levels_remaining"] == 2

"""SRS engine: the full stage x wrong-count matrix, per PLANNING §10."""
import datetime as dt

import pytest

from app.domain.srs import (
    INTERVALS,
    MAX_STAGE,
    MIN_STAGE,
    Stage,
    apply_srs,
    incorrect_adjustment_count,
    is_fluent,
    next_review_at,
    penalty_factor,
    prompt_kind_for_stage,
    resolve_pair,
)

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)


def test_clean_pair_promotes_one_stage():
    for stage in range(1, 9):
        assert apply_srs(stage, 0) == stage + 1


def test_promotion_caps_at_fluent():
    assert apply_srs(9, 0) == 9


def test_demotion_floors_at_beginner_1():
    assert apply_srs(1, 2) == 1
    assert apply_srs(1, 8) == 1
    assert apply_srs(2, 6) == 1


def test_penalty_factor_boundary_at_familiar_1():
    for s in (1, 2, 3, 4):
        assert penalty_factor(s) == 1
    for s in (5, 6, 7, 8, 9):
        assert penalty_factor(s) == 2


def test_incorrect_adjustment_is_ceil_half():
    assert incorrect_adjustment_count(0) == 0
    assert incorrect_adjustment_count(1) == 1
    assert incorrect_adjustment_count(2) == 1
    assert incorrect_adjustment_count(3) == 2
    assert incorrect_adjustment_count(4) == 2


@pytest.mark.parametrize(
    "stage,wrong,expected",
    [
        # below Familiar: penalty 1
        (4, 1, 3), (4, 2, 3), (4, 3, 2), (4, 4, 2),
        # at/above Familiar: penalty 2
        (5, 1, 3), (5, 2, 3), (6, 2, 4), (7, 2, 5),
        (8, 4, 4),          # ceil(4/2)=2 * 2 = 4 -> 8-4
        (9, 1, 7),          # fluent demotes too: ceil(1/2)=1 * 2 = 2 -> 9-2
    ],
)
def test_demotion_matrix(stage, wrong, expected):
    assert apply_srs(stage, wrong) == expected


def test_full_matrix_never_escapes_bounds():
    for stage in range(1, 10):
        for wrong in range(0, 9):
            out = apply_srs(stage, wrong)
            assert MIN_STAGE <= out <= MAX_STAGE


def test_invalid_inputs_rejected():
    with pytest.raises(ValueError):
        apply_srs(0, 0)
    with pytest.raises(ValueError):
        apply_srs(10, 0)
    with pytest.raises(ValueError):
        apply_srs(3, -1)


def test_intervals_match_spec():
    assert INTERVALS[1] == dt.timedelta(hours=4)
    assert INTERVALS[2] == dt.timedelta(hours=8)
    assert INTERVALS[3] == dt.timedelta(days=1)
    assert INTERVALS[4] == dt.timedelta(days=2)
    assert INTERVALS[5] == dt.timedelta(weeks=1)
    assert INTERVALS[6] == dt.timedelta(weeks=2)
    assert INTERVALS[7] == dt.timedelta(days=30)
    assert INTERVALS[8] == dt.timedelta(days=120)


def test_fluent_leaves_the_queue():
    assert next_review_at(int(Stage.fluent), NOW) is None
    assert is_fluent(9)
    assert not is_fluent(8)


def test_leech_items_review_sooner():
    normal = next_review_at(3, NOW)
    leeched = next_review_at(3, NOW, is_leech=True)
    assert leeched < normal
    assert leeched - NOW == dt.timedelta(hours=12)  # half of 1 day


def test_resolve_pair_reports_outcome():
    good = resolve_pair(stage_before=3, wrong_answer_count=0, now=NOW)
    assert good.promoted and good.stage_after == 4 and good.penalty == 0
    bad = resolve_pair(stage_before=6, wrong_answer_count=1, now=NOW)
    assert not bad.promoted and bad.stage_after == 4 and bad.penalty == 2


def test_prompt_kind_by_stage():
    assert prompt_kind_for_stage(1) == "translation"
    assert prompt_kind_for_stage(4) == "translation"
    assert prompt_kind_for_stage(5) == "cloze_short"
    assert prompt_kind_for_stage(6) == "cloze_short"
    assert prompt_kind_for_stage(7) == "cloze_long"
    assert prompt_kind_for_stage(8) == "cloze_long"

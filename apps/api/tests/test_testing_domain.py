"""Testing maps — the pure rules."""
import pytest

from app.domain.testing import (
    MAPS,
    is_correct,
    is_map,
    percentage,
    score_from_answers,
    validate_choice,
)


def test_maps():
    assert MAPS == ("cefr", "app", "life")
    assert is_map("app") and not is_map("nope")


def test_validate_choice_accepts_in_range():
    validate_choice(0, 4)
    validate_choice(3, 4)


@pytest.mark.parametrize("chosen,n", [(-1, 4), (4, 4), (5, 4)])
def test_validate_choice_rejects_out_of_range(chosen, n):
    with pytest.raises(ValueError):
        validate_choice(chosen, n)


def test_validate_choice_rejects_bool_and_str():
    # bool is an int subclass — must not sneak through
    with pytest.raises(ValueError):
        validate_choice(True, 4)
    with pytest.raises(ValueError):
        validate_choice("2", 4)  # type: ignore[arg-type]


def test_grading():
    assert is_correct(2, 2) is True
    assert is_correct(1, 2) is False


def test_scoring():
    answers = [{"correct": True}, {"correct": False}, {"correct": True}]
    assert score_from_answers(answers) == (2, 3)
    assert score_from_answers([]) == (0, 0)


def test_percentage():
    assert percentage(2, 3) == 67
    assert percentage(3, 3) == 100
    assert percentage(0, 0) == 0

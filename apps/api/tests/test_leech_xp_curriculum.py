"""Leech scoring, XP rules, and curriculum planning."""
import math

import pytest

from app.domain.curriculum import (
    PlannedItem,
    level_unlock_progress,
    plan_level,
)
from app.domain.leech import (
    CRITICAL_THRESHOLD,
    WATCH_THRESHOLD,
    WINDOW,
    LeechState,
    is_leech,
    leech_score,
    leech_state,
    push_result,
)
from app.domain.xp import XP_TABLE, XpKind, lesson_xp, review_xp, xp_for
from app.models.enums import CurriculumMode

# --- leech ---------------------------------------------------------------

def test_no_history_is_zero():
    assert leech_score([]) == 0.0
    assert leech_state(0.0) is LeechState.none


def test_all_correct_is_zero():
    assert leech_score([0] * 10) == 0.0


def test_all_wrong_reaches_leech():
    score = leech_score([1] * 10)
    assert score == 1.0
    assert leech_state(score) is LeechState.leech


def test_repeatedly_missed_reaches_critical():
    # 2 wrong answers per review weights above 1.0 (resolves PLANNING R-05)
    score = leech_score([2] * 10)
    assert score >= CRITICAL_THRESHOLD
    assert leech_state(score) is LeechState.critical


def test_recent_mistakes_weigh_more_than_old():
    old_mistakes = leech_score([1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    new_mistakes = leech_score([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    assert new_mistakes > old_mistakes


def test_only_last_ten_reviews_count():
    buf: list[int] = []
    for _ in range(25):
        buf = push_result(buf, 1)
    assert len(buf) == WINDOW
    # a long-ago streak of mistakes fully decays out of the window
    buf = [1] * 10
    for _ in range(10):
        buf = push_result(buf, 0)
    assert leech_score(buf) == 0.0


def test_threshold_boundaries():
    assert leech_state(WATCH_THRESHOLD) is LeechState.watch
    assert leech_state(0.79) is LeechState.none
    assert leech_state(1.0) is LeechState.leech
    assert leech_state(CRITICAL_THRESHOLD) is LeechState.critical


def test_user_threshold_is_respected():
    # a stricter threshold flags leeches sooner
    assert leech_state(0.9, threshold=0.85) is LeechState.leech
    assert leech_state(0.9, threshold=1.2) is LeechState.watch


def test_only_leech_and_critical_shorten_intervals():
    assert not is_leech(LeechState.none)
    assert not is_leech(LeechState.watch)
    assert is_leech(LeechState.leech)
    assert is_leech(LeechState.critical)


# --- XP ------------------------------------------------------------------

def test_xp_table_matches_spec():
    assert XP_TABLE[XpKind.grammar_lesson] == 60
    assert XP_TABLE[XpKind.vocab_lesson] == 50
    assert XP_TABLE[XpKind.grammar_review] == 20
    assert XP_TABLE[XpKind.vocab_review] == 10
    assert XP_TABLE[XpKind.journal] == 500
    assert XP_TABLE[XpKind.test_correct] == 20
    assert XP_TABLE[XpKind.translation_phrase] == 100
    assert XP_TABLE[XpKind.translation_sentence] == 200
    assert XP_TABLE[XpKind.translation_complex] == 300


def test_spec_example_five_grammar_lessons_is_300():
    assert lesson_xp(grammar_items=5) == 300


def test_spec_example_mixed_lesson_is_320():
    # "2 grammar items and 4 vocab items in a lesson -> 120+200 = 320"
    assert lesson_xp(grammar_items=2, vocab_items=4) == 320


def test_review_xp_follows_the_table():
    # NOTE: the spec's worked example ("30 vocab + 3 grammar = 630") contradicts
    # its own XP table, which gives 30*10 + 3*20 = 360. The table is implemented
    # as the source of truth; see docs/PLANNING.md open question.
    assert review_xp(vocab_items=30, grammar_items=3) == 360


def test_zero_counts_award_nothing():
    assert lesson_xp() == 0
    assert review_xp() == 0
    with pytest.raises(ValueError):
        xp_for(XpKind.journal, -1)


# --- curriculum ----------------------------------------------------------

def _level(vocab_n=48, grammar_n=12):
    v = [PlannedItem("vocabulary", f"v{i}", batch=(i // 12) + 1) for i in range(vocab_n)]
    g = [PlannedItem("grammar", f"g{i}") for i in range(grammar_n)]
    return v, g


@pytest.mark.parametrize("mode", list(CurriculumMode))
def test_no_items_are_lost_or_duplicated(mode):
    v, g = _level()
    lessons = plan_level(vocab=v, grammar=g, mode=mode, seed=3)
    seen = [it.item_id for l in lessons for it in l.items]
    assert len(seen) == 60
    assert len(set(seen)) == 60


def test_default_mode_disperses_grammar_across_themed_lessons():
    v, g = _level()
    lessons = plan_level(vocab=v, grammar=g, mode=CurriculumMode.default_dispersed, seed=1)
    assert len(lessons) == 4
    for l in lessons:
        kinds = {it.item_type for it in l.items}
        assert kinds == {"vocabulary", "grammar"}   # both present in every lesson


def test_grammar_batch_mode_isolates_grammar():
    v, g = _level()
    lessons = plan_level(vocab=v, grammar=g, mode=CurriculumMode.grammar_batch, seed=1)
    assert len(lessons) == 5
    for l in lessons[:4]:
        assert {it.item_type for it in l.items} == {"vocabulary"}
    assert {it.item_type for it in lessons[4].items} == {"grammar"}


def test_fully_dispersed_is_seed_stable():
    v, g = _level()
    a = plan_level(vocab=v, grammar=g, mode=CurriculumMode.fully_dispersed, seed=99)
    b = plan_level(vocab=v, grammar=g, mode=CurriculumMode.fully_dispersed, seed=99)
    assert [[i.item_id for i in l.items] for l in a] == [[i.item_id for i in l.items] for l in b]


def test_level_six_shape_still_plans(real_world="36 words, 3 batches"):
    v, g = _level(vocab_n=36, grammar_n=0)
    lessons = plan_level(vocab=v, grammar=g, mode=CurriculumMode.default_dispersed, seed=1)
    assert sum(len(l.items) for l in lessons) == 36


def test_unlock_requires_all_grammar_and_three_quarters_vocab():
    ok, prog = level_unlock_progress(grammar_stages=[5] * 12, vocab_stages=[5] * 36 + [1] * 12)
    assert ok
    assert prog["vocab_required"] == 36

    not_ok, _ = level_unlock_progress(grammar_stages=[5] * 11 + [4], vocab_stages=[5] * 48)
    assert not not_ok

    not_enough_vocab, _ = level_unlock_progress(
        grammar_stages=[5] * 12, vocab_stages=[5] * 35 + [1] * 13
    )
    assert not not_enough_vocab


def test_unlock_uses_actual_counts_not_assumed_48():
    # Level 6 really has 36 words; 3/4 of 36 = 27
    ok, prog = level_unlock_progress(grammar_stages=[], vocab_stages=[5] * 27 + [1] * 9)
    assert prog["vocab_required"] == 27
    assert ok


def test_unlock_rounds_up():
    _, prog = level_unlock_progress(grammar_stages=[], vocab_stages=[1] * 10)
    assert prog["vocab_required"] == math.ceil(10 * 0.75)

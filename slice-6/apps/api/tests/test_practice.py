"""Practice domain logic: weak-item selection, cloze, conjugation, stages."""

from app.domain.practice import (
    MAX_PRACTICE_STAGE,
    PracticeCandidate,
    PracticeMode,
    advance_practice_stage,
    available_conjugation_cells,
    is_perfect,
    make_cloze,
    make_conjugation,
    select_practice_pool,
    select_weak_items,
    weak_item_weight,
)


def _c(id, stage=3, leech=0.0, wrong=0, has_example=False, is_verb=False):
    return PracticeCandidate("vocabulary", id, stage, leech, wrong, has_example, is_verb)


def test_weak_weight_prioritizes_leeches():
    heavy = _c("a", leech=1.5, wrong=4)
    light = _c("b", leech=0.0, wrong=0)
    assert weak_item_weight(heavy) > weak_item_weight(light)


def test_select_weak_items_orders_by_need():
    cands = [_c("fine", leech=0), _c("bad", leech=1.5, wrong=5), _c("meh", leech=0.8, wrong=1)]
    picked = select_weak_items(cands, limit=2, seed=1)
    assert picked[0].item_id == "bad"
    assert len(picked) == 2


def test_select_weak_items_is_seed_stable():
    cands = [_c(str(i), leech=1.0, wrong=2) for i in range(10)]
    a = [c.item_id for c in select_weak_items(cands, seed=7)]
    b = [c.item_id for c in select_weak_items(cands, seed=7)]
    assert a == b


def test_weak_items_falls_back_when_nobody_is_weak():
    cands = [_c("a"), _c("b")]  # zero leech, zero mistakes
    picked = select_weak_items(cands, limit=5, seed=1)
    assert len(picked) == 2   # still returns something to practice


def test_fill_blank_pool_requires_examples():
    cands = [_c("has", has_example=True), _c("none", has_example=False)]
    pool = select_practice_pool(cands, PracticeMode.fill_blank, seed=1)
    assert [c.item_id for c in pool] == ["has"]


def test_conjugation_pool_requires_verbs():
    cands = [_c("verb", is_verb=True), _c("noun", is_verb=False)]
    pool = select_practice_pool(cands, PracticeMode.conjugation, seed=1)
    assert [c.item_id for c in pool] == ["verb"]


def test_make_cloze_blanks_the_word():
    cz = make_cloze("Yo tengo un carro rojo", "carro", "car")
    assert cz is not None
    assert "_____" in cz.sentence_with_blank
    assert "carro" not in cz.sentence_with_blank
    assert cz.answer == "carro"


def test_make_cloze_is_case_insensitive_and_whole_word():
    assert make_cloze("Carro nuevo", "carro", "car") is not None
    # substring should not match ("carro" inside "carroza")
    assert make_cloze("La carroza", "carro", "car") is None


def test_make_cloze_returns_none_when_absent():
    assert make_cloze("no target here", "xyz", "t") is None
    assert make_cloze("", "x", "t") is None


def test_make_conjugation_pulls_the_form():
    conj = {"present": {"yo": "hablo", "tú": "hablas"}}
    cj = make_conjugation("hablar", conj, tense="present", person="yo")
    assert cj is not None and cj.answer == "hablo"
    assert make_conjugation("hablar", conj, tense="present", person="nosotros") is None


def test_available_conjugation_cells():
    conj = {"present": {"yo": "hablo", "tú": ""}, "future": {"yo": "hablaré"}}
    cells = available_conjugation_cells(conj)
    assert ("present", "yo") in cells
    assert ("future", "yo") in cells
    assert ("present", "tú") not in cells   # empty form excluded


def test_practice_stage_advances_only_on_correct():
    assert advance_practice_stage(2, correct=True) == 3
    assert advance_practice_stage(2, correct=False) == 2


def test_practice_stage_caps_at_cinco():
    assert advance_practice_stage(5, correct=True) == MAX_PRACTICE_STAGE
    assert is_perfect(5)
    assert not is_perfect(4)

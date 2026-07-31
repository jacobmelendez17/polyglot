"""Utterance scoring — the pure rule."""
from app.domain.speech import PASS_THRESHOLD, score_utterance


def test_exact_match_is_perfect():
    r = score_utterance("me gusta el café", "me gusta el café")
    assert r.score == 100 and r.passed
    assert all(w.matched for w in r.words)
    assert r.missed == [] and r.extra == []


def test_accents_are_ignored():
    # consumer STT routinely drops accents
    r = score_utterance("el cafe esta caliente", "el café está caliente")
    assert r.score == 100 and r.passed


def test_case_and_punctuation_ignored():
    assert score_utterance("¡Hola, Mundo!", "hola mundo").score == 100


def test_empty_transcript_scores_zero():
    r = score_utterance("", "hola mundo")
    assert r.score == 0 and not r.passed
    assert r.missed == ["hola", "mundo"]
    assert all(not w.matched for w in r.words)


def test_one_missing_word_is_partial():
    r = score_utterance("gato negro", "el gato negro")
    assert r.score == 80  # 2*2/(3+2)
    assert [w.matched for w in r.words] == [False, True, True]
    assert r.missed == ["el"]


def test_filler_words_are_penalized():
    r = score_utterance("eh me gusta pues el café pues", "me gusta el café")
    assert r.score == 73 and not r.passed
    assert set(r.extra) == {"eh", "pues"}


def test_accepted_variant_can_win():
    r = score_utterance("ustedes", "vosotros", ["ustedes"])
    assert r.score == 100 and r.expected == "ustedes"


def test_wrong_word_scores_zero():
    r = score_utterance("perro", "gato")
    assert r.score == 0 and not r.passed


def test_threshold_is_configurable():
    r = score_utterance("gato negro", "el gato negro", threshold=90)
    assert r.score == 80 and not r.passed


def test_default_threshold_value():
    assert PASS_THRESHOLD == 80

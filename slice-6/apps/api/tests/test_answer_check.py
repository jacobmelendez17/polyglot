"""Answer checking: accents, typos, synonyms, rejected answers (PLANNING §8)."""

from app.domain.answer_check import (
    CheckMode,
    ExpectedAnswers,
    check_answer,
    damerau_levenshtein,
    expected_from_item,
)


def test_exact_match():
    e = ExpectedAnswers(primary="la casa")
    assert check_answer("la casa", e).correct


def test_case_and_space_insensitive():
    e = ExpectedAnswers(primary="la casa")
    assert check_answer("  La   Casa  ", e).correct


def test_punctuation_and_inverted_marks_ignored():
    e = ExpectedAnswers(primary="cómo estás")
    assert check_answer("¿Cómo estás?", e).correct


def test_accent_matters_but_is_forgiven_with_warning_in_normal_mode():
    e = ExpectedAnswers(primary="está")
    r = check_answer("esta", e, mode=CheckMode.normal)
    assert r.correct
    assert "missing_accent" in r.warning_values


def test_accent_required_in_strict_and_test_modes():
    e = ExpectedAnswers(primary="está")
    assert not check_answer("esta", e, mode=CheckMode.strict).correct
    assert not check_answer("esta", e, mode=CheckMode.test).correct


def test_rejected_answer_fails_with_message():
    e = ExpectedAnswers(primary="ser", rejected=("estar",))
    r = check_answer("estar", e)
    assert not r.correct
    assert r.message


def test_stored_synonym_accepted():
    e = ExpectedAnswers(primary="carro", synonyms=("coche", "auto"))
    r = check_answer("coche", e)
    assert r.correct and r.synonym_matched
    assert "synonym" in r.warning_values


def test_user_synonym_only_when_enabled():
    e = ExpectedAnswers(primary="carro", user_synonyms=("nave",))
    assert not check_answer("nave", e).correct
    r = check_answer("nave", e, accept_user_synonyms=True)
    assert r.correct and r.synonym_matched


def test_transposed_letters_pass():
    # spec: "a couple letters are swapped" should pass
    e = ExpectedAnswers(primary="abuela")
    r = check_answer("abeula", e)
    assert r.correct and r.typo_forgiven


def test_one_or_two_missing_letters_pass():
    e = ExpectedAnswers(primary="biblioteca")
    assert check_answer("bibloteca", e).correct     # 1 missing
    assert check_answer("bibloteca", e).typo_forgiven
    assert check_answer("bibliotec", e).correct     # 1 missing at end


def test_typos_rejected_in_strict_mode():
    e = ExpectedAnswers(primary="abuela")
    assert not check_answer("abeula", e, mode=CheckMode.strict).correct


def test_short_words_are_not_over_forgiven():
    # "no" must never pass for "si" — they are different answers
    assert not check_answer("no", ExpectedAnswers(primary="si")).correct
    assert not check_answer("mas", ExpectedAnswers(primary="más"), mode=CheckMode.strict).correct


def test_wrong_answer_is_wrong():
    e = ExpectedAnswers(primary="biblioteca")
    assert not check_answer("elefante", e).correct


def test_empty_answer_is_wrong():
    assert not check_answer("", ExpectedAnswers(primary="casa")).correct
    assert not check_answer("   ", ExpectedAnswers(primary="casa")).correct


def test_accepted_answers_alternatives():
    e = ExpectedAnswers(primary="grandmother", accepted=("grandma", "granny"))
    assert check_answer("grandma", e).correct
    assert check_answer("granny", e).correct


def test_normal_mode_allows_up_to_two_edits():
    e = ExpectedAnswers(primary="biblioteca")
    assert check_answer("bibiotca", e, mode=CheckMode.normal).correct   # distance 2


def test_practice_mode_more_forgiving_than_normal():
    # distance 3: beyond normal tolerance, within practice tolerance
    e = ExpectedAnswers(primary="biblioteca")
    assert not check_answer("bibiotc", e, mode=CheckMode.normal).correct
    assert check_answer("bibiotc", e, mode=CheckMode.practice).correct


def test_allow_cheating_widens_tolerance():
    e = ExpectedAnswers(primary="biblioteca")
    assert check_answer("bibiotc", e, allow_cheating=True).correct


def test_damerau_levenshtein_basics():
    assert damerau_levenshtein("casa", "casa") == 0
    assert damerau_levenshtein("casa", "cosa") == 1     # substitution
    assert damerau_levenshtein("casa", "caa") == 1      # deletion
    assert damerau_levenshtein("abuela", "abeula") == 1  # transposition
    assert damerau_levenshtein("", "abc") == 3


def test_expected_from_item_handles_both_json_shapes():
    e = expected_from_item(
        primary="casa",
        accepted=["home", {"text": "house"}],
        rejected=[{"answer": "car"}],
    )
    assert "home" in e.accepted and "house" in e.accepted
    assert "car" in e.rejected

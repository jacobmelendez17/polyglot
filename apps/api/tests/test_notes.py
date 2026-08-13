"""Unit tests for the pure notes validator (slice 44)."""
import pytest

from app.domain.notes import MAX_NOTE_WORDS, NoteError, count_words, validate_note


def test_count_words():
    assert count_words("") == 0
    assert count_words("   ") == 0
    assert count_words("hola mundo") == 2
    assert count_words("hola   mundo\n\ntest") == 3


def test_validate_trims_and_allows_empty():
    assert validate_note("  hola  ") == "hola"
    assert validate_note("") == ""
    assert validate_note("   ") == ""


def test_validate_allows_exactly_the_limit():
    words = " ".join(["w"] * MAX_NOTE_WORDS)
    assert validate_note(words) == words


def test_validate_rejects_over_word_limit():
    with pytest.raises(NoteError) as e:
        validate_note(" ".join(["w"] * (MAX_NOTE_WORDS + 1)))
    assert e.value.code == "too_many_words"


def test_validate_rejects_overlong_blob():
    with pytest.raises(NoteError) as e:
        validate_note("x" * 4001)
    assert e.value.code == "too_long"

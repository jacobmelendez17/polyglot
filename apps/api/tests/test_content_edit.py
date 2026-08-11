"""Unit tests for the pure curriculum-editor validation (slice 39)."""
import pytest

from app.domain.content_edit import (
    EditError,
    MAX_BATCH,
    MAX_LEVEL,
    normalize_article_gender,
    validate_batch,
    validate_level,
    validate_term,
)


def test_level_bounds():
    assert validate_level(1) == 1
    assert validate_level(MAX_LEVEL) == MAX_LEVEL
    for bad in (0, -3, MAX_LEVEL + 1):
        with pytest.raises(EditError) as e:
            validate_level(bad)
        assert e.value.code == "bad_level"


def test_batch_bounds():
    assert validate_batch(1) == 1
    assert validate_batch(MAX_BATCH) == MAX_BATCH
    for bad in (0, 5, -1):
        with pytest.raises(EditError) as e:
            validate_batch(bad)
        assert e.value.code == "bad_batch"


def test_term_required_and_trimmed():
    assert validate_term("  gato ") == "gato"
    with pytest.raises(EditError) as e:
        validate_term("   ")
    assert e.value.code == "empty_term"


def test_article_only_on_nouns():
    # Noun keeps its article/gender.
    assert normalize_article_gender("noun", "el", "masculine") == ("el", "masculine")
    # Verb (or anything non-noun) is coerced to none/none, not rejected.
    assert normalize_article_gender("verb", "el", "masculine") == ("none", "none")
    assert normalize_article_gender("adjective", "la", "feminine") == ("none", "none")


def test_article_and_gender_enum_membership():
    with pytest.raises(EditError) as e:
        normalize_article_gender("noun", "das", "masculine")
    assert e.value.code == "bad_article"
    with pytest.raises(EditError) as e:
        normalize_article_gender("noun", "el", "androgynous")
    assert e.value.code == "bad_gender"


def test_blank_article_gender_default_to_none():
    assert normalize_article_gender("noun", "", "") == ("none", "none")

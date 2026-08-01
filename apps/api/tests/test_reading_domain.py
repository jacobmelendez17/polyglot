"""Reading rules — annotation validation and the visibility gate."""
import pytest

from app.domain.reading import (
    can_view_text,
    excerpt,
    extract_quote,
    normalize_word,
    validate_annotation,
)


def test_normalize_word():
    assert normalize_word("  Café!! ") == "cafe"
    assert normalize_word("niño,") == "nino"
    assert normalize_word("") == ""


def test_visibility_gate():
    assert can_view_text(status="published", deleted=False, is_editor=False) is True
    # soft-deleted is hidden from the public even if published
    assert can_view_text(status="published", deleted=True, is_editor=False) is False
    # drafts/archived only for editors
    assert can_view_text(status="draft", deleted=False, is_editor=False) is False
    assert can_view_text(status="draft", deleted=False, is_editor=True) is True
    assert can_view_text(status="archived", deleted=False, is_editor=True) is True


def test_validate_annotation_accepts_valid_ranges():
    validate_annotation(22, 0, 5)
    validate_annotation(22, 6, 22)  # up to the end


@pytest.mark.parametrize("start,end", [(-1, 5), (5, 5), (6, 5), (0, 23), (22, 23)])
def test_validate_annotation_rejects_bad_ranges(start, end):
    with pytest.raises(ValueError):
        validate_annotation(22, start, end)


def test_validate_annotation_requires_integers():
    with pytest.raises(ValueError):
        validate_annotation(22, "0", 5)  # type: ignore[arg-type]


def test_quote_comes_from_the_server_body():
    body = "Había una vez un gato."
    assert extract_quote(body, 0, 5) == "Había"
    assert extract_quote(body, 14, 21) == "un gato"


def test_excerpt():
    assert excerpt("short") == "short"
    assert excerpt("a" * 300, n=10).endswith("…")

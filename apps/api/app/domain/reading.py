"""Reading resource — pure rules (spec §7).

The reading resource lets learners read short texts and annotate, translate, and
dissect them. Two things here are worth isolating as pure, tested functions: the
annotation-range validation (an annotation's character offsets must land inside
the text, or a client could store a range that points nowhere) and the visibility
gate (drafts are for editors; only published, non-deleted texts are public). Word
normalization backs tap-to-translate lookups against the vocabulary table.
"""
from __future__ import annotations

import unicodedata


def normalize_word(word: str) -> str:
    """Lower-case, strip accents and surrounding punctuation — the same shape used
    for vocabulary `normalized_term`, so a tapped word can be matched."""
    text = unicodedata.normalize("NFD", (word or "").strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c for c in text if c.isalnum() or c.isspace())
    return " ".join(text.split())


def can_view_text(*, status: str, deleted: bool, is_editor: bool) -> bool:
    """Published, non-deleted texts are public; everything else (draft, in_review,
    archived, soft-deleted) is visible only to content editors."""
    if status == "published" and not deleted:
        return True
    return is_editor


def validate_annotation(body_len: int, start: int, end: int) -> None:
    """A highlight must be a real, non-empty span inside the text.

    Raises ValueError otherwise — the server extracts the stored quote from its own
    copy of the body using these offsets, so an out-of-range span must be rejected
    before it's trusted.
    """
    if not isinstance(start, int) or not isinstance(end, int):
        raise ValueError("Offsets must be integers.")
    if start < 0 or end <= start or end > body_len:
        raise ValueError("Highlight is out of range.")


def extract_quote(body: str, start: int, end: int) -> str:
    """Authoritative quote — always sliced from the server's copy of the body,
    never trusted from the client."""
    return (body or "")[start:end]


def excerpt(body: str, n: int = 240) -> str:
    body = (body or "").strip()
    return body if len(body) <= n else body[:n].rstrip() + "…"

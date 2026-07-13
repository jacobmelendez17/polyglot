"""Text normalization shared by the importer and (later) the answer checker.

Kept dependency-free and pure so it is trivially unit-testable.
"""
from __future__ import annotations

import unicodedata

_PUNCT = "¡!¿?.,;:\"«»()-"


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def normalize_term(text: str, *, fold_accents: bool = False) -> str:
    """Lowercase, collapse whitespace, strip surrounding punctuation.

    Accents are preserved by default (esta != está matters); fold_accents=True
    is used only where accent-insensitive matching is wanted.
    """
    text = unicodedata.normalize("NFC", text or "").strip().lower()
    text = " ".join(text.split())
    text = text.strip(_PUNCT).strip()
    if fold_accents:
        text = strip_accents(text)
    return text

"""Per-item user notes (slice 44) — pure validation.

A learner may keep a private note on any item, capped at 250 words. Word counting
and the cap live here so they're unit-testable and identical wherever enforced.
"""
from __future__ import annotations

MAX_NOTE_WORDS = 250
MAX_NOTE_CHARS = 4000  # a hard backstop so a wordless blob can't be unbounded


class NoteError(ValueError):
    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def count_words(text: str) -> int:
    return len((text or "").split())


def validate_note(text: str) -> str:
    """Return the cleaned note or raise NoteError. Empty is allowed (clears it)."""
    body = (text or "").strip()
    if len(body) > MAX_NOTE_CHARS:
        raise NoteError(f"Note is too long (max {MAX_NOTE_CHARS} characters).", "too_long")
    if count_words(body) > MAX_NOTE_WORDS:
        raise NoteError(f"Notes are limited to {MAX_NOTE_WORDS} words.", "too_many_words")
    return body

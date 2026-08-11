"""Pure validation for the in-app curriculum editor (slice 39).

No DB, no FastAPI — just the rules, so they're unit-testable in isolation and the
admin routes stay thin. Covers: level/batch bounds, the "articles only on nouns"
rule (§6, also a DB CHECK constraint), and enum membership for article/gender.
"""
from __future__ import annotations

# Curriculum shape (§5): a level holds 4 themed vocab batches (1–4) + 1 grammar
# batch. Levels are unbounded upward in practice; cap high as a sanity backstop.
MIN_LEVEL = 1
MAX_LEVEL = 200
MIN_BATCH = 1
MAX_BATCH = 4  # the 4 themed vocab batches; grammar has no sub-batch

ARTICLES = {"el", "la", "los", "las", "un", "una", "none"}
GENDERS = {"masculine", "feminine", "both", "neutral", "none"}
NOUN = "noun"

MAX_TERM_LEN = 120
MAX_TRANSLATION_LEN = 200


class EditError(ValueError):
    """User-safe validation failure with a stable code."""

    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def validate_level(level: int) -> int:
    if not isinstance(level, int) or level < MIN_LEVEL or level > MAX_LEVEL:
        raise EditError(f"Level must be between {MIN_LEVEL} and {MAX_LEVEL}.", "bad_level")
    return level


def validate_batch(batch: int) -> int:
    if not isinstance(batch, int) or batch < MIN_BATCH or batch > MAX_BATCH:
        raise EditError(
            f"Batch must be between {MIN_BATCH} and {MAX_BATCH} "
            "(the four themed vocabulary batches).",
            "bad_batch",
        )
    return batch


def validate_term(term: str) -> str:
    t = (term or "").strip()
    if not t:
        raise EditError("Term can't be empty.", "empty_term")
    if len(t) > MAX_TERM_LEN:
        raise EditError(f"Term must be ≤ {MAX_TERM_LEN} characters.", "term_too_long")
    return t


def normalize_article_gender(
    part_of_speech: str, article: str, gender: str
) -> tuple[str, str]:
    """Enforce the §6 rule: only Spanish nouns may carry an article/gender.

    Non-nouns are coerced to article='none' + gender='none' rather than being
    rejected, so a caller flipping the part of speech doesn't leave a stale
    article that would trip the DB CHECK constraint. Returns (article, gender).
    """
    art = (article or "none").strip().lower() or "none"
    gen = (gender or "none").strip().lower() or "none"
    if art not in ARTICLES:
        raise EditError(f"Article must be one of: {', '.join(sorted(ARTICLES))}.", "bad_article")
    if gen not in GENDERS:
        raise EditError(f"Gender must be one of: {', '.join(sorted(GENDERS))}.", "bad_gender")
    if (part_of_speech or "").strip().lower() != NOUN:
        # Not a noun → cannot carry an article; normalise to none/none.
        return "none", "none"
    return art, gen

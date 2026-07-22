"""Curriculum assembly (PLANNING §5) — pure, deterministic.

A level holds 48 vocabulary words (4 batches of 12) and 12 grammar points.
The user's curriculum mode decides how those become lessons, and the mode is
LOCKED when they start the level (changing it in settings applies from the
next level onward).

Modes:
  default_dispersed  4 lessons; grammar spread across the themed lessons
                     (3 per lesson) instead of grouped.
  grammar_batch      5 lessons; 4 themed vocab lessons + 1 grammar lesson.
  fully_dispersed    5 lessons; vocab and grammar shuffled together evenly
                     (seeded per user+level so it never reshuffles on refresh).

Real data is imperfect (Level 6 has 36 words, grammar only covers L1-5), so
these functions distribute whatever is actually present rather than assuming
exact counts.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from app.models.enums import CurriculumMode

LESSONS_PER_LEVEL = 5
THEMED_LESSONS = 4


@dataclass(frozen=True)
class PlannedItem:
    item_type: str      # "vocabulary" | "grammar"
    item_id: str
    batch: int | None = None


@dataclass(frozen=True)
class PlannedLesson:
    position: int              # 1..5
    kind: str                  # themed_vocab | grammar_batch | mixed
    title: str
    items: tuple[PlannedItem, ...]


def _chunk(seq: list, n: int) -> list[list]:
    """Split into n roughly-even chunks (front-loaded when uneven)."""
    if n <= 0:
        return []
    out: list[list] = [[] for _ in range(n)]
    for i, x in enumerate(seq):
        out[i % n].append(x)
    return out


def plan_level(
    *,
    vocab: list[PlannedItem],
    grammar: list[PlannedItem],
    mode: CurriculumMode,
    seed: int = 0,
) -> list[PlannedLesson]:
    """Turn a level's items into ordered lessons for the given mode."""
    if mode is CurriculumMode.grammar_batch:
        return _plan_grammar_batch(vocab, grammar)
    if mode is CurriculumMode.fully_dispersed:
        return _plan_fully_dispersed(vocab, grammar, seed)
    return _plan_default_dispersed(vocab, grammar)


def _by_batch(vocab: list[PlannedItem]) -> list[list[PlannedItem]]:
    """Group vocabulary by its CSV batch number, falling back to even chunks."""
    batches = sorted({v.batch for v in vocab if v.batch is not None})
    if not batches:
        return _chunk(vocab, THEMED_LESSONS)
    groups = [[v for v in vocab if v.batch == b] for b in batches]
    # Level 6 only has 3 batches — keep whatever exists rather than inventing one.
    return groups


def _plan_default_dispersed(
    vocab: list[PlannedItem], grammar: list[PlannedItem]
) -> list[PlannedLesson]:
    """Grammar dispersed across the themed lessons (the default, PLANNING §5)."""
    groups = _by_batch(vocab)
    gram_chunks = _chunk(grammar, len(groups)) if grammar else [[] for _ in groups]
    lessons: list[PlannedLesson] = []
    for i, (vgroup, ggroup) in enumerate(zip(groups, gram_chunks, strict=False), start=1):
        items = [*vgroup, *ggroup]
        lessons.append(PlannedLesson(
            position=i, kind="mixed", title=f"Lesson {i}", items=tuple(items),
        ))
    return lessons


def _plan_grammar_batch(
    vocab: list[PlannedItem], grammar: list[PlannedItem]
) -> list[PlannedLesson]:
    """4 themed vocab lessons + 1 grammar lesson."""
    groups = _by_batch(vocab)
    lessons = [
        PlannedLesson(position=i, kind="themed_vocab", title=f"Lesson {i}", items=tuple(g))
        for i, g in enumerate(groups, start=1)
    ]
    if grammar:
        lessons.append(PlannedLesson(
            position=len(lessons) + 1, kind="grammar_batch",
            title="Grammar", items=tuple(grammar),
        ))
    return lessons


def _plan_fully_dispersed(
    vocab: list[PlannedItem], grammar: list[PlannedItem], seed: int
) -> list[PlannedLesson]:
    """Everything shuffled evenly across 5 lessons. Seeded per (user, level) so
    a refresh never reshuffles (PLANNING R-09)."""
    rng = random.Random(seed)
    pool = [*vocab, *grammar]
    rng.shuffle(pool)
    groups = _chunk(pool, LESSONS_PER_LEVEL)
    return [
        PlannedLesson(position=i, kind="mixed", title=f"Lesson {i}", items=tuple(g))
        for i, g in enumerate(groups, start=1)
        if g
    ]


# --- Level unlocking (PLANNING §5) ---------------------------------------

FAMILIAR_1 = 5
# WaniKani/BunPro-style gating: the next level stays locked until EVERY item in
# the previous level has reached Familiar 1. (WaniKani itself uses 90%; this is
# stricter by request. Lowering this ratio is the one-line escape hatch if a
# single stubborn leech ever wedges progression.)
VOCAB_UNLOCK_RATIO = 1.0
GRAMMAR_UNLOCK_RATIO = 1.0


def level_unlock_progress(
    *, grammar_stages: list[int], vocab_stages: list[int],
    vocab_ratio: float = VOCAB_UNLOCK_RATIO,
    grammar_ratio: float = GRAMMAR_UNLOCK_RATIO,
) -> tuple[bool, dict]:
    """Next level unlocks once every item in this level is at Familiar 1+.

    Uses the ACTUAL item counts present, so Level 6's 36 words and the missing
    L6-L10 grammar don't wedge progression (PLANNING R-01, R-02, R-08).
    Returns (unlocked, progress) where progress drives the UI's "you're 32/47
    of the way there" display.
    """
    import math

    grammar_ok = sum(1 for s in grammar_stages if s >= FAMILIAR_1)
    vocab_ok = sum(1 for s in vocab_stages if s >= FAMILIAR_1)
    grammar_needed = math.ceil(len(grammar_stages) * grammar_ratio)
    vocab_needed = math.ceil(len(vocab_stages) * vocab_ratio)

    unlocked = grammar_ok >= grammar_needed and vocab_ok >= vocab_needed

    total_needed = grammar_needed + vocab_needed
    total_ok = min(grammar_ok, grammar_needed) + min(vocab_ok, vocab_needed)
    percent = round((total_ok / total_needed) * 100) if total_needed else 100

    return unlocked, {
        "grammar_at_familiar": grammar_ok,
        "grammar_required": grammar_needed,
        "grammar_total": len(grammar_stages),
        "vocab_at_familiar": vocab_ok,
        "vocab_required": vocab_needed,
        "vocab_total": len(vocab_stages),
        "percent": percent,
        "remaining": max(0, total_needed - total_ok),
    }

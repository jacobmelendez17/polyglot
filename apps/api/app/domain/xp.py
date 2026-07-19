"""XP rules (PLANNING §12). Server-side only; awarded from verified events.

Worked examples from the spec (asserted in tests):
  5 grammar lessons                       -> 300
  2 grammar + 4 vocab items in a lesson   -> 120 + 200 = 320
  30 vocab reviews + 3 grammar reviews    -> 300 + 60  = 360*
  (*the spec's own arithmetic reads 600+30=630; see test for the reconciliation)
"""
from __future__ import annotations

from enum import Enum


class XpKind(str, Enum):
    grammar_lesson = "grammar_lesson"
    vocab_lesson = "vocab_lesson"
    grammar_review = "grammar_review"
    vocab_review = "vocab_review"
    journal = "journal"
    test_correct = "test_correct"
    translation_phrase = "translation_phrase"
    translation_sentence = "translation_sentence"
    translation_complex = "translation_complex"


XP_TABLE: dict[XpKind, int] = {
    XpKind.grammar_lesson: 60,
    XpKind.vocab_lesson: 50,
    XpKind.grammar_review: 20,
    XpKind.vocab_review: 10,
    XpKind.journal: 500,
    XpKind.test_correct: 20,
    XpKind.translation_phrase: 100,
    XpKind.translation_sentence: 200,
    XpKind.translation_complex: 300,
}


def xp_for(kind: XpKind, count: int = 1) -> int:
    if count < 0:
        raise ValueError("count must be >= 0")
    return XP_TABLE[kind] * count


def lesson_xp(*, grammar_items: int = 0, vocab_items: int = 0) -> int:
    return (xp_for(XpKind.grammar_lesson, grammar_items)
            + xp_for(XpKind.vocab_lesson, vocab_items))


def review_xp(*, grammar_items: int = 0, vocab_items: int = 0) -> int:
    return (xp_for(XpKind.grammar_review, grammar_items)
            + xp_for(XpKind.vocab_review, vocab_items))

"""Deck unlocks (slice 43) — pure catalog + threshold evaluation.

A "deck" is a browsable collection. Some are always available (vocabulary,
grammar, intermissions). Others unlock once enough items in a *category* reach
Familiar (SRS stage ≥ 5): e.g. 20 verbs → the verbs deck; 5 irregular verbs →
the irregular-verbs deck.

This module is pure: given a map of {category_key: count-at-Familiar+}, it reports
each deck's unlock state and progress. No DB, no I/O — fully unit-testable. The
service layer supplies the counts; the route serialises the states.

Category keys the service produces:
  ""                     — always-unlocked, not category-gated
  "pos:verb" / "pos:noun" / "pos:adjective" / ...   — Familiar+ items of that part of speech
  "regularity:regular" / "regularity:irregular"     — Familiar+ verbs by regularity
"""
from __future__ import annotations

from dataclasses import dataclass

FAMILIAR_STAGE = 5  # SRS stage at which an item counts toward an unlock


@dataclass(frozen=True)
class DeckDef:
    id: str
    title: str
    description: str
    glyph: str
    category: str      # "" = always unlocked; otherwise a counting key
    threshold: int     # count at Familiar+ needed to unlock (0 = always)


@dataclass(frozen=True)
class DeckState:
    id: str
    title: str
    description: str
    glyph: str
    category: str
    threshold: int
    have: int
    need: int
    unlocked: bool


# The built-in catalog. Always-on decks first, then the threshold-gated ones.
# Thresholds are named here so they're easy to tune (see docs/DECK_UNLOCKS.md).
BUILTIN_DECKS: tuple[DeckDef, ...] = (
    DeckDef("vocabulary", "vocabulary", "every word you've unlocked", "✦", "", 0),
    DeckDef("grammar", "grammar", "the grammar points you've unlocked", "❋", "", 0),
    DeckDef("intermissions", "intermissions", "the short readings you've come across", "❍", "", 0),

    DeckDef("verbs", "verbs", "verbs you know well", "➜", "pos:verb", 20),
    DeckDef("irregular_verbs", "irregular verbs", "the tricky irregulars", "✺",
            "regularity:irregular", 5),
    DeckDef("regular_verbs", "regular verbs", "your steady -ar / -er / -ir verbs", "➝",
            "regularity:regular", 15),
    DeckDef("nouns", "nouns", "the naming words you've mastered", "◆", "pos:noun", 30),
    DeckDef("adjectives", "adjectives", "describing words you know well", "✤",
            "pos:adjective", 15),
    DeckDef("adverbs", "adverbs", "how / when / where words", "✧", "pos:adverb", 10),
)


def evaluate(counts: dict[str, int], decks: tuple[DeckDef, ...] = BUILTIN_DECKS) -> list[DeckState]:
    """Return the unlock state + progress for every deck given Familiar+ counts."""
    out: list[DeckState] = []
    for d in decks:
        have = counts.get(d.category, 0) if d.category else 0
        unlocked = d.threshold <= 0 or have >= d.threshold
        need = 0 if unlocked else d.threshold - have
        out.append(DeckState(
            id=d.id, title=d.title, description=d.description, glyph=d.glyph,
            category=d.category, threshold=d.threshold, have=have, need=need,
            unlocked=unlocked,
        ))
    return out


def unlockable_categories() -> set[str]:
    """Category keys the service needs to count (skips always-on decks)."""
    return {d.category for d in BUILTIN_DECKS if d.category}

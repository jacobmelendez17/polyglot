"""Practice mode logic — pure functions (PLANNING §7).

Practice is UNSCHEDULED, on-demand drilling that draws from items the user has
already learned. Unlike SRS review it doesn't change the SRS stage; it awards XP
and (for the practice-stage system) advances Uno..Cinco. Three modes here:

  fill_blank   — a cloze sentence with one word removed; type the missing word.
  conjugation  — given an infinitive + tense + person, type the conjugated form.
  weak_items   — a batch built from the user's leeches / most-missed items.

Selection is deterministic given a seed so tests are stable and a refresh doesn't
reshuffle a session.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum


class PracticeMode(str, Enum):
    fill_blank = "fill_blank"
    conjugation = "conjugation"
    weak_items = "weak_items"
    listening = "listening"      # hear it, type what you heard


@dataclass(frozen=True)
class PracticeCandidate:
    """An item eligible for practice, with the signals used to weight selection."""
    item_type: str
    item_id: str
    srs_stage: int
    leech_score: float
    total_incorrect: int
    has_example: bool = False       # fill_blank needs an example sentence
    is_verb: bool = False           # conjugation needs a verb


# --- weak-item selection -------------------------------------------------

def weak_item_weight(c: PracticeCandidate) -> float:
    """Higher = more in need of practice. Leeches dominate, then raw mistakes,
    then lower SRS stages (less established)."""
    return (
        c.leech_score * 3.0
        + c.total_incorrect * 0.5
        + max(0, 6 - c.srs_stage) * 0.2
    )


def select_weak_items(
    candidates: list[PracticeCandidate], *, limit: int = 10, seed: int = 0,
) -> list[PracticeCandidate]:
    """Pick the items most in need of practice. Ties broken deterministically by
    a seeded shuffle so equal-weight items don't always appear in id order."""
    rng = random.Random(seed)
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    ranked = sorted(shuffled, key=weak_item_weight, reverse=True)
    # Only include items that actually have some difficulty signal.
    meaningful = [c for c in ranked if weak_item_weight(c) > 0]
    pool = meaningful or ranked   # fall back to anything if nobody is "weak" yet
    return pool[:limit]


def select_practice_pool(
    candidates: list[PracticeCandidate], mode: PracticeMode, *,
    limit: int = 10, seed: int = 0,
) -> list[PracticeCandidate]:
    if mode is PracticeMode.weak_items:
        return select_weak_items(candidates, limit=limit, seed=seed)
    if mode is PracticeMode.fill_blank:
        eligible = [c for c in candidates if c.has_example]
    elif mode is PracticeMode.conjugation:
        eligible = [c for c in candidates if c.is_verb]
    elif mode is PracticeMode.listening:
        # Anything with a spoken form works; vocabulary is always speakable.
        eligible = [c for c in candidates if c.item_type == "vocabulary"]
    else:
        eligible = list(candidates)
    rng = random.Random(seed)
    rng.shuffle(eligible)
    return eligible[:limit]


# --- fill-in-the-blank prompt construction -------------------------------

@dataclass(frozen=True)
class ClozePrompt:
    sentence_with_blank: str
    answer: str
    translation: str


def make_cloze(example: str, term: str, translation: str, *,
               blank: str = "_____") -> ClozePrompt | None:
    """Remove the target term from an example sentence, case-insensitively,
    matching whole words only. Returns None if the term isn't found (so the
    caller can skip rather than show a broken prompt)."""
    if not example or not term:
        return None
    import re
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    if not pattern.search(example):
        return None
    blanked = pattern.sub(blank, example, count=1)
    return ClozePrompt(sentence_with_blank=blanked, answer=term, translation=translation)


# --- conjugation prompt construction -------------------------------------

TENSES = ("present", "preterite", "imperfect", "future")
PERSONS = ("yo", "tú", "él/ella", "nosotros", "vosotros", "ellos/ellas")


@dataclass(frozen=True)
class ConjugationPrompt:
    infinitive: str
    tense: str
    person: str
    answer: str


def make_conjugation(
    infinitive: str, conjugations: dict, *, tense: str, person: str,
) -> ConjugationPrompt | None:
    """Pull the expected form from a {tense: {person: form}} map.
    Returns None if that cell isn't populated."""
    form = (conjugations or {}).get(tense, {}).get(person)
    if not form:
        return None
    return ConjugationPrompt(
        infinitive=infinitive, tense=tense, person=person, answer=form,
    )


def available_conjugation_cells(conjugations: dict) -> list[tuple[str, str]]:
    """Every (tense, person) pair that actually has a stored form."""
    out: list[tuple[str, str]] = []
    for tense, forms in (conjugations or {}).items():
        for person, form in (forms or {}).items():
            if form:
                out.append((tense, person))
    return out


# --- practice-stage progression (Uno..Cinco, PLANNING §10) ---------------

MAX_PRACTICE_STAGE = 5


def advance_practice_stage(current: int, *, correct: bool) -> int:
    """Practice stages only go up, and only on a correct answer. They cap at
    Cinco. A wrong answer holds the stage (practice is low-stakes)."""
    if correct:
        return min(current + 1, MAX_PRACTICE_STAGE)
    return current


def is_perfect(stage: int) -> bool:
    """'Perfect' status = reached the top practice stage (PLANNING §10)."""
    return stage >= MAX_PRACTICE_STAGE

"""Schemas for item detail, review history, user synonyms, level progression.

Kept separate from `schemas.py` because that module is already carrying auth,
admin, lessons, reviews, and stats; splitting by feature keeps each file
readable. Every request body/query is validated here (PLANNING §25).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

ITEM_TYPE_PATTERN = "^(vocabulary|grammar)$"


class PracticeStageOut(BaseModel):
    category: str
    stage: int
    max_stage: int
    label: str
    complete: bool
    on_cooldown: bool
    next_available_at: str | None = None
    stage_reached_at: str | None = None


class PracticeSummaryOut(BaseModel):
    stages: list[PracticeStageOut]
    categories_complete: int
    categories_total: int
    completed_categories: list[str]
    remaining_categories: list[str]
    srs_fluent: bool
    perfect: bool


class ItemProgressOut(BaseModel):
    learned: bool
    srs_stage: int
    srs_stage_name: str
    next_review_at: str | None = None
    unlocked_at: str | None = None
    lesson_completed_at: str | None = None
    fluent: bool
    fluent_at: str | None = None
    perfect: bool
    perfect_at: str | None = None
    total_reviews: int
    total_incorrect: int
    answers_total: int
    answers_correct: int
    accuracy: float | None = None
    mistakes: int
    leech_state: str
    leech_score: float


class UserSynonymOut(BaseModel):
    id: str
    synonym: str


class ExampleSentenceOut(BaseModel):
    id: str
    text_es: str
    text_en: str
    difficulty: str
    role: str
    audio: dict | None = None


class ItemDetailOut(BaseModel):
    """Public item view. Deliberately has no accepted/rejected answer fields —
    those are the answer key and never leave the server (spec §6)."""

    item_type: str
    item_id: str
    term: str
    translation: str
    part_of_speech: str
    meaning: str
    level: int
    level_title: str
    synonyms: list[str]
    audio: dict | None = None
    examples: list[ExampleSentenceOut]
    user_synonyms: list[UserSynonymOut]
    progress: ItemProgressOut
    practice: PracticeSummaryOut
    # vocabulary-only
    pronunciation: str | None = None
    ipa: str | None = None
    article: str | None = None
    gender: str | None = None
    variations: list[str] | None = None
    castilian_variant: str | None = None
    latam_variant: str | None = None
    context: list | None = None
    # grammar-only
    structure: str | None = None
    explanation: str | None = None


class ReviewHistoryEntryOut(BaseModel):
    id: str
    direction: str
    prompt_kind: str
    submitted_answer: str
    original_correct: bool
    final_correct: bool
    typo_forgiven: bool
    synonym_matched: bool
    undo_used: bool
    warnings: list[str]
    srs_stage_before: int | None = None
    srs_stage_after: int | None = None
    pair_incomplete: bool
    answered_at: str | None = None


class ReviewHistoryOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ReviewHistoryEntryOut]


class AddSynonymRequest(BaseModel):
    synonym: str = Field(min_length=1, max_length=60)


class AddSynonymOut(BaseModel):
    id: str
    synonym: str
    created: bool


class LevelProgressItemOut(BaseModel):
    item_type: str
    item_id: str
    term: str
    translation: str
    part_of_speech: str
    article: str | None = None
    learned: bool
    srs_stage: int
    srs_stage_name: str
    next_review_at: str | None = None
    leech_state: str
    practice_stages: dict[str, int]
    practice_labels: dict[str, str]
    categories_complete: int
    perfect: bool


class LevelProgressTotalsOut(BaseModel):
    items: int
    learned: int
    not_started: int
    familiar_plus: int
    fluent: int
    perfect: int
    leeches: int


class LevelProgressOut(BaseModel):
    position: int
    title: str
    unlocked: bool
    totals: LevelProgressTotalsOut
    items: list[LevelProgressItemOut]

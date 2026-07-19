"""Request/response schemas. Every request body is validated here (PLANNING §25)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=500)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=500)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: str
    email: str
    role: str


class MeResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    capabilities: list[str]


# ---- Admin ----

class ImportReportOut(BaseModel):
    kind: str
    rows_seen: int
    rows_ok: int
    error_count: int
    warning_count: int
    level_counts: dict[int, int]
    issues: list[dict]


class ImportResult(BaseModel):
    created: int
    updated: int
    report: ImportReportOut


class ContentItemOut(BaseModel):
    id: str
    term: str
    translation: str
    part_of_speech: str
    level: int
    status: str


class ContentListOut(BaseModel):
    items: list[ContentItemOut]
    total: int


class StatusChange(BaseModel):
    status: str = Field(pattern="^(draft|in_review|published|archived)$")


class AdminUserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    status: str


class RoleChange(BaseModel):
    role: str = Field(pattern="^(user|beta_tester|moderator|content_editor|admin|owner)$")


# ---- Learn (lessons + reviews) ----

class LevelOut(BaseModel):
    id: str
    position: int
    title: str
    vocab_count: int
    grammar_count: int
    unlocked: bool


class LessonOut(BaseModel):
    position: int
    kind: str
    title: str
    item_count: int
    completed: bool


class LessonDetailOut(BaseModel):
    position: int
    title: str
    items: list[dict]


class CompleteLessonRequest(BaseModel):
    idempotency_key: str


class CompleteLessonOut(BaseModel):
    xp_awarded: int
    unlocked: int
    already_completed: bool


class QueuePromptOut(BaseModel):
    item_type: str
    item_id: str
    direction: str
    srs_stage: int
    prompt_kind: str
    shown: str
    article: str | None = None
    part_of_speech: str = ""
    hint: str | None = None


class SessionOut(BaseModel):
    session_id: str
    prompts: list[QueuePromptOut]


class SubmitAnswerRequest(BaseModel):
    item_type: str = Field(pattern="^(vocabulary|grammar)$")
    item_id: str
    direction: str = Field(pattern="^(es_to_en|en_to_es)$")
    answer: str = Field(max_length=500)
    idempotency_key: str


class SubmitAnswerOut(BaseModel):
    original_correct: bool
    final_correct: bool
    warnings: list[str]
    typo_forgiven: bool
    synonym_matched: bool
    expected: str
    pair_resolved: bool
    srs_stage_before: int | None = None
    srs_stage_after: int | None = None
    xp_awarded: int = 0
    answer_id: str | None = None
    message: str | None = None


class UndoRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ForecastBucket(BaseModel):
    label: str
    count: int


class SrsStageCount(BaseModel):
    stage: int
    name: str
    count: int


class StatsOut(BaseModel):
    xp_total: int
    reviews_due: int
    lessons_available: int
    items_learned: int
    items_fluent: int
    leeches: int
    # WaniKani-style grouped SRS buckets for the progression widget.
    stage_group_counts: dict[str, int]
    stage_counts: list[SrsStageCount]
    forecast: list[ForecastBucket]
    next_review_at: str | None = None


# ---- Practice ----

class PracticePromptOut(BaseModel):
    item_type: str
    item_id: str
    mode: str
    shown: str
    translation: str
    tense: str | None = None
    person: str | None = None


class PracticeSessionOut(BaseModel):
    session_id: str
    mode: str
    prompts: list[PracticePromptOut]


class PracticeAnswerRequest(BaseModel):
    item_type: str = Field(pattern="^(vocabulary|grammar)$")
    item_id: str
    mode: str = Field(pattern="^(fill_blank|conjugation|weak_items)$")
    answer: str = Field(max_length=500)
    tense: str | None = Field(default=None, max_length=30)
    person: str | None = Field(default=None, max_length=30)
    idempotency_key: str


class PracticeGradeOut(BaseModel):
    correct: bool
    expected: str
    warnings: list[str]
    xp_awarded: int
    practice_stage: int | None = None
    perfect: bool = False

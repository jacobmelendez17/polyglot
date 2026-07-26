"""Schemas for password reset, email verification, and decks."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

DECK_TYPE_PATTERN = "^(vocabulary|grammar|intermissions)$"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class MessageOut(BaseModel):
    ok: bool = True
    message: str


class VerificationStatusOut(BaseModel):
    email: str
    verified: bool


class VerifyResultOut(BaseModel):
    verified: bool
    already_verified: bool


# --- decks ---------------------------------------------------------------

class DeckSummaryOut(BaseModel):
    type: str
    title: str
    description: str
    count: int


class DeckItemOut(BaseModel):
    item_type: str
    item_id: str
    term: str
    translation: str
    part_of_speech: str | None = None
    article: str | None = None
    level: int | None = None
    learned: bool | None = None
    srs_stage: int | None = None
    srs_stage_name: str | None = None
    next_review_at: str | None = None
    # intermissions only
    body: str | None = None
    kind: str | None = None
    viewed_at: str | None = None


class DeckPageOut(BaseModel):
    type: str
    total: int
    limit: int
    offset: int
    items: list[DeckItemOut]

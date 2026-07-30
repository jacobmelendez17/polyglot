"""Schemas for feedback/support and onboarding."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SubmitFeedbackRequest(BaseModel):
    category: str = Field(pattern="^(bug|feature|question|other)$")
    body: str = Field(min_length=1, max_length=5_000)
    route: str = Field(default="", max_length=300)
    browser: str = Field(default="", max_length=300)


class SubmitFeedbackOut(BaseModel):
    id: str
    state: str


class FeedbackTicketOut(BaseModel):
    id: str
    category: str
    body: str
    route: str
    browser: str
    state: str
    pinned: bool
    from_name: str
    from_email: str
    admin_response: str
    responded_at: str | None = None
    email_sent: bool
    created_at: str | None = None


class FeedbackListOut(BaseModel):
    total: int
    limit: int
    offset: int
    tickets: list[FeedbackTicketOut]
    counts: dict


class RespondRequest(BaseModel):
    response: str = Field(min_length=1, max_length=5_000)


class PinRequest(BaseModel):
    pinned: bool


class StateRequest(BaseModel):
    state: str = Field(pattern="^(unanswered|answered)$")


class OnboardingStateOut(BaseModel):
    completed: bool

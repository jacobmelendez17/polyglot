"""Schemas for intermissions, changelog, and immersion mode."""
from __future__ import annotations

from pydantic import BaseModel, Field

CHANGELOG_TYPE_PATTERN = "^(feature|fix|content|announcement)$"
EVENT_PATTERN = "^(level_start|lesson_complete|progress)$"


class IntermissionOut(BaseModel):
    id: str
    title: str
    body: str
    kind: str
    trigger_description: str
    viewed_at: str | None = None


class IntermissionHistoryOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[IntermissionOut]


class ViewedOut(BaseModel):
    id: str
    viewed_at: str | None = None


class ChangelogItemOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    published_at: str | None = None


class ChangelogPageOut(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ChangelogItemOut]


class UnreadOut(BaseModel):
    unread: int
    last_read_at: str | None = None


class ImmersionOut(BaseModel):
    unlocked: bool
    enabled: bool
    unlock_level: int
    levels_completed: int
    levels_remaining: int
    never_translated: list[str]


class ImmersionIn(BaseModel):
    enabled: bool


# --- admin ---------------------------------------------------------------

class ChangelogCreate(BaseModel):
    type: str = Field(pattern=CHANGELOG_TYPE_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20_000)
    publish: bool = False


class ChangelogUpdate(BaseModel):
    type: str | None = Field(default=None, pattern=CHANGELOG_TYPE_PATTERN)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=20_000)


class AdminChangelogOut(BaseModel):
    id: str
    type: str
    title: str
    body: str
    status: str
    published_at: str | None = None


class IntermissionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=20_000)
    trigger: dict = Field(default_factory=dict)
    publish: bool = False


class AdminIntermissionOut(BaseModel):
    id: str
    title: str
    body: str
    trigger: dict
    trigger_description: str
    status: str


class StatusIn(BaseModel):
    status: str = Field(pattern="^(draft|in_review|published|archived)$")

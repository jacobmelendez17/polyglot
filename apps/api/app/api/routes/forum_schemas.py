"""Schemas for forum endpoints. Every write body is validated here (§25)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: str
    slug: str
    title: str
    description: str
    locked: bool
    thread_count: int


class ThreadSummaryOut(BaseModel):
    id: str
    title: str
    slug: str
    author: str
    reply_count: int
    pinned: bool
    locked: bool
    hidden: bool
    created_at: str | None = None
    last_activity_at: str | None = None


class ThreadListOut(BaseModel):
    category: dict
    total: int
    limit: int
    offset: int
    threads: list[ThreadSummaryOut]


class ReplyOut(BaseModel):
    id: str
    body: str
    author: str
    hidden: bool
    created_at: str | None = None


class ThreadDetailOut(BaseModel):
    id: str
    title: str
    body: str
    author: str
    category: dict | None = None
    pinned: bool
    locked: bool
    hidden: bool
    created_at: str | None = None
    reply_total: int
    limit: int
    offset: int
    replies: list[ReplyOut]


class CreateThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=10_000)


class CreateReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10_000)


class ReportRequest(BaseModel):
    target_type: str = Field(pattern="^(thread|reply)$")
    target_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(pattern="^(spam|abuse|off_topic|other)$")
    detail: str = Field(default="", max_length=2_000)


class ReportOut(BaseModel):
    reported: bool
    already: bool
    auto_hidden: bool


class ModerateRequest(BaseModel):
    target_type: str = Field(pattern="^(thread|reply)$")
    target_id: str = Field(min_length=1, max_length=64)
    action: str = Field(pattern="^(hide|unhide|delete|restore)$")


class ModerateOut(BaseModel):
    target_type: str
    target_id: str
    action: str
    hidden: bool
    deleted: bool


class ReportQueueItem(BaseModel):
    id: str
    target_type: str
    target_id: str
    reason: str
    detail: str
    created_at: str | None = None


class PostingStateOut(BaseModel):
    posting_enabled: bool

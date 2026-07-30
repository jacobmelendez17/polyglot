"""Forum models (spec §18).

Four tables. Categories are seeded and fixed (Grammar Help, Vocabulary, …).
Threads start a discussion inside a category; replies hang off a thread; reports
flag either a thread or a reply for a moderator.

Moderation is soft throughout: a hidden post keeps its row (with who hid it and
when) so it can be restored, and deletion is a `deleted_at` stamp, never a real
DELETE — the same soft-delete discipline the rest of the platform uses (§22).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, TimestampMixin, fk, pk


class ForumCategory(Base, TimestampMixin):
    __tablename__ = "forum_categories"

    id: Mapped[uuid.UUID] = pk()
    slug: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    # A locked category can be browsed but not posted to, independent of the
    # global posting switch — useful for read-only announcement categories.
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ForumThread(Base, TimestampMixin):
    __tablename__ = "forum_threads"

    id: Mapped[uuid.UUID] = pk()
    category_id: Mapped[uuid.UUID] = fk("forum_categories.id", nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), default="")
    body: Mapped[str] = mapped_column(Text, default="")

    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_activity_at: Mapped[datetime | None]

    pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Moderation. hidden_at != None → withheld from public listings pending review.
    hidden_at: Mapped[datetime | None]
    hidden_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    deleted_at: Mapped[datetime | None]


class ForumReply(Base, TimestampMixin):
    __tablename__ = "forum_replies"

    id: Mapped[uuid.UUID] = pk()
    thread_id: Mapped[uuid.UUID] = fk("forum_threads.id", nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, default="")

    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    hidden_at: Mapped[datetime | None]
    hidden_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    deleted_at: Mapped[datetime | None]


class ForumReport(Base, TimestampMixin):
    __tablename__ = "forum_reports"
    # One report per person per target — re-reporting the same post does nothing,
    # so the auto-hide threshold counts distinct people, not clicks.
    __table_args__ = (
        UniqueConstraint("reporter_id", "target_type", "target_id",
                         name="uq_forum_report_once"),
    )

    id: Mapped[uuid.UUID] = pk()
    reporter_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)  # thread | reply
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(20), default="other")
    detail: Mapped[str] = mapped_column(Text, default="")

    resolved_at: Mapped[datetime | None]
    resolved_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    action_taken: Mapped[str] = mapped_column(String(20), default="")  # hidden|deleted|dismissed

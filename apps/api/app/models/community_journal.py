"""Community feedback on shared journal entries (spec §7).

One row per comment left on a shared journal entry. `hidden` is the moderation
flag (mirrors the forum reply pattern): a moderator can hide a comment without
deleting it, so nothing is lost and it can be restored. Feedback is only ever
shown for entries that are currently shared and visible — the visibility gate in
`domain.community_journal` is enforced in the service before any feedback is read
or written.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk, pk


class JournalFeedback(Base, TimestampMixin):
    __tablename__ = "journal_feedback"
    id: Mapped[uuid.UUID] = pk()
    entry_id: Mapped[uuid.UUID] = fk("journal_entries.id", nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, default="")
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_reason: Mapped[str | None]

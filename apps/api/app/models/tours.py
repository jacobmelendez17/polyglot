"""Guided-tour state (PLANNING §14).

One row per user per tour. Kept in its own table rather than as a flag on
`user_settings` because tours are plural and will keep arriving — the dashboard
walkthrough now, a reviews walkthrough later — and a boolean column per tour
would mean a migration every time.

`step_index` is stored as the learner advances so a refresh mid-tour resumes
where they were instead of restarting from step one.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk, pk


class UserTourState(Base, TimestampMixin):
    __tablename__ = "user_tour_state"
    __table_args__ = (
        UniqueConstraint("user_id", "tour_key", name="uq_user_tour"),
    )

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    tour_key: Mapped[str] = mapped_column(String(40), nullable=False)
    step_index: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    completed_at: Mapped[datetime | None]
    # Skipping still completes the tour — we just record which way it ended so
    # analytics can tell "finished the walkthrough" from "dismissed it".
    skipped: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

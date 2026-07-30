"""Vacation / pause periods (spec R-25).

One row per pause. A period is *open* (the user is currently paused) while
`ended_at` is NULL; resuming stamps `ended_at` and records how far the schedule
was shifted, so the whole thing is auditable — you can see when someone paused,
for how long, and how many items moved. At most one open period per user is
enforced in the service.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk, pk


class VacationPeriod(Base, TimestampMixin):
    __tablename__ = "vacation_periods"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    started_at: Mapped[datetime]
    ended_at: Mapped[datetime | None]
    # Set on resume: the shift applied and how many items it touched.
    shift_seconds: Mapped[int] = mapped_column(Integer, default=0)
    items_shifted: Mapped[int] = mapped_column(Integer, default=0)

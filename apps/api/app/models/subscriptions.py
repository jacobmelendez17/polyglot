"""Subscription state (spec §19).

One row per user. `status` is the source of truth for what they can reach;
`resolve_entitlement` in the domain layer turns it (plus the clock) into an
entitlement every request. The Stripe columns are nullable because free, beta,
and lifetime users never touch Stripe — only paid subscriptions carry them.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk, pk


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, unique=True, index=True)

    # free | beta | lifetime | paid_active | paid_past_due | paid_canceled
    status: Mapped[str] = mapped_column(String(20), default="free", nullable=False)

    # Stripe linkage — all nullable; only paid subs use them.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(80), index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(80), index=True)
    price_interval: Mapped[str | None] = mapped_column(String(10))  # month | year

    # When the current paid period ends. For a canceled sub this is the moment
    # access drops back to free; the entitlement is recomputed from it, so no
    # cron is needed to perform the downgrade.
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

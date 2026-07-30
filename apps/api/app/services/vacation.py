"""Vacation / pause service (spec R-25).

Pausing opens a period; resuming closes it and shifts the schedule. The shift is
computed by the pure `domain.vacation` functions and applied in Python (not in
SQL) so the behavior is identical on Postgres and the test database — no reliance
on database-specific interval arithmetic.

`is_paused` is the single predicate the rest of the app asks: the review queue
calls it to stay empty during a break.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import vacation as rules
from app.models.progress import UserItemProgress
from app.models.vacation import VacationPeriod


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def _open_period(db: Session, user_id: uuid.UUID) -> VacationPeriod | None:
    return db.execute(
        select(VacationPeriod)
        .where(VacationPeriod.user_id == user_id, VacationPeriod.ended_at.is_(None))
        .order_by(VacationPeriod.started_at.desc())
    ).scalars().first()


def is_paused(db: Session, user_id: uuid.UUID) -> bool:
    return _open_period(db, user_id) is not None


def get_state(db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None) -> dict:
    now = now or _now()
    period = _open_period(db, user_id)
    if period is None:
        return {"paused": False, "since": None, "days": 0}
    return {
        "paused": True,
        "since": _iso(period.started_at),
        "days": rules.paused_days(period.started_at, now),
    }


def pause(db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None) -> dict:
    """Start a break. Idempotent: pausing while already paused is a no-op that
    returns the existing state (the original start time is preserved)."""
    now = now or _now()
    existing = _open_period(db, user_id)
    if existing is not None:
        return get_state(db, user_id=user_id, now=now)
    db.add(VacationPeriod(user_id=user_id, started_at=now))
    db.flush()
    return get_state(db, user_id=user_id, now=now)


def resume(db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None) -> dict:
    """End a break and shift the schedule forward by its duration.

    No-op if the user isn't paused. Otherwise every item that existed before the
    pause has its `next_review_at` pushed by the elapsed time; items learned
    during the break are left alone.
    """
    now = now or _now()
    period = _open_period(db, user_id)
    if period is None:
        return {"resumed": False, "shifted": 0, "shift_seconds": 0,
                "paused": False, "since": None, "days": 0}

    shift = rules.compute_shift(period.started_at, now)
    shifted_count = 0
    if shift.total_seconds() > 0:
        items = db.execute(
            select(UserItemProgress).where(
                UserItemProgress.user_id == user_id,
                UserItemProgress.next_review_at.is_not(None),
            )
        ).scalars().all()
        for item in items:
            if rules.should_shift_item(item.unlocked_at, period.started_at):
                item.next_review_at = rules.shifted(item.next_review_at, shift)
                shifted_count += 1

    period.ended_at = now
    period.shift_seconds = int(shift.total_seconds())
    period.items_shifted = shifted_count
    db.flush()
    return {
        "resumed": True,
        "shifted": shifted_count,
        "shift_seconds": int(shift.total_seconds()),
        "paused": False,
        "since": None,
        "days": 0,
    }

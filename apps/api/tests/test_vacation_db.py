"""Vacation mode end-to-end: pause freezes reviews, resume shifts the schedule."""
import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from app.models.enums import ItemType
from app.models.progress import UserItemProgress
from app.models.vacation import VacationPeriod
from app.services import reviews as review_svc
from app.services import vacation as svc


def _mk_item(db, user_id, *, next_review_at, unlocked_at, stage=3):
    p = UserItemProgress(
        user_id=user_id, item_type=ItemType.vocabulary, item_id=uuid.uuid4(),
        srs_stage=stage, next_review_at=next_review_at, unlocked_at=unlocked_at,
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture()
def user_id(db):
    # A bare user row is enough for these tests; the FK points at users.id.
    from app.models.identity import User
    from app.models.enums import UserRole
    u = User(email=f"vac-{uuid.uuid4().hex[:8]}@example.com", role=UserRole.user)
    db.add(u)
    db.flush()
    return u.id


def test_pause_opens_a_single_period(db, user_id):
    now = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    svc.pause(db, user_id=user_id, now=now)
    # pausing again doesn't open a second period or move the start
    svc.pause(db, user_id=user_id, now=now + dt.timedelta(days=1))
    open_periods = db.execute(
        select(VacationPeriod).where(
            VacationPeriod.user_id == user_id, VacationPeriod.ended_at.is_(None))
    ).scalars().all()
    assert len(open_periods) == 1
    assert open_periods[0].started_at.replace(tzinfo=dt.timezone.utc) == now


def test_state_reports_paused_and_days(db, user_id):
    start = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    svc.pause(db, user_id=user_id, now=start)
    state = svc.get_state(db, user_id=user_id, now=start + dt.timedelta(days=4))
    assert state["paused"] is True
    assert state["days"] == 4


def test_reviews_are_frozen_while_paused(db, user_id):
    now = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    # an item that is due right now
    _mk_item(db, user_id, next_review_at=now - dt.timedelta(hours=1),
             unlocked_at=now - dt.timedelta(days=5))
    assert len(review_svc.due_items(db, user_id, now=now)) == 1

    svc.pause(db, user_id=user_id, now=now)
    # frozen: nothing is due while paused
    assert review_svc.due_items(db, user_id, now=now) == []


def test_resume_shifts_pre_pause_items_by_the_break_length(db, user_id):
    pause_at = dt.datetime(2026, 7, 1, 12, tzinfo=dt.timezone.utc)
    # due 2 days after the pause begins; unlocked well before
    item = _mk_item(db, user_id, next_review_at=pause_at + dt.timedelta(days=2),
                    unlocked_at=pause_at - dt.timedelta(days=10))
    original_due = item.next_review_at

    svc.pause(db, user_id=user_id, now=pause_at)
    resume_at = pause_at + dt.timedelta(days=10)
    result = svc.resume(db, user_id=user_id, now=resume_at)

    assert result["resumed"] is True
    assert result["shifted"] == 1
    db.refresh(item)
    # pushed forward by exactly the 10-day break → still due 2 days out
    assert item.next_review_at.replace(tzinfo=dt.timezone.utc) == \
        original_due.replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=10)


def test_items_learned_during_the_break_are_not_shifted(db, user_id):
    pause_at = dt.datetime(2026, 7, 1, 12, tzinfo=dt.timezone.utc)
    svc.pause(db, user_id=user_id, now=pause_at)

    # learned three days into the vacation
    learned_at = pause_at + dt.timedelta(days=3)
    fresh = _mk_item(db, user_id, next_review_at=learned_at + dt.timedelta(hours=4),
                     unlocked_at=learned_at)
    untouched_due = fresh.next_review_at

    svc.resume(db, user_id=user_id, now=pause_at + dt.timedelta(days=10))
    db.refresh(fresh)
    assert fresh.next_review_at.replace(tzinfo=dt.timezone.utc) == \
        untouched_due.replace(tzinfo=dt.timezone.utc)


def test_resume_when_not_paused_is_a_noop(db, user_id):
    result = svc.resume(db, user_id=user_id, now=dt.datetime.now(tz=dt.timezone.utc))
    assert result["resumed"] is False
    assert result["shifted"] == 0


def test_resume_reopens_normally_after(db, user_id):
    now = dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    svc.pause(db, user_id=user_id, now=now)
    svc.resume(db, user_id=user_id, now=now + dt.timedelta(days=2))
    assert svc.is_paused(db, user_id) is False
    # can pause again — a second period
    svc.pause(db, user_id=user_id, now=now + dt.timedelta(days=3))
    assert svc.is_paused(db, user_id) is True

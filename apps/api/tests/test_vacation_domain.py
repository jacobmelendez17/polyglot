"""Vacation shift math — the invariant this slice exists to protect."""
import datetime as dt

from app.domain.vacation import (
    MAX_SHIFT,
    compute_shift,
    paused_days,
    shifted,
    should_shift_item,
)

P = dt.datetime(2026, 7, 1, 12, 0, tzinfo=dt.timezone.utc)
R = P + dt.timedelta(days=10)


def test_shift_is_the_pause_duration():
    assert compute_shift(P, R) == dt.timedelta(days=10)


def test_resume_before_pause_yields_no_shift():
    assert compute_shift(R, P) == dt.timedelta(0)


def test_shift_is_capped():
    assert compute_shift(P, P + dt.timedelta(days=99999)) == MAX_SHIFT


def test_time_until_due_is_preserved():
    # The core promise: an item 3 days from due stays 3 days from due.
    shift = compute_shift(P, R)
    due_before = P + dt.timedelta(days=3)
    assert shifted(due_before, shift) - R == dt.timedelta(days=3)


def test_overdue_stays_equally_overdue():
    shift = compute_shift(P, R)
    overdue = P - dt.timedelta(days=1)
    # still one day behind, relative to the resume moment
    assert shifted(overdue, shift) - R == dt.timedelta(days=-1)


def test_only_pre_pause_items_shift():
    assert should_shift_item(P - dt.timedelta(days=5), P) is True
    assert should_shift_item(P, P) is True                       # boundary = shift
    assert should_shift_item(P + dt.timedelta(days=2), P) is False  # learned mid-break
    assert should_shift_item(None, P) is True                    # null unlock = old


def test_naive_datetimes_are_tolerated():
    assert compute_shift(P.replace(tzinfo=None), R.replace(tzinfo=None)) == dt.timedelta(days=10)


def test_paused_days():
    assert paused_days(P, R) == 10
    assert paused_days(R, P) == 0

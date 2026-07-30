"""Vacation / pause mode — pure scheduling math (spec R-25).

The one invariant this slice exists to protect: pausing and resuming must never
corrupt an item's `next_review_at`. The model that guarantees it is simple —

  while paused, no reviews come due; on resume, every item that existed *before*
  the pause has its due date pushed forward by exactly the pause's length.

That preserves each item's time-until-due across the break (an item three days
from due is still three days from due when you get back), so nothing turns into a
huge overdue pile and nothing is advanced for free. Items learned *during* the
break are left on their natural schedule — they were never frozen, so they aren't
shifted. These functions are deterministic and take every timestamp explicitly so
the behavior is fully unit-testable.
"""
from __future__ import annotations

import datetime as dt

# A sanity ceiling. A "pause" longer than this is almost certainly a clock or
# data problem, not a real vacation; we cap the shift rather than fling every due
# date into the far future. Ten years is comfortably beyond any real break.
MAX_SHIFT = dt.timedelta(days=3650)


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def compute_shift(paused_at: dt.datetime, resumed_at: dt.datetime) -> dt.timedelta:
    """How far to push due dates forward: the elapsed pause duration.

    Never negative (a resume that predates the pause yields no shift), and capped
    at MAX_SHIFT so a bad clock can't launch the schedule into the next decade.
    """
    delta = _aware(resumed_at) - _aware(paused_at)
    if delta.total_seconds() <= 0:
        return dt.timedelta(0)
    return min(delta, MAX_SHIFT)


def should_shift_item(
    unlocked_at: dt.datetime | None, paused_at: dt.datetime,
) -> bool:
    """Only items that existed before the pause get shifted.

    An item unlocked during the break was never frozen, so its schedule is
    already correct and must be left alone. `unlocked_at is None` is treated as
    "old" (pre-existing) — the conservative choice, since a null unlock time
    predates any pause we'd be resuming from.
    """
    if unlocked_at is None:
        return True
    return _aware(unlocked_at) <= _aware(paused_at)


def shifted(next_review_at: dt.datetime, shift: dt.timedelta) -> dt.datetime:
    """Push a single due date forward by the shift. tz-preserving."""
    return _aware(next_review_at) + shift


def paused_days(paused_at: dt.datetime, now: dt.datetime) -> int:
    """Whole days elapsed since the pause began (for display). Never negative."""
    delta = _aware(now) - _aware(paused_at)
    return max(0, delta.days)

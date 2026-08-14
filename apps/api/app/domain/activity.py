"""Review-activity bucketing (slice 46) — pure functions.

Turns a list of review timestamps into fixed-length series the dashboard graph
can draw: 7 daily buckets (six days ago → today) and 24 hourly buckets (23 hours
ago → this hour). No DB, no I/O — unit-testable. Buckets are computed in UTC;
threading the user's timezone through is a later refinement (R-131).
"""
from __future__ import annotations

import datetime as dt

WEEKDAY = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _aware(t: dt.datetime) -> dt.datetime:
    return t if t.tzinfo is not None else t.replace(tzinfo=dt.timezone.utc)


def _floor_day(t: dt.datetime) -> dt.datetime:
    return _aware(t).replace(hour=0, minute=0, second=0, microsecond=0)


def _floor_hour(t: dt.datetime) -> dt.datetime:
    return _aware(t).replace(minute=0, second=0, microsecond=0)


def seven_day_buckets(timestamps: list[dt.datetime], now: dt.datetime) -> list[dict]:
    """Seven daily buckets, oldest first, today last."""
    today = _floor_day(now)
    days = [today - dt.timedelta(days=6 - i) for i in range(7)]
    counts = {d: 0 for d in days}
    for t in timestamps:
        d = _floor_day(t)
        if d in counts:
            counts[d] += 1
    return [
        {"label": WEEKDAY[d.weekday()], "count": counts[d], "iso": d.isoformat()}
        for d in days
    ]


def twenty_four_hour_buckets(timestamps: list[dt.datetime], now: dt.datetime) -> list[dict]:
    """Twenty-four hourly buckets, oldest first, current hour last."""
    current = _floor_hour(now)
    hours = [current - dt.timedelta(hours=23 - i) for i in range(24)]
    counts = {h: 0 for h in hours}
    for t in timestamps:
        h = _floor_hour(t)
        if h in counts:
            counts[h] += 1
    return [
        {"label": f"{h.hour:02d}", "count": counts[h], "iso": h.isoformat()}
        for h in hours
    ]


def activity_series(timestamps: list[dt.datetime], now: dt.datetime) -> dict:
    """Both series in the shape the API returns."""
    day_window = [t for t in timestamps if _aware(t) >= _aware(now) - dt.timedelta(hours=24)]
    return {
        "seven_day": seven_day_buckets(timestamps, now),
        "twenty_four_hour": twenty_four_hour_buckets(day_window, now),
    }

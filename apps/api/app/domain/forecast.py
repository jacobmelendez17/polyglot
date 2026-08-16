"""Review forecast (slice 47) — pure functions over upcoming `next_review_at`s.

Two shapes the dashboard needs, both looking forward from *now*:

  * daily_buckets  — the next 7 days: today, then the following six by weekday.
                     Each day carries a 24-slot hourly breakdown so the bar graph
                     can drill into a day.
  * rolling_24h    — the next 24 hours, hour by hour starting from the current
                     hour, for the line graph's 24-hour view.

Only reviews due in the window [now, now+7d) count — overdue ("due now") items
are not part of a forecast. No DB, no I/O; unit-testable. UTC buckets (R-131).
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


def daily_buckets(next_reviews: list[dt.datetime], now: dt.datetime) -> list[dict]:
    """Seven days from today. Day 0 counts from `now` (upcoming today); each day
    includes a 24-slot hourly breakdown indexed by hour-of-day."""
    now = _aware(now)
    today = _floor_day(now)
    out: list[dict] = []
    for offset in range(7):
        day_start = today + dt.timedelta(days=offset)
        day_end = day_start + dt.timedelta(days=1)
        window_start = now if offset == 0 else day_start
        hours = [0] * 24
        count = 0
        for t in next_reviews:
            ta = _aware(t)
            if window_start <= ta < day_end:
                hours[ta.hour] += 1
                count += 1
        label = "today" if offset == 0 else WEEKDAY[day_start.weekday()]
        out.append({
            "offset": offset, "label": label, "date": day_start.date().isoformat(),
            "count": count, "hours": hours,
        })
    return out


def rolling_24h(next_reviews: list[dt.datetime], now: dt.datetime) -> list[dict]:
    """Twenty-four hourly buckets starting from the current hour."""
    base = _floor_hour(now)
    counts = [0] * 24
    for t in next_reviews:
        delta = int((_floor_hour(t) - base).total_seconds() // 3600)
        if 0 <= delta < 24:
            counts[delta] += 1
    return [
        {"label": f"{(base + dt.timedelta(hours=i)).hour:02d}", "count": counts[i]}
        for i in range(24)
    ]


def forecast_payload(next_reviews: list[dt.datetime], now: dt.datetime) -> dict:
    return {
        "days": daily_buckets(next_reviews, now),
        "next_24h": rolling_24h(next_reviews, now),
    }

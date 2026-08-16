"""Unit tests for review forecast bucketing (slice 47)."""
import datetime as dt

from app.domain.forecast import daily_buckets, forecast_payload, rolling_24h

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 8, 13, 14, 30, tzinfo=UTC)  # Thursday 14:30


def test_daily_is_seven_today_then_weekdays():
    days = daily_buckets([], NOW)
    assert len(days) == 7
    assert days[0]["label"] == "today"
    assert days[1]["label"] == "fri"
    assert days[2]["label"] == "sat"
    assert len(days[0]["hours"]) == 24


def test_daily_counts_and_window():
    revs = [
        NOW.replace(hour=16),                          # today, upcoming → counted
        NOW.replace(hour=10),                          # today, before now → excluded
        (NOW + dt.timedelta(days=1)).replace(hour=9),  # fri
        NOW + dt.timedelta(days=6),                    # last day
        NOW + dt.timedelta(days=7),                    # outside window → excluded
    ]
    days = daily_buckets(revs, NOW)
    assert days[0]["count"] == 1 and days[0]["hours"][16] == 1
    assert days[1]["count"] == 1 and days[1]["hours"][9] == 1
    assert days[6]["count"] == 1
    assert sum(d["count"] for d in days) == 3


def test_rolling_24h_from_current_hour():
    r = rolling_24h([
        NOW + dt.timedelta(hours=1),
        NOW + dt.timedelta(hours=1),
        NOW + dt.timedelta(hours=23),
        NOW + dt.timedelta(hours=24),   # excluded
        NOW - dt.timedelta(hours=1),    # overdue, excluded
    ], NOW)
    assert len(r) == 24
    assert r[0]["label"] == "14"
    assert r[1]["count"] == 2
    assert r[23]["count"] == 1
    assert sum(b["count"] for b in r) == 3


def test_payload_shape():
    p = forecast_payload([NOW + dt.timedelta(hours=2)], NOW)
    assert set(p) == {"days", "next_24h"}
    assert len(p["days"]) == 7 and len(p["next_24h"]) == 24


def test_naive_timestamps_tolerated():
    daily_buckets([dt.datetime(2026, 8, 13, 16, 0)], NOW)  # no raise

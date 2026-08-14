"""Unit tests for review-activity bucketing (slice 46)."""
import datetime as dt

from app.domain.activity import (
    activity_series,
    seven_day_buckets,
    twenty_four_hour_buckets,
)

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 8, 13, 14, 30, tzinfo=UTC)  # Thursday 14:30


def test_seven_day_is_fixed_length_today_last():
    b = seven_day_buckets([], NOW)
    assert len(b) == 7
    assert b[-1]["label"] == "thu"
    assert all(x["count"] == 0 for x in b)


def test_seven_day_counts_and_window():
    ts = [
        NOW, NOW - dt.timedelta(hours=1),      # today: 2
        NOW - dt.timedelta(days=1),            # yesterday: 1
        NOW - dt.timedelta(days=6),            # oldest in window: 1
        NOW - dt.timedelta(days=7),            # just outside: excluded
    ]
    b = seven_day_buckets(ts, NOW)
    assert b[-1]["count"] == 2
    assert b[-2]["count"] == 1
    assert b[0]["count"] == 1
    assert sum(x["count"] for x in b) == 4


def test_twenty_four_hour_is_fixed_length_current_last():
    b = twenty_four_hour_buckets([], NOW)
    assert len(b) == 24
    assert b[-1]["label"] == "14"


def test_twenty_four_hour_counts_and_window():
    ts = [
        NOW, NOW,                              # this hour: 2
        NOW - dt.timedelta(hours=1),           # last hour: 1
        NOW - dt.timedelta(hours=23),          # oldest in window: 1
        NOW - dt.timedelta(hours=24),          # just outside: excluded
    ]
    b = twenty_four_hour_buckets(ts, NOW)
    assert b[-1]["count"] == 2
    assert b[-2]["count"] == 1
    assert b[0]["count"] == 1
    assert sum(x["count"] for x in b) == 4


def test_naive_timestamps_are_tolerated():
    seven_day_buckets([dt.datetime(2026, 8, 13, 10, 0)], NOW)  # no raise


def test_activity_series_shape():
    s = activity_series([NOW], NOW)
    assert set(s) == {"seven_day", "twenty_four_hour"}
    assert len(s["seven_day"]) == 7 and len(s["twenty_four_hour"]) == 24

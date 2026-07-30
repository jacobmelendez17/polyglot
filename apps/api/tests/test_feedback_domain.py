"""Feedback rules — pure functions."""
import datetime as dt

from app.domain.feedback import (
    BODY_MAX,
    MAX_IN_WINDOW,
    can_submit,
    is_valid_body,
    normalize_category,
    sanitize_body,
    sanitize_meta,
)

NOW = dt.datetime(2026, 7, 27, 12, 0, tzinfo=dt.timezone.utc)


def test_body_is_sanitized():
    assert sanitize_body("<script>alert(1)</script>broken") == "alert(1)broken"
    assert "<" not in sanitize_body("a <b>bold</b> c")


def test_meta_is_a_single_capped_line():
    assert sanitize_meta("/dashboard\n\tweird", max_length=300) == "/dashboard weird"
    assert len(sanitize_meta("x" * 999, max_length=300)) == 300


def test_category_normalizes_to_known_values():
    assert normalize_category("BUG") == "bug"
    assert normalize_category("feature") == "feature"
    assert normalize_category("garbage") == "other"
    assert normalize_category(None) == "other"


def test_body_validity():
    assert is_valid_body("something")
    assert not is_valid_body("   ")
    assert len(sanitize_body("y" * (BODY_MAX + 100))) == BODY_MAX


def test_rate_limit():
    assert can_submit([NOW] * (MAX_IN_WINDOW - 1), NOW)
    assert not can_submit([NOW] * MAX_IN_WINDOW, NOW)
    # old ones don't count
    assert can_submit([NOW - dt.timedelta(hours=2)] * 10, NOW)


def test_rate_limit_tolerates_naive_datetimes():
    naive = NOW.replace(tzinfo=None)
    assert can_submit([naive], naive)

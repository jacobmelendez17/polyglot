"""Forum rules — pure functions (sanitization, rate limiting, moderation)."""
import datetime as dt

import pytest

from app.domain.forum import (
    BODY_MAX,
    POST_MAX_IN_WINDOW,
    REPORT_AUTO_HIDE_THRESHOLD,
    TITLE_MAX,
    can_post,
    is_valid_body,
    is_valid_reason,
    is_valid_title,
    recent_count,
    sanitize_body,
    sanitize_title,
    seconds_until_can_post,
    should_auto_hide,
    slugify,
)

NOW = dt.datetime(2026, 7, 26, 12, 0, tzinfo=dt.timezone.utc)


# --- sanitization ---------------------------------------------------------

def test_html_tags_are_stripped():
    """The classic stored-XSS vector — removed before it's ever stored."""
    assert sanitize_body("<script>alert(1)</script>hola") == "alert(1)hola"
    assert sanitize_body("<b>bold</b> and <i>it</i>") == "bold and it"
    assert "<" not in sanitize_body("a <img src=x onerror=y> b")


def test_control_characters_are_dropped():
    assert sanitize_body("\x00\x07\x1fhi") == "hi"


def test_title_is_a_single_collapsed_line():
    assert sanitize_title("  many   spaces\n\there ") == "many spaces here"


def test_body_collapses_runaway_blank_lines():
    assert sanitize_body("a\n\n\n\n\n\nb") == "a\n\nb"


def test_lengths_are_capped():
    assert len(sanitize_title("x" * 999)) == TITLE_MAX
    assert len(sanitize_body("y" * (BODY_MAX + 500))) == BODY_MAX


def test_validity_checks():
    assert is_valid_title("hi") and not is_valid_title("   ")
    assert is_valid_body("something") and not is_valid_body("")


def test_sanitize_tolerates_non_strings():
    assert sanitize_body(None) == ""
    assert sanitize_title(None) == ""


# --- rate limiting --------------------------------------------------------

def test_under_the_limit_can_post():
    times = [NOW - dt.timedelta(minutes=i) for i in range(POST_MAX_IN_WINDOW - 1)]
    assert can_post(times, NOW)


def test_at_the_limit_is_blocked():
    times = [NOW - dt.timedelta(minutes=i) for i in range(POST_MAX_IN_WINDOW)]
    assert not can_post(times, NOW)


def test_posts_outside_the_window_do_not_count():
    old = [NOW - dt.timedelta(hours=1) for _ in range(POST_MAX_IN_WINDOW + 3)]
    assert can_post(old, NOW)
    assert recent_count(old, NOW) == 0


def test_seconds_until_can_post_is_zero_when_free():
    assert seconds_until_can_post([], NOW) == 0


def test_seconds_until_can_post_counts_down_the_oldest():
    # Six posts, the oldest 9 minutes ago; window is 10 → ~1 minute until free.
    times = [NOW - dt.timedelta(minutes=m) for m in (9, 7, 5, 3, 2, 1)]
    wait = seconds_until_can_post(times, NOW)
    assert 0 < wait <= 61


def test_rate_limit_tolerates_naive_datetimes():
    naive = NOW.replace(tzinfo=None)
    assert can_post([naive], naive)


# --- reports --------------------------------------------------------------

def test_auto_hide_at_threshold():
    assert not should_auto_hide(REPORT_AUTO_HIDE_THRESHOLD - 1)
    assert should_auto_hide(REPORT_AUTO_HIDE_THRESHOLD)
    assert should_auto_hide(REPORT_AUTO_HIDE_THRESHOLD + 5)


def test_valid_reasons():
    assert is_valid_reason("spam") and is_valid_reason("abuse")
    assert not is_valid_reason("whatever") and not is_valid_reason(None)


# --- slugs ----------------------------------------------------------------

def test_slugify():
    assert slugify("Grammar Help") == "grammar-help"
    assert slugify("¿Cómo estás?") == "c-mo-est-s"
    assert slugify("") == "untitled"
    assert slugify("Multiple   Spaces!!!") == "multiple-spaces"

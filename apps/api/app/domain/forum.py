"""Forum rules — pure functions (spec §18).

Everything a forum needs to be *safe* before it needs to be *featureful* lives
here, with no database and no clock of its own, so each rule is a deterministic
unit test:

  * **Sanitization.** User-generated content is the classic stored-XSS vector.
    We strip HTML rather than trust it, collapse runaway whitespace, and drop
    control characters. The frontend renders the result as text (never
    innerHTML), so this is defense in depth, not the only line.
  * **Rate limiting.** Spam is the other forum failure mode. `can_post` answers
    "has this person posted too much, too fast?" from their recent post times —
    the edge limiter (Cloudflare/Upstash) is the first wall; this is the second,
    per-user and content-aware.
  * **Auto-hide on reports.** A post that enough people flag is hidden pending a
    moderator, so the crowd can't be forced to look at abuse while waiting for a
    human — but nothing is ever *deleted* by report count alone.
"""
from __future__ import annotations

import datetime as dt
import re

# --- limits ---------------------------------------------------------------

TITLE_MAX = 160
BODY_MAX = 10_000
BODY_MIN = 1

# A person may create at most this many posts (threads + replies combined)
# within the rolling window. Slow enough to stop a flood, generous enough that
# a real conversation never trips it.
POST_MAX_IN_WINDOW = 6
POST_WINDOW = dt.timedelta(minutes=10)

# How many distinct reports hide a post pending moderation.
REPORT_AUTO_HIDE_THRESHOLD = 3

REPORT_REASONS = ("spam", "abuse", "off_topic", "other")

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def _strip(raw: object) -> str:
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    text = _TAG_RE.sub("", text)          # remove any HTML tags outright
    text = _CONTROL_RE.sub("", text)      # drop control characters
    return text


def sanitize_title(raw: object) -> str:
    """A single clean line, no markup, collapsed whitespace."""
    text = _strip(raw).replace("\n", " ").replace("\r", " ")
    text = _SPACES_RE.sub(" ", text).strip()
    return text[:TITLE_MAX]


def sanitize_body(raw: object) -> str:
    """Multi-line clean text: tags stripped, whitespace tamed, length capped."""
    text = _strip(raw).replace("\r\n", "\n").replace("\r", "\n")
    # collapse runs of spaces/tabs per line, then trim each line's trailing space
    text = "\n".join(_SPACES_RE.sub(" ", line).rstrip() for line in text.split("\n"))
    text = _BLANKLINES_RE.sub("\n\n", text).strip()
    return text[:BODY_MAX]


def is_valid_body(text: str) -> bool:
    return BODY_MIN <= len(text.strip()) <= BODY_MAX


def is_valid_title(text: str) -> bool:
    return 1 <= len(text.strip()) <= TITLE_MAX


# --- rate limiting --------------------------------------------------------

def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def recent_count(
    post_times: list[dt.datetime], now: dt.datetime, *, window: dt.timedelta = POST_WINDOW,
) -> int:
    cutoff = _aware(now) - window
    return sum(1 for t in post_times if _aware(t) >= cutoff)


def can_post(
    post_times: list[dt.datetime], now: dt.datetime, *,
    max_in_window: int = POST_MAX_IN_WINDOW, window: dt.timedelta = POST_WINDOW,
) -> bool:
    """True if the person is under the rolling post limit."""
    return recent_count(post_times, now, window=window) < max_in_window


def seconds_until_can_post(
    post_times: list[dt.datetime], now: dt.datetime, *,
    max_in_window: int = POST_MAX_IN_WINDOW, window: dt.timedelta = POST_WINDOW,
) -> int:
    """How long until the oldest in-window post ages out enough to post again.

    0 when the person can post now. Used for a friendly "try again in N seconds".
    """
    now = _aware(now)
    cutoff = now - window
    in_window = sorted(_aware(t) for t in post_times if _aware(t) >= cutoff)
    if len(in_window) < max_in_window:
        return 0
    # The (max_in_window)th-most-recent post must leave the window.
    oldest_relevant = in_window[len(in_window) - max_in_window]
    free_at = oldest_relevant + window
    return max(0, int((free_at - now).total_seconds()) + 1)


# --- reports / moderation -------------------------------------------------

def is_valid_reason(reason: object) -> bool:
    return isinstance(reason, str) and reason in REPORT_REASONS


def should_auto_hide(
    report_count: int, *, threshold: int = REPORT_AUTO_HIDE_THRESHOLD,
) -> bool:
    """Enough distinct reports hide a post pending a moderator — never delete."""
    return int(report_count or 0) >= threshold


# --- slugs ----------------------------------------------------------------

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, *, max_length: int = 60) -> str:
    """A URL-safe slug for a category or thread title."""
    slug = _SLUG_STRIP.sub("-", (text or "").lower()).strip("-")
    return slug[:max_length].strip("-") or "untitled"

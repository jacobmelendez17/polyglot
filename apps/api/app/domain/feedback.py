"""Feedback rules — pure functions (spec §22, §30).

A support/feedback message is user-generated content that gets stored, shown to
an admin, and emailed — so the same two hazards as forum posts apply: it must be
sanitized, and it must be rate-limited so one person can't flood the inbox. This
module holds both as deterministic, testable rules, plus the small category
vocabulary the form offers.
"""
from __future__ import annotations

import datetime as dt
import re

CATEGORIES = ("bug", "feature", "question", "other")

BODY_MAX = 5_000
BODY_MIN = 1
ROUTE_MAX = 300
BROWSER_MAX = 300

# A person may file at most this many tickets in the rolling window. Feedback is
# lower-frequency than forum posting, so the window is wider and the count lower.
MAX_IN_WINDOW = 5
WINDOW = dt.timedelta(minutes=30)

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES_RE = re.compile(r"[ \t]+")
_BLANKLINES_RE = re.compile(r"\n{3,}")


def _clean(raw: object, *, one_line: bool = False) -> str:
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))
    text = _TAG_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    if one_line:
        text = text.replace("\n", " ").replace("\r", " ")
    else:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def sanitize_body(raw: object) -> str:
    text = _clean(raw)
    text = "\n".join(_SPACES_RE.sub(" ", line).rstrip() for line in text.split("\n"))
    text = _BLANKLINES_RE.sub("\n\n", text).strip()
    return text[:BODY_MAX]


def sanitize_meta(raw: object, *, max_length: int) -> str:
    """Route/browser strings: a single clean line, length-capped. These come from
    the client and are shown to an admin, so they're sanitized like any input."""
    text = _SPACES_RE.sub(" ", _clean(raw, one_line=True)).strip()
    return text[:max_length]


def normalize_category(raw: object) -> str:
    text = (raw if isinstance(raw, str) else "").strip().lower()
    return text if text in CATEGORIES else "other"


def is_valid_body(text: str) -> bool:
    return BODY_MIN <= len(text.strip()) <= BODY_MAX


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def can_submit(
    times: list[dt.datetime], now: dt.datetime, *,
    max_in_window: int = MAX_IN_WINDOW, window: dt.timedelta = WINDOW,
) -> bool:
    cutoff = _aware(now) - window
    recent = sum(1 for t in times if _aware(t) >= cutoff)
    return recent < max_in_window

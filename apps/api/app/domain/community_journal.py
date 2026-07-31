"""Community journals — pure rules (spec §7).

Journals are private by default. A user may *share* an entry to the community for
feedback, and unshare it at any time. The one rule this module exists to protect —
and the reason it's a pure, exhaustively-tested function — is the visibility
invariant: **a journal that hasn't been shared must never be visible to anyone but
its owner.** Everything else (sharing, feedback, moderation) is built on top of it.

`can_view_shared_entry` is the single gate the community endpoints consult. It's
deliberately conservative: the default answer is "no," and access is granted only
by an explicit share (or by being the owner). Nothing here trusts a client-supplied
identity — the caller passes the owner id and the authenticated viewer id, and this
function only compares them.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

FEEDBACK_MAX = 3000
# Feedback posting cap: generous for a real conversation, tight enough to blunt spam.
RATE_LIMIT = 8
RATE_WINDOW = dt.timedelta(minutes=10)

_TAG = re.compile(r"<[^>]*>")
_WS = re.compile(r"[ \t\r\f\v]+")


def can_view_shared_entry(
    *, owner_id: uuid.UUID, viewer_id: uuid.UUID | None,
    shared: bool, share_hidden: bool, viewer_is_mod: bool,
) -> bool:
    """The visibility gate. Owner always sees their own entry; a private entry is
    visible to no one else; a shared entry is visible to the community unless a
    moderator has hidden it, in which case only moderators can still review it."""
    if viewer_id is not None and viewer_id == owner_id:
        return True            # your own journal is always yours to see
    if not shared:
        return False           # private — never leaks
    if share_hidden:
        return viewer_is_mod   # mod-removed from the feed; only mods may review
    return True                # shared and visible → the community can read it


def is_in_feed(*, shared: bool, share_hidden: bool) -> bool:
    """Whether a shared entry belongs in the public community feed."""
    return shared and not share_hidden


def sanitize(text: str) -> str:
    """Strip any markup and collapse horizontal whitespace. User feedback is
    rendered as plain text; this makes sure no stored markup can be interpreted."""
    text = _TAG.sub("", text or "")
    # collapse runs of spaces/tabs but keep newlines (paragraphs survive)
    text = "\n".join(_WS.sub(" ", line).strip() for line in text.splitlines())
    return text.strip()


def validate_feedback(body: str) -> str:
    """Sanitize and bound a feedback body. Raises ValueError on empty/oversize."""
    cleaned = sanitize(body)
    if not cleaned:
        raise ValueError("Feedback can't be empty.")
    if len(cleaned) > FEEDBACK_MAX:
        raise ValueError(f"Feedback is too long (max {FEEDBACK_MAX} characters).")
    return cleaned


def within_rate_limit(
    recent: list[dt.datetime], now: dt.datetime, *,
    limit: int = RATE_LIMIT, window: dt.timedelta = RATE_WINDOW,
) -> bool:
    """True if another post is allowed: fewer than `limit` posts in the last window."""
    cutoff = now - window
    count = sum(1 for t in recent if t and t >= cutoff)
    return count < limit


def excerpt(body: str, n: int = 240) -> str:
    body = (body or "").strip()
    if len(body) <= n:
        return body
    return body[:n].rstrip() + "…"

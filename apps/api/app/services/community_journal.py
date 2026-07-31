"""Community journals service (spec §7).

Sharing is a `visibility` transition on the user's own entry: "private" ↔
"community". Every read of another user's entry passes through the visibility gate
in `domain.community_journal`, so a private entry can never leak. Feedback is only
allowed on entries that are currently shared and visible, is sanitized and
rate-limited, and can be hidden (not deleted) by a moderator.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import community_journal as rules
from app.models.community_journal import JournalFeedback
from app.models.identity import Profile
from app.models.progress import JournalEntry

SHARED = "community"
PRIVATE = "private"


class CommunityJournalError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _is_shared(entry: JournalEntry) -> bool:
    return entry.visibility == SHARED


def _iso(v: dt.datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=dt.timezone.utc)
    return v.isoformat()


def _display_name(db: Session, user_id: uuid.UUID) -> str:
    profile = db.get(Profile, user_id)
    name = (profile.display_name or "").strip() if profile else ""
    return name or "someone"


def _get_owned(db: Session, user_id: uuid.UUID, entry_id: str) -> JournalEntry:
    try:
        eid = uuid.UUID(str(entry_id))
    except (ValueError, AttributeError):
        raise CommunityJournalError("Entry not found.", "not_found", 404) from None
    entry = db.get(JournalEntry, eid)
    if entry is None or entry.user_id != user_id:
        raise CommunityJournalError("Entry not found.", "not_found", 404)
    return entry


# --- owner: share / unshare / list own -------------------------------------

def share(db: Session, *, user_id: uuid.UUID, entry_id: str,
          now: dt.datetime | None = None) -> dict:
    now = now or _now()
    entry = _get_owned(db, user_id, entry_id)
    if not (entry.body or "").strip():
        raise CommunityJournalError("Write something before sharing.", "empty", 400)
    entry.visibility = SHARED
    if entry.shared_at is None:
        entry.shared_at = now
    entry.share_hidden = False  # a fresh share is visible; a prior mod-hide is cleared
    db.flush()
    return {"id": str(entry.id), "shared": True}


def unshare(db: Session, *, user_id: uuid.UUID, entry_id: str) -> dict:
    entry = _get_owned(db, user_id, entry_id)
    entry.visibility = PRIVATE
    entry.shared_at = None
    db.flush()
    return {"id": str(entry.id), "shared": False}


def my_entries(db: Session, *, user_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(JournalEntry).where(
            JournalEntry.user_id == user_id, JournalEntry.archived_at.is_(None),
        ).order_by(JournalEntry.created_at.desc())
    ).scalars().all()
    out = []
    for e in rows:
        shared = _is_shared(e)
        out.append({
            "id": str(e.id),
            "title": e.title or "",
            "excerpt": rules.excerpt(e.body),
            "shared": shared,
            "share_hidden": bool(e.share_hidden),
            "shared_at": _iso(e.shared_at),
            "feedback_count": _feedback_count(db, e.id) if shared else 0,
        })
    return out


# --- community: feed / read ------------------------------------------------

def _feedback_count(db: Session, entry_id: uuid.UUID) -> int:
    return len(db.execute(
        select(JournalFeedback.id).where(
            JournalFeedback.entry_id == entry_id, JournalFeedback.hidden.is_(False))
    ).scalars().all())


def community_feed(db: Session, *, limit: int = 30) -> list[dict]:
    rows = db.execute(
        select(JournalEntry).where(
            JournalEntry.visibility == SHARED,
            JournalEntry.share_hidden.is_(False),
        ).order_by(JournalEntry.shared_at.desc()).limit(limit)
    ).scalars().all()
    return [{
        "id": str(e.id),
        "author": _display_name(db, e.user_id),
        "title": e.title or "",
        "excerpt": rules.excerpt(e.body),
        "shared_at": _iso(e.shared_at),
        "feedback_count": _feedback_count(db, e.id),
    } for e in rows]


def get_shared_entry(db: Session, *, viewer_id: uuid.UUID, viewer_is_mod: bool,
                     entry_id: str) -> dict:
    try:
        eid = uuid.UUID(str(entry_id))
    except (ValueError, AttributeError):
        raise CommunityJournalError("Entry not found.", "not_found", 404) from None
    entry = db.get(JournalEntry, eid)
    if entry is None:
        raise CommunityJournalError("Entry not found.", "not_found", 404)
    if not rules.can_view_shared_entry(
        owner_id=entry.user_id, viewer_id=viewer_id, shared=_is_shared(entry),
        share_hidden=bool(entry.share_hidden), viewer_is_mod=viewer_is_mod,
    ):
        # Don't reveal existence of a private entry — same 404 as "no such entry".
        raise CommunityJournalError("Entry not found.", "not_found", 404)

    fb_rows = db.execute(
        select(JournalFeedback).where(JournalFeedback.entry_id == entry.id)
        .order_by(JournalFeedback.created_at)
    ).scalars().all()
    feedback = [{
        "id": str(f.id),
        "author": _display_name(db, f.author_id),
        "body": f.body,
        "hidden": bool(f.hidden),
        "created_at": _iso(f.created_at),
    } for f in fb_rows if (not f.hidden) or viewer_is_mod]

    return {
        "id": str(entry.id),
        "author": _display_name(db, entry.user_id),
        "title": entry.title or "",
        "body": entry.body or "",
        "shared_at": _iso(entry.shared_at),
        "share_hidden": bool(entry.share_hidden),
        "is_owner": viewer_id == entry.user_id,
        "feedback": feedback,
    }


# --- community: feedback ----------------------------------------------------

def post_feedback(db: Session, *, author_id: uuid.UUID, entry_id: str, body: str,
                  now: dt.datetime | None = None) -> dict:
    now = now or _now()
    try:
        eid = uuid.UUID(str(entry_id))
    except (ValueError, AttributeError):
        raise CommunityJournalError("Entry not found.", "not_found", 404) from None
    entry = db.get(JournalEntry, eid)
    # Feedback is only for entries that are actually shared and visible.
    if entry is None or not rules.is_in_feed(
        shared=_is_shared(entry), share_hidden=bool(entry.share_hidden)
    ):
        raise CommunityJournalError("This entry isn't open for feedback.", "not_shared", 404)

    try:
        clean = rules.validate_feedback(body)
    except ValueError as e:
        raise CommunityJournalError(str(e), "invalid", 422) from e

    recent = db.execute(
        select(JournalFeedback.created_at).where(JournalFeedback.author_id == author_id)
        .order_by(JournalFeedback.created_at.desc()).limit(rules.RATE_LIMIT)
    ).scalars().all()
    if not rules.within_rate_limit(list(recent), now):
        raise CommunityJournalError("You're posting too fast — take a breather.",
                                    "rate_limited", 429)

    fb = JournalFeedback(entry_id=eid, author_id=author_id, body=clean)
    db.add(fb)
    db.flush()
    return {"id": str(fb.id), "author": _display_name(db, author_id),
            "body": clean, "hidden": False, "created_at": _iso(fb.created_at)}


# --- moderation (forum_moderate) -------------------------------------------

def set_feedback_hidden(db: Session, *, feedback_id: str, hidden: bool,
                        reason: str | None = None) -> dict:
    try:
        fid = uuid.UUID(str(feedback_id))
    except (ValueError, AttributeError):
        raise CommunityJournalError("Feedback not found.", "not_found", 404) from None
    fb = db.get(JournalFeedback, fid)
    if fb is None:
        raise CommunityJournalError("Feedback not found.", "not_found", 404)
    fb.hidden = hidden
    fb.hidden_reason = reason if hidden else None
    db.flush()
    return {"id": str(fb.id), "hidden": hidden}


def set_entry_hidden(db: Session, *, entry_id: str, hidden: bool,
                     reason: str | None = None) -> dict:
    try:
        eid = uuid.UUID(str(entry_id))
    except (ValueError, AttributeError):
        raise CommunityJournalError("Entry not found.", "not_found", 404) from None
    entry = db.get(JournalEntry, eid)
    if entry is None:
        raise CommunityJournalError("Entry not found.", "not_found", 404)
    entry.share_hidden = hidden
    entry.share_hidden_reason = reason if hidden else None
    db.flush()
    return {"id": str(entry.id), "share_hidden": hidden}

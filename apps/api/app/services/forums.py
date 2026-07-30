"""Forum service (spec §18).

The read path is public: anyone can browse categories, threads, and replies —
that's the "available to go on without anyone being able to post" requirement.
Hidden and deleted content is filtered out for everyone except a moderator.

The write path is gated three ways, in order:
  1. Is posting enabled at all? (the global switch — off by default, §18)
  2. Is this category open? (a category can be individually locked)
  3. Is this person under the rate limit? (spam control, per-user)

...and every stored string is sanitized first. Moderation (hide / delete /
restore) is capability-gated at the route and audit-logged here.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.domain import forum as rules
from app.models.forum import (
    ForumCategory,
    ForumReply,
    ForumReport,
    ForumThread,
)
from app.models.identity import Profile, User
from app.models.platform import AdminAuditLog

MAX_PAGE = 50


class ForumError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def _uuid(value: str, what: str = "item") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise ForumError(f"{what.capitalize()} not found.", "not_found", 404) from None


# --- posting gate ---------------------------------------------------------

def _posting_enabled(settings) -> bool:
    return bool(getattr(settings, "forums_posting_enabled", False))


def _assert_can_post(
    db: Session, *, user_id: uuid.UUID, category: ForumCategory, settings,
    now: dt.datetime,
) -> None:
    if not _posting_enabled(settings):
        raise ForumError(
            "The forums are read-only right now. Posting opens soon.",
            "posting_disabled", 403,
        )
    if category.locked:
        raise ForumError("This category is locked.", "category_locked", 403)

    # Rate limit: count this user's recent threads + replies.
    since = now - rules.POST_WINDOW
    thread_times = db.execute(
        select(ForumThread.created_at).where(
            ForumThread.author_id == user_id, ForumThread.created_at >= since,
        )
    ).scalars().all()
    reply_times = db.execute(
        select(ForumReply.created_at).where(
            ForumReply.author_id == user_id, ForumReply.created_at >= since,
        )
    ).scalars().all()
    post_times = [t for t in (*thread_times, *reply_times) if t is not None]
    if not rules.can_post(post_times, now):
        wait = rules.seconds_until_can_post(post_times, now)
        raise ForumError(
            f"You're posting quite fast — try again in about {wait} seconds.",
            "rate_limited", 429,
        )


# --- reads ----------------------------------------------------------------

def list_categories(db: Session) -> list[dict]:
    rows = db.execute(
        select(ForumCategory).order_by(ForumCategory.position, ForumCategory.title)
    ).scalars().all()

    # Thread counts per category, hidden/deleted excluded.
    counts = dict(db.execute(
        select(ForumThread.category_id, func.count(ForumThread.id)).where(
            ForumThread.hidden_at.is_(None), ForumThread.deleted_at.is_(None),
        ).group_by(ForumThread.category_id)
    ).all())

    return [
        {
            "id": str(c.id), "slug": c.slug, "title": c.title,
            "description": c.description or "", "locked": bool(c.locked),
            "thread_count": int(counts.get(c.id, 0)),
        }
        for c in rows
    ]


def _visible_threads(category_id: uuid.UUID, *, include_hidden: bool):
    where = [ForumThread.category_id == category_id, ForumThread.deleted_at.is_(None)]
    if not include_hidden:
        where.append(ForumThread.hidden_at.is_(None))
    return where


def list_threads(
    db: Session, *, slug: str, limit: int = 20, offset: int = 0,
    include_hidden: bool = False,
) -> dict:
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))

    category = db.execute(
        select(ForumCategory).where(ForumCategory.slug == slug)
    ).scalar_one_or_none()
    if category is None:
        raise ForumError("Category not found.", "not_found", 404)

    where = _visible_threads(category.id, include_hidden=include_hidden)
    total = db.execute(
        select(func.count(ForumThread.id)).where(*where)
    ).scalar_one()
    rows = db.execute(
        select(ForumThread, Profile.display_name)
        .outerjoin(Profile, Profile.user_id == ForumThread.author_id)
        .where(*where)
        # pinned first, then most recent activity
        .order_by(ForumThread.pinned.desc(),
                  func.coalesce(ForumThread.last_activity_at, ForumThread.created_at).desc())
        .limit(limit).offset(offset)
    ).all()

    return {
        "category": {"slug": category.slug, "title": category.title,
                    "description": category.description or "", "locked": bool(category.locked)},
        "total": int(total or 0), "limit": limit, "offset": offset,
        "threads": [_thread_summary(t, name) for t, name in rows],
    }


def _thread_summary(t: ForumThread, author_name: str | None) -> dict:
    return {
        "id": str(t.id), "title": t.title, "slug": t.slug,
        "author": author_name or "someone",
        "reply_count": int(t.reply_count or 0),
        "pinned": bool(t.pinned), "locked": bool(t.locked),
        "hidden": t.hidden_at is not None,
        "created_at": _iso(t.created_at),
        "last_activity_at": _iso(t.last_activity_at or t.created_at),
    }


def get_thread(
    db: Session, *, thread_id: str, limit: int = 50, offset: int = 0,
    include_hidden: bool = False,
) -> dict:
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))
    tid = _uuid(thread_id, "thread")

    thread = db.get(ForumThread, tid)
    if thread is None or thread.deleted_at is not None or (
        thread.hidden_at is not None and not include_hidden
    ):
        raise ForumError("Thread not found.", "not_found", 404)

    author = db.get(Profile, thread.author_id)
    category = db.get(ForumCategory, thread.category_id)

    where = [ForumReply.thread_id == tid, ForumReply.deleted_at.is_(None)]
    if not include_hidden:
        where.append(ForumReply.hidden_at.is_(None))
    total = db.execute(select(func.count(ForumReply.id)).where(*where)).scalar_one()
    reply_rows = db.execute(
        select(ForumReply, Profile.display_name)
        .outerjoin(Profile, Profile.user_id == ForumReply.author_id)
        .where(*where).order_by(ForumReply.created_at).limit(limit).offset(offset)
    ).all()

    return {
        "id": str(thread.id), "title": thread.title, "body": thread.body or "",
        "author": author.display_name if author else "someone",
        "category": {"slug": category.slug, "title": category.title} if category else None,
        "pinned": bool(thread.pinned), "locked": bool(thread.locked),
        "hidden": thread.hidden_at is not None,
        "created_at": _iso(thread.created_at),
        "reply_total": int(total or 0), "limit": limit, "offset": offset,
        "replies": [
            {
                "id": str(r.id), "body": r.body or "",
                "author": name or "someone",
                "hidden": r.hidden_at is not None,
                "created_at": _iso(r.created_at),
            }
            for r, name in reply_rows
        ],
    }


# --- writes ---------------------------------------------------------------

def create_thread(
    db: Session, *, user_id: uuid.UUID, slug: str, title: str, body: str,
    settings, now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    category = db.execute(
        select(ForumCategory).where(ForumCategory.slug == slug)
    ).scalar_one_or_none()
    if category is None:
        raise ForumError("Category not found.", "not_found", 404)

    _assert_can_post(db, user_id=user_id, category=category, settings=settings, now=now)

    clean_title = rules.sanitize_title(title)
    clean_body = rules.sanitize_body(body)
    if not rules.is_valid_title(clean_title):
        raise ForumError("Give your post a title.", "invalid_title", 400)
    if not rules.is_valid_body(clean_body):
        raise ForumError("Your post needs some content.", "invalid_body", 400)

    thread = ForumThread(
        category_id=category.id, author_id=user_id,
        title=clean_title, slug=rules.slugify(clean_title), body=clean_body,
        last_activity_at=now,
    )
    db.add(thread)
    db.flush()
    return _thread_summary(thread, None) | {"id": str(thread.id)}


def create_reply(
    db: Session, *, user_id: uuid.UUID, thread_id: str, body: str,
    settings, now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    tid = _uuid(thread_id, "thread")
    thread = db.get(ForumThread, tid)
    if thread is None or thread.deleted_at is not None or thread.hidden_at is not None:
        raise ForumError("Thread not found.", "not_found", 404)
    if thread.locked:
        raise ForumError("This thread is locked.", "thread_locked", 403)

    category = db.get(ForumCategory, thread.category_id)
    _assert_can_post(db, user_id=user_id, category=category, settings=settings, now=now)

    clean_body = rules.sanitize_body(body)
    if not rules.is_valid_body(clean_body):
        raise ForumError("Your reply needs some content.", "invalid_body", 400)

    reply = ForumReply(thread_id=tid, author_id=user_id, body=clean_body)
    db.add(reply)
    thread.reply_count = int(thread.reply_count or 0) + 1
    thread.last_activity_at = now
    db.flush()
    return {
        "id": str(reply.id), "body": reply.body, "author": "you",
        "hidden": False, "created_at": _iso(reply.created_at),
    }


# --- reporting ------------------------------------------------------------

def report(
    db: Session, *, user_id: uuid.UUID, target_type: str, target_id: str,
    reason: str, detail: str = "", now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    if target_type not in ("thread", "reply"):
        raise ForumError("Unknown target.", "invalid_target", 400)
    if not rules.is_valid_reason(reason):
        raise ForumError("Choose a valid reason.", "invalid_reason", 400)
    tid = _uuid(target_id, target_type)

    target = db.get(ForumThread if target_type == "thread" else ForumReply, tid)
    if target is None or target.deleted_at is not None:
        raise ForumError(f"{target_type.capitalize()} not found.", "not_found", 404)

    # One report per person per target (unique constraint) — re-reporting no-ops.
    existing = db.execute(
        select(ForumReport).where(
            ForumReport.reporter_id == user_id,
            ForumReport.target_type == target_type,
            ForumReport.target_id == tid,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"reported": True, "already": True,
                "auto_hidden": target.hidden_at is not None}

    db.add(ForumReport(
        reporter_id=user_id, target_type=target_type, target_id=tid,
        reason=rules.sanitize_title(reason), detail=rules.sanitize_body(detail),
    ))
    target.report_count = int(target.report_count or 0) + 1

    # Auto-hide once enough distinct people have flagged it — pending a human.
    auto_hidden = False
    if target.hidden_at is None and rules.should_auto_hide(target.report_count):
        target.hidden_at = now
        auto_hidden = True

    db.flush()
    return {"reported": True, "already": False, "auto_hidden": auto_hidden}


# --- moderation -----------------------------------------------------------

def _audit(db: Session, actor: User, action: str, table: str, target_id: uuid.UUID) -> None:
    db.add(AdminAuditLog(
        actor_id=actor.id, action=action, target_table=table, target_id=target_id,
    ))


def _mod_target(db: Session, target_type: str, target_id: str):
    if target_type not in ("thread", "reply"):
        raise ForumError("Unknown target.", "invalid_target", 400)
    tid = _uuid(target_id, target_type)
    model = ForumThread if target_type == "thread" else ForumReply
    target = db.get(model, tid)
    if target is None:
        raise ForumError(f"{target_type.capitalize()} not found.", "not_found", 404)
    return target, model.__tablename__


def moderate(
    db: Session, *, actor: User, target_type: str, target_id: str, action: str,
    now: dt.datetime | None = None,
) -> dict:
    """Hide, restore, or soft-delete a thread or reply (§18 moderator tools)."""
    now = now or _now()
    target, table = _mod_target(db, target_type, target_id)

    if action == "hide":
        target.hidden_at = now
        target.hidden_by = actor.id
    elif action == "unhide":
        target.hidden_at = None
        target.hidden_by = None
    elif action == "delete":
        target.deleted_at = now      # soft delete, recoverable from the row
    elif action == "restore":
        target.deleted_at = None
    else:
        raise ForumError("Unknown moderation action.", "invalid_action", 400)

    # Mark any open reports on this target resolved.
    db.execute(
        select(ForumReport).where(
            ForumReport.target_type == target_type,
            ForumReport.target_id == target.id,
            ForumReport.resolved_at.is_(None),
        )
    )
    for rep in db.execute(
        select(ForumReport).where(
            ForumReport.target_type == target_type,
            ForumReport.target_id == target.id,
            ForumReport.resolved_at.is_(None),
        )
    ).scalars().all():
        rep.resolved_at = now
        rep.resolved_by = actor.id
        rep.action_taken = action

    _audit(db, actor, f"forum_{action}", table, target.id)
    db.flush()
    return {
        "target_type": target_type, "target_id": str(target.id), "action": action,
        "hidden": target.hidden_at is not None,
        "deleted": target.deleted_at is not None,
    }


def report_queue(db: Session, *, limit: int = 50) -> list[dict]:
    """Open reports, newest first — the moderator's work list."""
    limit = max(1, min(int(limit), MAX_PAGE))
    rows = db.execute(
        select(ForumReport).where(ForumReport.resolved_at.is_(None))
        .order_by(ForumReport.created_at.desc()).limit(limit)
    ).scalars().all()
    return [
        {
            "id": str(r.id), "target_type": r.target_type,
            "target_id": str(r.target_id), "reason": r.reason,
            "detail": r.detail or "", "created_at": _iso(r.created_at),
        }
        for r in rows
    ]

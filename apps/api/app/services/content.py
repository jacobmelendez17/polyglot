"""Intermissions, changelog, and immersion state.

Three small read/write surfaces that share one property: none of them can fail
in a way that blocks learning. An intermission that can't load is skipped, a
changelog that can't load shows empty, and immersion falls back to English.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain import immersion as immersion_rules
from app.domain import intermissions as trigger_rules
from app.models.identity import Profile, UserSettings
from app.models.platform import (
    ChangelogEntry,
    Intermission,
    UserChangelogRead,
    UserIntermissionView,
)
from app.models.progress import UserItemProgress

CHANGELOG_TYPES = ("feature", "fix", "content", "announcement")
MAX_PAGE = 50


class ContentError(Exception):
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


# --- intermissions --------------------------------------------------------

def _progress_context(
    db: Session, user_id: uuid.UUID, *, event: str,
    level: int | None, lesson: int | None,
) -> trigger_rules.TriggerContext:
    """Threshold triggers are evaluated from the database, not from the client.

    The event/level/lesson come from the client (it knows what the learner just
    did), but "how many items have you learned" is ours to answer — otherwise a
    crafted request could unlock every intermission at once.
    """
    learned, highest = db.execute(
        select(
            func.count(UserItemProgress.id).filter(
                UserItemProgress.lesson_completed_at.isnot(None)
            ),
            func.coalesce(func.max(UserItemProgress.srs_stage), 0),
        ).where(UserItemProgress.user_id == user_id)
    ).one()
    return trigger_rules.TriggerContext(
        event=event, level=level, lesson=lesson,
        items_learned=int(learned or 0), highest_stage=int(highest or 0),
    )


def pending_intermissions(
    db: Session, *, user_id: uuid.UUID, event: str,
    level: int | None = None, lesson: int | None = None,
) -> list[dict]:
    if event not in trigger_rules.EVENTS:
        raise ContentError("Unknown event.", "invalid", 400)

    settings = db.get(UserSettings, user_id)
    if settings is not None and not settings.intermissions_enabled:
        return []      # switched off in settings (§17) — respected server-side

    rows = db.execute(
        select(Intermission).where(
            Intermission.status == ContentStatus.published,
            Intermission.deleted_at.is_(None),
        )
    ).scalars().all()
    if not rows:
        return []

    seen = {
        str(v.intermission_id)
        for v in db.execute(
            select(UserIntermissionView).where(
                UserIntermissionView.user_id == user_id,
                UserIntermissionView.viewed_at.isnot(None),
            )
        ).scalars().all()
    }

    ctx = _progress_context(db, user_id, event=event, level=level, lesson=lesson)
    by_id = {str(r.id): r for r in rows}
    candidates = [
        trigger_rules.Candidate(
            id=str(r.id), trigger=r.trigger or {}, title=r.title or "",
            order_hint=int((r.trigger or {}).get("order", 0) or 0)
            if isinstance(r.trigger, dict) else 0,
        )
        for r in rows
    ]
    due = trigger_rules.select_due(candidates, ctx, seen)
    return [_intermission_dict(by_id[c.id]) for c in due]


def _intermission_dict(row: Intermission, viewed_at: dt.datetime | None = None) -> dict:
    return {
        "id": str(row.id),
        "title": row.title or "",
        "body": row.body_rich or "",
        "kind": (row.trigger or {}).get("category", "note")
        if isinstance(row.trigger, dict) else "note",
        "trigger_description": trigger_rules.describe(row.trigger),
        "viewed_at": _iso(viewed_at),
    }


def mark_intermission_viewed(
    db: Session, *, user_id: uuid.UUID, intermission_id: str,
    now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    try:
        pk = uuid.UUID(intermission_id)
    except (ValueError, AttributeError):
        raise ContentError("Intermission not found.", "not_found", 404) from None

    row = db.get(Intermission, pk)
    if row is None or row.deleted_at is not None or row.status != ContentStatus.published:
        raise ContentError("Intermission not found.", "not_found", 404)

    view = db.execute(
        select(UserIntermissionView).where(
            UserIntermissionView.user_id == user_id,
            UserIntermissionView.intermission_id == pk,
        )
    ).scalar_one_or_none()
    if view is None:
        view = UserIntermissionView(user_id=user_id, intermission_id=pk, viewed_at=now)
        db.add(view)
    elif view.viewed_at is None:
        view.viewed_at = now
    db.flush()
    return {"id": str(pk), "viewed_at": _iso(view.viewed_at)}


def intermission_history(
    db: Session, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0,
) -> dict:
    """Everything the learner has already read (§17: a page to revisit them)."""
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))

    base = (
        select(Intermission, UserIntermissionView.viewed_at)
        .join(
            UserIntermissionView,
            UserIntermissionView.intermission_id == Intermission.id,
        )
        .where(
            UserIntermissionView.user_id == user_id,
            UserIntermissionView.viewed_at.isnot(None),
            Intermission.deleted_at.is_(None),
        )
    )
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = db.execute(
        base.order_by(UserIntermissionView.viewed_at.desc()).limit(limit).offset(offset)
    ).all()
    return {
        "total": int(total or 0), "limit": limit, "offset": offset,
        "items": [_intermission_dict(row, viewed) for row, viewed in rows],
    }


# --- changelog ------------------------------------------------------------

def list_changelog(
    db: Session, *, limit: int = 20, offset: int = 0,
) -> dict:
    """Public: published entries only, newest first."""
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))

    where = (
        ChangelogEntry.status == ContentStatus.published,
        ChangelogEntry.deleted_at.is_(None),
        ChangelogEntry.published_at.isnot(None),
    )
    total = db.execute(
        select(func.count(ChangelogEntry.id)).where(*where)
    ).scalar_one()
    rows = db.execute(
        select(ChangelogEntry).where(*where)
        .order_by(ChangelogEntry.published_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all()
    return {
        "total": int(total or 0), "limit": limit, "offset": offset,
        "items": [
            {
                "id": str(r.id), "type": r.type or "announcement",
                "title": r.title or "", "body": r.body or "",
                "published_at": _iso(r.published_at),
            }
            for r in rows
        ],
    }


def unread_changelog_count(db: Session, *, user_id: uuid.UUID) -> dict:
    read = db.get(UserChangelogRead, user_id)
    since = read.last_read_at if read else None
    where = [
        ChangelogEntry.status == ContentStatus.published,
        ChangelogEntry.deleted_at.is_(None),
        ChangelogEntry.published_at.isnot(None),
    ]
    if since is not None:
        where.append(ChangelogEntry.published_at > since)
    count = db.execute(
        select(func.count(ChangelogEntry.id)).where(*where)
    ).scalar_one()
    return {"unread": int(count or 0), "last_read_at": _iso(since)}


def mark_changelog_read(
    db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    row = db.get(UserChangelogRead, user_id)
    if row is None:
        db.add(UserChangelogRead(user_id=user_id, last_read_at=now))
    else:
        row.last_read_at = now
    db.flush()
    return {"unread": 0, "last_read_at": _iso(now)}


# --- immersion ------------------------------------------------------------

def _levels_completed(db: Session, user_id: uuid.UUID) -> int:
    """How many levels the learner has fully cleared.

    Derived from the same unlock rule the curriculum uses, so immersion can't
    unlock on a different definition of "finished" than the levels page shows.
    """
    from app.models.curriculum import Language
    from app.services.levels import all_level_states

    lang = db.execute(
        select(Language).where(Language.code == "es-MX")
    ).scalar_one_or_none()
    if lang is None:
        return 0
    states = all_level_states(db, user_id, lang.id)
    # A level is "completed" when the NEXT level has unlocked.
    completed = 0
    for i, state in enumerate(states):
        nxt = states[i + 1] if i + 1 < len(states) else None
        if nxt is not None and nxt.unlocked:
            completed = state.module.position
    return completed


def immersion_state(db: Session, *, user_id: uuid.UUID) -> dict:
    completed = _levels_completed(db, user_id)
    unlocked = immersion_rules.immersion_unlocked(completed)
    settings = db.get(UserSettings, user_id)
    profile = db.get(Profile, user_id)

    # Record the moment it unlocked, so the UI can celebrate it once.
    if unlocked and profile is not None and profile.immersion_unlocked_at is None:
        profile.immersion_unlocked_at = _now()
        db.flush()

    return {
        "unlocked": unlocked,
        "enabled": bool(settings.immersion_mode) if settings else False,
        "unlock_level": immersion_rules.IMMERSION_UNLOCK_LEVEL,
        "levels_completed": completed,
        "levels_remaining": immersion_rules.levels_remaining(completed),
        "never_translated": list(immersion_rules.NEVER_TRANSLATED),
    }


def set_immersion(db: Session, *, user_id: uuid.UUID, enabled: bool) -> dict:
    completed = _levels_completed(db, user_id)
    if not immersion_rules.can_enable(completed, enabled):
        raise ContentError(
            f"Immersion unlocks after level {immersion_rules.IMMERSION_UNLOCK_LEVEL}.",
            "locked", 403,
        )
    settings = db.get(UserSettings, user_id)
    if settings is None:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
    settings.immersion_mode = bool(enabled)
    db.flush()
    return immersion_state(db, user_id=user_id)

"""Admin management of changelog entries and intermissions (§22).

Same contract as the rest of the admin surface: capability-gated server-side,
every mutation audit-logged in the same transaction, destructive actions are
soft deletes.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.content_schemas import (
    AdminChangelogOut,
    AdminIntermissionOut,
    ChangelogCreate,
    ChangelogUpdate,
    IntermissionCreate,
    StatusIn,
)
from app.auth.capabilities import Capability
from app.auth.deps import require
from app.db.base import ContentStatus
from app.db.session import get_db
from app.domain.intermissions import TRIGGER_KINDS, describe
from app.models.identity import User
from app.models.platform import AdminAuditLog, ChangelogEntry, Intermission

router = APIRouter(prefix="/api/v1/admin", tags=["admin-content"])


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def _audit(db: Session, actor: User, action: str, table: str,
           target_id: uuid.UUID | None = None, before=None, after=None) -> None:
    db.add(AdminAuditLog(
        actor_id=actor.id, action=action, target_table=table,
        target_id=target_id, before=before or {}, after=after or {},
    ))


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Not found."}},
        ) from None


def _changelog_dict(row: ChangelogEntry) -> dict:
    return {
        "id": str(row.id), "type": row.type or "announcement",
        "title": row.title or "", "body": row.body or "",
        "status": row.status.value, "published_at": _iso(row.published_at),
    }


def _intermission_dict(row: Intermission) -> dict:
    return {
        "id": str(row.id), "title": row.title or "", "body": row.body_rich or "",
        "trigger": row.trigger or {}, "trigger_description": describe(row.trigger),
        "status": row.status.value,
    }


# --- changelog ------------------------------------------------------------

@router.get("/changelog", response_model=list[AdminChangelogOut])
def list_entries(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_view_draft)),
):
    """Admins see drafts too — that is the point of the draft state."""
    rows = db.execute(
        select(ChangelogEntry).where(ChangelogEntry.deleted_at.is_(None))
        .order_by(ChangelogEntry.created_at.desc()).limit(limit)
    ).scalars().all()
    return [_changelog_dict(r) for r in rows]


@router.post("/changelog", response_model=AdminChangelogOut, status_code=201)
def create_entry(
    body: ChangelogCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    row = ChangelogEntry(
        type=body.type, title=body.title, body=body.body, author_id=actor.id,
        status=ContentStatus.published if body.publish else ContentStatus.draft,
        published_at=_now() if body.publish else None,
    )
    db.add(row)
    db.flush()
    _audit(db, actor, "create", "changelog_entries", row.id, after=_changelog_dict(row))
    db.commit()
    return _changelog_dict(row)


@router.patch("/changelog/{entry_id}", response_model=AdminChangelogOut)
def update_entry(
    body: ChangelogUpdate,
    entry_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    row = db.get(ChangelogEntry, _uuid(entry_id))
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Entry not found."}})
    before = _changelog_dict(row)
    if body.type is not None:
        row.type = body.type
    if body.title is not None:
        row.title = body.title
    if body.body is not None:
        row.body = body.body
    db.flush()
    _audit(db, actor, "update", "changelog_entries", row.id,
           before=before, after=_changelog_dict(row))
    db.commit()
    return _changelog_dict(row)


@router.patch("/changelog/{entry_id}/status", response_model=AdminChangelogOut)
def set_entry_status(
    body: StatusIn,
    entry_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_publish)),
):
    row = db.get(ChangelogEntry, _uuid(entry_id))
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Entry not found."}})
    before = _changelog_dict(row)
    row.status = ContentStatus(body.status)
    # published_at is set once, on first publish: re-publishing an edited entry
    # should not shove it back to the top of everyone's unread count.
    if row.status == ContentStatus.published and row.published_at is None:
        row.published_at = _now()
    db.flush()
    _audit(db, actor, "set_status", "changelog_entries", row.id,
           before=before, after=_changelog_dict(row))
    db.commit()
    return _changelog_dict(row)


@router.delete("/changelog/{entry_id}", status_code=204)
def delete_entry(
    entry_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    """Soft delete (§22). The row stays for the archives view."""
    row = db.get(ChangelogEntry, _uuid(entry_id))
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Entry not found."}})
    before = _changelog_dict(row)
    row.deleted_at = _now()
    row.status = ContentStatus.archived
    db.flush()
    _audit(db, actor, "soft_delete", "changelog_entries", row.id, before=before)
    db.commit()
    return None


# --- intermissions --------------------------------------------------------

@router.get("/intermissions", response_model=list[AdminIntermissionOut])
def list_intermissions(
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_view_draft)),
):
    rows = db.execute(
        select(Intermission).where(Intermission.deleted_at.is_(None))
        .order_by(Intermission.created_at).limit(limit)
    ).scalars().all()
    return [_intermission_dict(r) for r in rows]


@router.post("/intermissions", response_model=AdminIntermissionOut, status_code=201)
def create_intermission(
    body: IntermissionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    kind = body.trigger.get("kind")
    if kind not in TRIGGER_KINDS:
        raise HTTPException(status_code=400, detail={"error": {
            "code": "invalid_trigger",
            "message": f"Trigger kind must be one of: {', '.join(TRIGGER_KINDS)}.",
        }})
    row = Intermission(
        title=body.title, body_rich=body.body, trigger=body.trigger,
        status=ContentStatus.published if body.publish else ContentStatus.draft,
    )
    db.add(row)
    db.flush()
    _audit(db, actor, "create", "intermissions", row.id, after=_intermission_dict(row))
    db.commit()
    return _intermission_dict(row)


@router.patch("/intermissions/{item_id}/status", response_model=AdminIntermissionOut)
def set_intermission_status(
    body: StatusIn,
    item_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_publish)),
):
    row = db.get(Intermission, _uuid(item_id))
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Intermission not found."}})
    before = _intermission_dict(row)
    row.status = ContentStatus(body.status)
    db.flush()
    _audit(db, actor, "set_status", "intermissions", row.id,
           before=before, after=_intermission_dict(row))
    db.commit()
    return _intermission_dict(row)


@router.delete("/intermissions/{item_id}", status_code=204)
def delete_intermission(
    item_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    row = db.get(Intermission, _uuid(item_id))
    if row is None or row.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Intermission not found."}})
    before = _intermission_dict(row)
    row.deleted_at = _now()
    row.status = ContentStatus.archived
    db.flush()
    _audit(db, actor, "soft_delete", "intermissions", row.id, before=before)
    db.commit()
    return None

"""Intermissions, changelog, and immersion mode.

The changelog list is public — anyone can read what shipped without an account.
Everything under `/me` is scoped to the authenticated user.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.routes.content_schemas import (
    EVENT_PATTERN,
    ChangelogPageOut,
    ImmersionIn,
    ImmersionOut,
    IntermissionHistoryOut,
    IntermissionOut,
    UnreadOut,
    ViewedOut,
)
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import content as content_svc

router = APIRouter(prefix="/api/v1", tags=["content"])


def _http(err: content_svc.ContentError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


# --- intermissions --------------------------------------------------------

@router.get("/me/intermissions/pending", response_model=list[IntermissionOut])
def pending(
    event: str = Query(pattern=EVENT_PATTERN),
    level: int | None = Query(default=None, ge=1, le=1000),
    lesson: int | None = Query(default=None, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return content_svc.pending_intermissions(
            db, user_id=user.id, event=event, level=level, lesson=lesson
        )
    except content_svc.ContentError as e:
        raise _http(e) from e


@router.post("/me/intermissions/{intermission_id}/viewed", response_model=ViewedOut)
def mark_viewed(
    intermission_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = content_svc.mark_intermission_viewed(
            db, user_id=user.id, intermission_id=intermission_id
        )
    except content_svc.ContentError as e:
        raise _http(e) from e
    db.commit()
    return result


@router.get("/me/intermissions/history", response_model=IntermissionHistoryOut)
def history(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return content_svc.intermission_history(
        db, user_id=user.id, limit=limit, offset=offset
    )


# --- changelog ------------------------------------------------------------

@router.get("/changelog", response_model=ChangelogPageOut)
def changelog(
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Public. No auth — what shipped is not a secret."""
    return content_svc.list_changelog(db, limit=limit, offset=offset)


@router.get("/me/changelog/unread", response_model=UnreadOut)
def unread(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return content_svc.unread_changelog_count(db, user_id=user.id)


@router.post("/me/changelog/mark-read", response_model=UnreadOut)
def mark_read(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    result = content_svc.mark_changelog_read(db, user_id=user.id)
    db.commit()
    return result


# --- immersion ------------------------------------------------------------

@router.get("/me/immersion", response_model=ImmersionOut)
def immersion(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    state = content_svc.immersion_state(db, user_id=user.id)
    db.commit()      # may have stamped immersion_unlocked_at
    return state


@router.put("/me/immersion", response_model=ImmersionOut)
def set_immersion(
    body: ImmersionIn,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        state = content_svc.set_immersion(db, user_id=user.id, enabled=body.enabled)
    except content_svc.ContentError as e:
        raise _http(e) from e
    db.commit()
    return state

"""Forum endpoints (spec §18).

Reads are public — the forums are browsable before anyone can post. Writes need
a signed-in user and pass through the posting gate + rate limiter in the service.
Moderation routes require the `forum_moderate` capability.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.routes.forum_schemas import (
    CategoryOut,
    CreateReplyRequest,
    CreateThreadRequest,
    ModerateOut,
    ModerateRequest,
    PostingStateOut,
    ReplyOut,
    ReportOut,
    ReportQueueItem,
    ReportRequest,
    ThreadDetailOut,
    ThreadListOut,
    ThreadSummaryOut,
)
from app.auth.capabilities import Capability, has_capability
from app.auth.deps import get_current_user, get_optional_user, require
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.identity import User
from app.services import forums as svc

router = APIRouter(prefix="/api/v1/forums", tags=["forums"])


def _http(err: svc.ForumError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


def _is_mod(user: User | None) -> bool:
    return user is not None and has_capability(user.role, Capability.forum_moderate)


# --- public reads ---------------------------------------------------------

@router.get("/posting-state", response_model=PostingStateOut)
def posting_state(settings: Settings = Depends(get_settings)):
    return PostingStateOut(
        posting_enabled=bool(getattr(settings, "forums_posting_enabled", False))
    )


@router.get("/categories", response_model=list[CategoryOut])
def categories(db: Session = Depends(get_db)):
    return svc.list_categories(db)


@router.get("/categories/{slug}/threads", response_model=ThreadListOut)
def threads(
    slug: str = Path(max_length=60),
    limit: int = Query(default=20, ge=1, le=svc.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    try:
        return svc.list_threads(
            db, slug=slug, limit=limit, offset=offset, include_hidden=_is_mod(user)
        )
    except svc.ForumError as e:
        raise _http(e) from e


@router.get("/threads/{thread_id}", response_model=ThreadDetailOut)
def thread(
    thread_id: str = Path(max_length=64),
    limit: int = Query(default=50, ge=1, le=svc.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    try:
        return svc.get_thread(
            db, thread_id=thread_id, limit=limit, offset=offset,
            include_hidden=_is_mod(user),
        )
    except svc.ForumError as e:
        raise _http(e) from e


# --- authed writes --------------------------------------------------------

@router.post("/categories/{slug}/threads", response_model=ThreadSummaryOut, status_code=201)
def create_thread(
    body: CreateThreadRequest,
    slug: str = Path(max_length=60),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    try:
        result = svc.create_thread(
            db, user_id=user.id, slug=slug, title=body.title, body=body.body,
            settings=settings,
        )
    except svc.ForumError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


@router.post("/threads/{thread_id}/replies", response_model=ReplyOut, status_code=201)
def create_reply(
    body: CreateReplyRequest,
    thread_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    try:
        result = svc.create_reply(
            db, user_id=user.id, thread_id=thread_id, body=body.body, settings=settings,
        )
    except svc.ForumError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


@router.post("/report", response_model=ReportOut)
def report(
    body: ReportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = svc.report(
            db, user_id=user.id, target_type=body.target_type,
            target_id=body.target_id, reason=body.reason, detail=body.detail,
        )
    except svc.ForumError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


# --- moderation (forum_moderate) ------------------------------------------

@router.get(
    "/moderation/reports",
    response_model=list[ReportQueueItem],
    dependencies=[Depends(require(Capability.forum_moderate))],
)
def report_queue(
    limit: int = Query(default=50, ge=1, le=svc.MAX_PAGE),
    db: Session = Depends(get_db),
):
    return svc.report_queue(db, limit=limit)


@router.post(
    "/moderation/act",
    response_model=ModerateOut,
    dependencies=[Depends(require(Capability.forum_moderate))],
)
def moderate(
    body: ModerateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        result = svc.moderate(
            db, actor=actor, target_type=body.target_type,
            target_id=body.target_id, action=body.action,
        )
    except svc.ForumError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result

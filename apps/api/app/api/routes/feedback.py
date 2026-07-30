"""Feedback / support endpoints (spec §22, §30).

`POST /feedback` is available to any signed-in user. The admin inbox
(`/admin/feedback`) is gated on the `feedback_manage` capability, which
moderator, admin, and owner all hold.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.routes.feedback_schemas import (
    FeedbackListOut,
    FeedbackTicketOut,
    PinRequest,
    RespondRequest,
    StateRequest,
    SubmitFeedbackOut,
    SubmitFeedbackRequest,
)
from app.auth.capabilities import Capability
from app.auth.deps import get_current_user, require
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.identity import User
from app.services import feedback as svc

router = APIRouter(prefix="/api/v1", tags=["feedback"])


def _http(err: svc.FeedbackError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.post("/feedback", response_model=SubmitFeedbackOut, status_code=201)
def submit_feedback(
    body: SubmitFeedbackRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    try:
        result = svc.submit(
            db, user=user, category=body.category, body=body.body,
            route=body.route, browser=body.browser, settings=settings,
        )
    except svc.FeedbackError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


# --- admin inbox (feedback_manage) ---------------------------------------

@router.get(
    "/admin/feedback",
    response_model=FeedbackListOut,
    dependencies=[Depends(require(Capability.feedback_manage))],
)
def list_feedback(
    state: str | None = Query(default=None, pattern="^(unanswered|answered)$"),
    pinned: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=svc.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    data = svc.list_tickets(db, state=state, pinned=pinned, limit=limit, offset=offset)
    data["counts"] = svc.counts(db)
    return data


@router.post(
    "/admin/feedback/{ticket_id}/respond",
    response_model=FeedbackTicketOut,
    dependencies=[Depends(require(Capability.feedback_manage))],
)
def respond_feedback(
    body: RespondRequest,
    ticket_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        result = svc.respond(db, actor=actor, ticket_id=ticket_id, response=body.response)
    except svc.FeedbackError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


@router.post(
    "/admin/feedback/{ticket_id}/pin",
    response_model=FeedbackTicketOut,
    dependencies=[Depends(require(Capability.feedback_manage))],
)
def pin_feedback(
    body: PinRequest,
    ticket_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
):
    try:
        result = svc.set_pin(db, ticket_id=ticket_id, pinned=body.pinned)
    except svc.FeedbackError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


@router.post(
    "/admin/feedback/{ticket_id}/state",
    response_model=FeedbackTicketOut,
    dependencies=[Depends(require(Capability.feedback_manage))],
)
def state_feedback(
    body: StateRequest,
    ticket_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
):
    try:
        result = svc.set_state(db, ticket_id=ticket_id, state=body.state)
    except svc.FeedbackError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result

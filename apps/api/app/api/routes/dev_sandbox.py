"""Admin dev sandbox endpoints (troubleshooting).

Every route here is gated on `Capability.dev_panel`, which only owner and admin
hold. A normal account gets 403 on all of them, and none of them can touch
another user's data — they operate on the caller's own rows.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.subscription_schemas import (
    DevActionOut,
    DevModeRequest,
    DevStateOut,
    SetStageRequest,
    UnlockAllRequest,
)
from app.auth.capabilities import Capability
from app.auth.deps import get_current_user, require
from app.db.session import get_db
from app.models.identity import User
from app.services import dev_sandbox as dev_svc

router = APIRouter(
    prefix="/api/v1/dev",
    tags=["dev-sandbox"],
    dependencies=[Depends(require(Capability.dev_panel))],
)


def _http(err: dev_svc.DevError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.get("/state", response_model=DevStateOut)
def state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return dev_svc.dev_state(db, user_id=user.id)


@router.put("/mode", response_model=DevStateOut)
def set_mode(
    body: DevModeRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    state = dev_svc.set_dev_mode(
        db, user_id=user.id, enabled=body.enabled, scale=body.scale
    )
    db.commit()
    return state


@router.post("/unlock-all", response_model=DevActionOut)
def unlock_all(
    body: UnlockAllRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        detail = dev_svc.unlock_all(db, user_id=user.id, up_to_level=body.up_to_level)
    except dev_svc.DevError as e:
        raise _http(e) from e
    db.commit()
    return DevActionOut(detail=detail)


@router.post("/make-reviews-due", response_model=DevActionOut)
def make_reviews_due(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    detail = dev_svc.make_reviews_due(db, user_id=user.id)
    db.commit()
    return DevActionOut(detail=detail)


@router.post("/set-stage", response_model=DevActionOut)
def set_stage(
    body: SetStageRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    try:
        detail = dev_svc.set_stage(
            db, user_id=user.id, item_type=body.item_type,
            item_id=body.item_id, stage=body.stage,
        )
    except dev_svc.DevError as e:
        raise _http(e) from e
    db.commit()
    return DevActionOut(detail=detail)


@router.post("/reset-progress", response_model=DevActionOut)
def reset_progress(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    from app.services import dev_reset
    detail = dev_reset.reset_progress(db, user_id=user.id)
    db.commit()
    return DevActionOut(detail=detail)


@router.post("/replay-onboarding", response_model=DevActionOut)
def replay_onboarding(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    detail = dev_svc.replay_onboarding(db, user_id=user.id)
    db.commit()
    return DevActionOut(detail=detail)

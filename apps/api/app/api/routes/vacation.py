"""Vacation / pause endpoints (spec R-25)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import vacation as svc

router = APIRouter(prefix="/api/v1/me/vacation", tags=["vacation"])


class VacationState(BaseModel):
    paused: bool
    since: str | None = None
    days: int = 0


class ResumeResult(BaseModel):
    resumed: bool
    shifted: int
    shift_seconds: int
    paused: bool
    since: str | None = None
    days: int = 0


@router.get("", response_model=VacationState)
def state(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.get_state(db, user_id=user.id)


@router.post("/pause", response_model=VacationState)
def pause(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = svc.pause(db, user_id=user.id)
    db.commit()
    return result


@router.post("/resume", response_model=ResumeResult)
def resume(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = svc.resume(db, user_id=user.id)
    db.commit()
    return result

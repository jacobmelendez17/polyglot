"""Practice endpoints: on-demand drilling that draws from learned items.

Practice does not change SRS scheduling; it awards XP and advances the
practice-stage (Uno..Cinco). All routes require auth and scope to the user.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.schemas import (
    PracticeAnswerRequest,
    PracticeGradeOut,
    PracticePromptOut,
    PracticeSessionOut,
)
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import practice as practice_svc

router = APIRouter(prefix="/api/v1/practice", tags=["practice"])


def _err(msg: str, code: str = "error", status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code,
                         detail={"error": {"code": code, "message": msg}})


@router.post("/sessions", response_model=PracticeSessionOut)
def create_practice(mode: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    seed = int(dt.datetime.now(tz=dt.timezone.utc).timestamp())
    try:
        session, prompts = practice_svc.start_practice(db, user.id, mode=mode, seed=seed)
    except practice_svc.PracticeError as exc:
        db.rollback()
        raise _err(str(exc), "practice_error") from exc
    db.commit()
    return PracticeSessionOut(
        session_id=str(session.id), mode=mode,
        prompts=[PracticePromptOut(**p.__dict__) for p in prompts],
    )


@router.post("/sessions/{session_id}/answers", response_model=PracticeGradeOut)
def answer_practice(session_id: str, body: PracticeAnswerRequest,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        grade = practice_svc.grade_practice(
            db, user_id=user.id, item_type=body.item_type, item_id=body.item_id,
            mode=body.mode, submitted=body.answer,
            tense=body.tense, person=body.person,
            idempotency_key=uuid.UUID(body.idempotency_key),
        )
    except practice_svc.PracticeError as exc:
        db.rollback()
        raise _err(str(exc), "practice_error") from exc
    except ValueError as exc:
        db.rollback()
        raise _err("Invalid identifier.", "bad_request") from exc
    db.commit()
    return PracticeGradeOut(**grade.__dict__)


@router.post("/sessions/{session_id}/complete")
def finish_practice(session_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    try:
        out = practice_svc.complete_practice(db, user_id=user.id, session_id=uuid.UUID(session_id))
    except practice_svc.PracticeError as exc:
        db.rollback()
        raise _err(str(exc), "not_found", 404) from exc
    db.commit()
    return out

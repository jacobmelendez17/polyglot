"""Testing-map endpoints (spec §7). Reader routes need auth; admin routes gated."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.capabilities import Capability
from app.auth.deps import get_current_user, require
from app.db.session import get_db
from app.models.identity import User
from app.services import testing as svc

router = APIRouter(prefix="/api/v1", tags=["testing"])


class OptionOut(BaseModel):
    text: str


class QuestionOut(BaseModel):
    id: str
    caption: str
    stem: str
    options: list[OptionOut]
    audio_asset_id: str | None = None


class StartOut(BaseModel):
    attempt_id: str
    map: str
    questions: list[QuestionOut]


class AnswerIn(BaseModel):
    question_id: str = Field(max_length=64)
    chosen_index: int = Field(ge=0, le=25)
    idempotency_key: str = Field(min_length=1, max_length=100)


class AnswerOut(BaseModel):
    correct: bool
    correct_index: int
    explanation: str
    xp_awarded: int
    already_answered: bool


class CompleteOut(BaseModel):
    map: str
    score: int
    total: int
    answered: int
    percentage: int


class AdminQuestionIn(BaseModel):
    language_code: str = "es-MX"
    map: str = Field(pattern="^(cefr|app|life)$")
    stem: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(min_length=2, max_length=8)
    correct_index: int = Field(ge=0, le=7)
    band: str = Field(default="", max_length=40)
    app_level: int = Field(default=1, ge=1, le=99)
    caption: str = Field(default="", max_length=1000)
    explanation: str = Field(default="", max_length=1000)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(draft|in_review|published|archived)$")


def _http(e: svc.TestingError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


@router.post("/tests/{map_name}/start", response_model=StartOut)
def start(map_name: str = Path(max_length=8), band: str = Query(default="", max_length=40),
          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return svc.start_attempt(db, user_id=user.id, map_name=map_name, band=band)
    except svc.TestingError as e:
        raise _http(e) from e
    finally:
        db.commit()


@router.post("/tests/attempts/{attempt_id}/answer", response_model=AnswerOut)
def answer(body: AnswerIn, attempt_id: str = Path(max_length=64),
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.answer(db, user_id=user.id, attempt_id=attempt_id,
                            question_id=body.question_id, chosen_index=body.chosen_index,
                            idempotency_key=body.idempotency_key)
    except svc.TestingError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return result


@router.post("/tests/attempts/{attempt_id}/complete", response_model=CompleteOut)
def complete(attempt_id: str = Path(max_length=64), db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    try:
        result = svc.complete(db, user_id=user.id, attempt_id=attempt_id)
    except svc.TestingError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return result


# --- admin -----------------------------------------------------------------

@router.post("/admin/tests/questions")
def admin_create(body: AdminQuestionIn, db: Session = Depends(get_db),
                 actor: User = Depends(require(Capability.content_edit))):
    from sqlalchemy import select
    from app.models.curriculum import Language
    lang = db.execute(select(Language).where(Language.code == body.language_code)).scalar_one_or_none()
    if lang is None:
        raise HTTPException(status_code=409,
            detail={"error": {"code": "no_language", "message": "Language not found."}})
    try:
        result = svc.create_question(
            db, actor_id=actor.id, language_id=str(lang.id), map_name=body.map,
            stem=body.stem, options=body.options, correct_index=body.correct_index,
            band=body.band, app_level=body.app_level, caption=body.caption,
            explanation=body.explanation)
    except svc.TestingError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return result


@router.patch("/admin/tests/questions/{question_id}/status")
def admin_status(body: StatusIn, question_id: str = Path(max_length=64),
                 db: Session = Depends(get_db),
                 actor: User = Depends(require(Capability.content_publish))):
    try:
        result = svc.set_status(db, actor_id=actor.id, question_id=question_id, status=body.status)
    except svc.TestingError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return result

"""Speaking practice endpoints (spec §7, §33). Auth required; no audio stored."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import speech_practice as svc

router = APIRouter(prefix="/api/v1/me/practice/speaking", tags=["speaking"])


class SpeakingPromptOut(BaseModel):
    idx: int
    item_type: str
    item_id: str
    prompt: str
    prompt_lang: str
    hint: str


class StartOut(BaseModel):
    prompts: list[SpeakingPromptOut]


class ScoreIn(BaseModel):
    item_type: str = Field(pattern="^(vocabulary|grammar)$")
    item_id: str = Field(max_length=64)
    # A text transcript ONLY — the audio is never uploaded (spec §33).
    transcript: str = Field(default="", max_length=1000)
    idempotency_key: str = Field(min_length=1, max_length=100)


class WordOut(BaseModel):
    word: str
    matched: bool


class ScoreOut(BaseModel):
    score: int
    passed: bool
    expected: str
    heard: str
    words: list[WordOut]
    missed: list[str]
    extra: list[str]
    xp_awarded: int
    practice_stage: int | None = None
    perfect: bool = False
    already_scored: bool = False


def _http(e: svc.SpeechPracticeError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


@router.post("/start", response_model=StartOut)
def start(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"prompts": svc.build_prompts(db, user_id=user.id)}


@router.post("/score", response_model=ScoreOut)
def score(body: ScoreIn, db: Session = Depends(get_db),
          user: User = Depends(get_current_user)):
    try:
        result = svc.score_item(
            db, user_id=user.id, item_type=body.item_type, item_id=body.item_id,
            transcript=body.transcript, idempotency_key=body.idempotency_key,
        )
    except svc.SpeechPracticeError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result

"""Learning endpoints: levels, lessons, review sessions, stats.

Every route requires an authenticated user and scopes all queries to that user.
Answer grading and SRS transitions happen server-side only; the client never
tells us whether it got something right.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.schemas import (
    CompleteLessonOut,
    CompleteLessonRequest,
    ForecastBucket,
    LessonDetailOut,
    LessonOut,
    LevelOut,
    QueuePromptOut,
    SessionOut,
    StatsOut,
    SubmitAnswerOut,
    SubmitAnswerRequest,
    UndoRequest,
)
from app.auth.deps import get_current_user
from app.db.base import ContentStatus
from app.db.session import get_db
from app.domain import srs
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import LeechState
from app.models.identity import User
from app.models.progress import UserItemProgress, XpEvent
from app.services import lessons as lesson_svc
from app.services import reviews as review_svc

router = APIRouter(prefix="/api/v1", tags=["learn"])


def _err(msg: str, code: str = "error", status_code: int = 400) -> HTTPException:
    return HTTPException(status_code=status_code,
                         detail={"error": {"code": code, "message": msg}})


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _module_or_404(db: Session, position: int) -> Module:
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    if lang is None:
        raise _err("Curriculum not set up yet.", "no_language", 409)
    module = db.execute(
        select(Module).where(Module.language_id == lang.id, Module.position == position)
    ).scalar_one_or_none()
    if module is None:
        raise _err("Level not found.", "not_found", 404)
    return module


@router.get("/levels", response_model=list[LevelOut])
def list_levels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    if lang is None:
        return []
    modules = db.execute(
        select(Module).where(Module.language_id == lang.id).order_by(Module.position)
    ).scalars().all()
    out: list[LevelOut] = []
    for m in modules:
        vcount = db.execute(
            select(func.count()).select_from(VocabularyItem).where(
                VocabularyItem.module_id == m.id,
                VocabularyItem.status == ContentStatus.published,
            )
        ).scalar_one()
        gcount = db.execute(
            select(func.count()).select_from(GrammarPoint).where(
                GrammarPoint.module_id == m.id,
                GrammarPoint.status == ContentStatus.published,
            )
        ).scalar_one()
        # Level 1 is always open; later levels open as earlier ones are learned.
        out.append(LevelOut(
            id=str(m.id), position=m.position, title=m.title,
            vocab_count=vcount, grammar_count=gcount,
            unlocked=m.position == 1 or _level_unlocked(db, user.id, lang.id, m.position),
        ))
    return out


def _level_unlocked(db: Session, user_id: uuid.UUID, lang_id: uuid.UUID, position: int) -> bool:
    from app.domain.curriculum import level_unlock_progress
    if position <= 1:
        return True
    prev = db.execute(
        select(Module).where(Module.language_id == lang_id, Module.position == position - 1)
    ).scalar_one_or_none()
    if prev is None:
        return False
    vocab_ids = db.execute(
        select(VocabularyItem.id).where(
            VocabularyItem.module_id == prev.id,
            VocabularyItem.status == ContentStatus.published,
        )
    ).scalars().all()
    gram_ids = db.execute(
        select(GrammarPoint.id).where(
            GrammarPoint.module_id == prev.id,
            GrammarPoint.status == ContentStatus.published,
        )
    ).scalars().all()
    if not vocab_ids and not gram_ids:
        return False
    prog = {
        (str(p.item_id)): p.srs_stage
        for p in db.execute(
            select(UserItemProgress).where(UserItemProgress.user_id == user_id)
        ).scalars().all()
    }
    unlocked, _ = level_unlock_progress(
        grammar_stages=[prog.get(str(i), 0) for i in gram_ids],
        vocab_stages=[prog.get(str(i), 0) for i in vocab_ids],
    )
    return unlocked


@router.get("/levels/{position}/lessons", response_model=list[LessonOut])
def list_lessons(position: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    module = _module_or_404(db, position)
    views = lesson_svc.list_lessons(db, user.id, module)
    db.commit()
    return [
        LessonOut(position=v.position, kind=v.kind, title=v.title,
                  item_count=len(v.items), completed=v.completed)
        for v in views
    ]


@router.get("/levels/{position}/lessons/{lesson_position}", response_model=LessonDetailOut)
def lesson_detail(position: int, lesson_position: int, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    module = _module_or_404(db, position)
    items = lesson_svc.get_lesson_items(db, user.id, module, lesson_position)
    db.commit()
    if not items:
        raise _err("Lesson not found or has no published items.", "not_found", 404)
    return LessonDetailOut(position=lesson_position, title=f"Lesson {lesson_position}", items=items)


@router.post("/levels/{position}/lessons/{lesson_position}/complete",
             response_model=CompleteLessonOut)
def complete_lesson(position: int, lesson_position: int, body: CompleteLessonRequest,
                    db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    module = _module_or_404(db, position)
    try:
        key = uuid.UUID(body.idempotency_key)
    except ValueError:
        raise _err("Invalid idempotency key.", "bad_request") from None
    try:
        result = lesson_svc.complete_lesson(
            db, user_id=user.id, module=module, position=lesson_position, idempotency_key=key,
        )
    except ValueError as exc:
        db.rollback()
        raise _err(str(exc), "not_found", 404) from exc
    db.commit()
    return CompleteLessonOut(**result)


@router.post("/reviews/sessions", response_model=SessionOut)
def create_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    session = review_svc.start_session(db, user.id, seed=int(_now().timestamp()))
    prompts_out: list[QueuePromptOut] = []
    for p in session.queue_snapshot.get("prompts", []):
        try:
            payload = review_svc.prompt_payload(db, p["item_type"], p["item_id"], p["direction"])
        except review_svc.ReviewError:
            continue
        prompts_out.append(QueuePromptOut(**p, **payload))
    db.commit()
    return SessionOut(session_id=str(session.id), prompts=prompts_out)


@router.post("/reviews/sessions/{session_id}/answers", response_model=SubmitAnswerOut)
def submit_answer(session_id: str, body: SubmitAnswerRequest,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = review_svc.submit_answer(
            db, user_id=user.id, session_id=uuid.UUID(session_id),
            item_type=body.item_type, item_id=body.item_id, direction=body.direction,
            submitted=body.answer, idempotency_key=uuid.UUID(body.idempotency_key),
        )
    except review_svc.ReviewError as exc:
        db.rollback()
        raise _err(str(exc), "review_error", 400) from exc
    except ValueError as exc:
        db.rollback()
        raise _err("Invalid identifier.", "bad_request") from exc
    db.commit()
    return SubmitAnswerOut(**result.__dict__)


@router.post("/reviews/answers/{answer_id}/undo")
def undo(answer_id: str, body: UndoRequest, db: Session = Depends(get_db),
         user: User = Depends(get_current_user)):
    try:
        out = review_svc.undo_answer(
            db, user_id=user.id, answer_id=uuid.UUID(answer_id), reason=body.reason,
        )
    except review_svc.ReviewError as exc:
        db.rollback()
        raise _err(str(exc), "undo_error", 400) from exc
    db.commit()
    return out


@router.post("/reviews/sessions/{session_id}/complete")
def finish_session(session_id: str, abandoned: bool = False,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        out = review_svc.complete_session(
            db, user_id=user.id, session_id=uuid.UUID(session_id), abandoned=abandoned,
        )
    except review_svc.ReviewError as exc:
        db.rollback()
        raise _err(str(exc), "not_found", 404) from exc
    db.commit()
    return out


@router.get("/me/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = _now()
    xp_total = db.execute(
        select(func.coalesce(func.sum(XpEvent.amount), 0)).where(XpEvent.user_id == user.id)
    ).scalar_one()
    rows = db.execute(
        select(UserItemProgress).where(UserItemProgress.user_id == user.id)
    ).scalars().all()
    due = sum(1 for p in rows if p.next_review_at and p.next_review_at <= now
              and p.srs_stage < int(srs.Stage.fluent))
    fluent = sum(1 for p in rows if p.srs_stage >= int(srs.Stage.fluent))
    leeches = sum(1 for p in rows if p.leech_state in (LeechState.leech, LeechState.critical))

    buckets: list[ForecastBucket] = []
    for offset, label in ((0, "today"), (1, "mañana"), (2, "+2 días")):
        start = now + dt.timedelta(days=offset)
        end = start + dt.timedelta(days=1)
        count = sum(
            1 for p in rows
            if p.next_review_at and start <= p.next_review_at < end
        ) if offset else due
        buckets.append(ForecastBucket(label=label, count=count))

    return StatsOut(
        xp_total=int(xp_total), reviews_due=due, items_learned=len(rows),
        items_fluent=fluent, leeches=leeches, forecast=buckets,
    )

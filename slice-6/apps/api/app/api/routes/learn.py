"""Learning endpoints: levels, lessons, review sessions, stats.

Every route requires an authenticated user and scopes all queries to that user.
Answer grading and SRS transitions happen server-side only; the client never
tells us whether it got something right.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

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
    QuizAnswerOut,
    QuizAnswerRequest,
    QuizPromptOut,
    QuizSessionOut,
    SessionOut,
    SrsStageCount,
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


def _require_unlocked(db: Session, user_id: uuid.UUID, module: Module) -> None:
    """Locked levels aren't reachable by URL either — the gate is server-side."""
    lang_id = module.language_id
    for st in _all_level_states(db, user_id, lang_id):
        if st.module.id == module.id:
            if not st.unlocked:
                raise _err(
                    "Finish the previous level to unlock this one.",
                    "level_locked", 403,
                )
            return


@router.get("/levels", response_model=list[LevelOut])
def list_levels(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    if lang is None:
        return []
    out: list[LevelOut] = []
    for st in _all_level_states(db, user.id, lang.id):
        out.append(LevelOut(
            id=str(st.module.id), position=st.module.position, title=st.module.title,
            vocab_count=len(st.vocab_ids), grammar_count=len(st.grammar_ids),
            unlocked=st.unlocked, unlock_progress=st.progress,
        ))
    return out


@dataclass
class _LevelState:
    module: Module
    vocab_ids: list[uuid.UUID]
    grammar_ids: list[uuid.UUID]
    unlocked: bool
    progress: dict | None


def _all_level_states(
    db: Session, user_id: uuid.UUID, lang_id: uuid.UUID,
) -> list[_LevelState]:
    """Unlock state for every level, computed in one pass.

    Level 1 is always open; level N opens once level N-1 hits the Familiar-1
    threshold. Everything is loaded up front (modules, published item ids, the
    user's progress) so this doesn't fan out into a query per level.
    """
    from app.domain.curriculum import level_unlock_progress

    modules = db.execute(
        select(Module).where(Module.language_id == lang_id).order_by(Module.position)
    ).scalars().all()
    if not modules:
        return []

    module_ids = [m.id for m in modules]
    vocab_rows = db.execute(
        select(VocabularyItem.id, VocabularyItem.module_id).where(
            VocabularyItem.module_id.in_(module_ids),
            VocabularyItem.status == ContentStatus.published,
            VocabularyItem.deleted_at.is_(None),
        )
    ).all()
    grammar_rows = db.execute(
        select(GrammarPoint.id, GrammarPoint.module_id).where(
            GrammarPoint.module_id.in_(module_ids),
            GrammarPoint.status == ContentStatus.published,
            GrammarPoint.deleted_at.is_(None),
        )
    ).all()
    vocab_by_module: dict[uuid.UUID, list[uuid.UUID]] = {m: [] for m in module_ids}
    grammar_by_module: dict[uuid.UUID, list[uuid.UUID]] = {m: [] for m in module_ids}
    for item_id, mod_id in vocab_rows:
        vocab_by_module.setdefault(mod_id, []).append(item_id)
    for item_id, mod_id in grammar_rows:
        grammar_by_module.setdefault(mod_id, []).append(item_id)

    stages = {
        str(p.item_id): p.srs_stage
        for p in db.execute(
            select(UserItemProgress).where(UserItemProgress.user_id == user_id)
        ).scalars().all()
    }

    states: list[_LevelState] = []
    prev_state: _LevelState | None = None
    for m in modules:
        v_ids = vocab_by_module.get(m.id, [])
        g_ids = grammar_by_module.get(m.id, [])
        if prev_state is None:
            unlocked, progress = True, None          # level 1 is always open
        elif not prev_state.vocab_ids and not prev_state.grammar_ids:
            unlocked, progress = False, None         # previous level has no content
        else:
            unlocked, progress = level_unlock_progress(
                grammar_stages=[stages.get(str(i), 0) for i in prev_state.grammar_ids],
                vocab_stages=[stages.get(str(i), 0) for i in prev_state.vocab_ids],
            )
        state = _LevelState(module=m, vocab_ids=v_ids, grammar_ids=g_ids,
                            unlocked=unlocked, progress=progress)
        states.append(state)
        prev_state = state
    return states


@router.get("/levels/{position}/lessons", response_model=list[LessonOut])
def list_lessons(position: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    module = _module_or_404(db, position)
    _require_unlocked(db, user.id, module)
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
    _require_unlocked(db, user.id, module)
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
    _require_unlocked(db, user.id, module)
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

    # Lessons available = published items the user hasn't started, counted ONLY
    # from levels they've actually unlocked. Counting every published item would
    # advertise the whole curriculum (509 items) as immediately learnable, when
    # really only the current level is reachable.
    started_ids = {(p.item_type.value, str(p.item_id)) for p in rows}
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    lessons_available = 0
    if lang is not None:
        for st in _all_level_states(db, user.id, lang.id):
            if not st.unlocked:
                continue
            lessons_available += sum(
                1 for i in st.vocab_ids if ("vocabulary", str(i)) not in started_ids
            )
            lessons_available += sum(
                1 for i in st.grammar_ids if ("grammar", str(i)) not in started_ids
            )

    # Per-stage counts + WaniKani-style groups.
    stage_counts_map: dict[int, int] = {s: 0 for s in range(1, 10)}
    for p in rows:
        stage_counts_map[p.srs_stage] = stage_counts_map.get(p.srs_stage, 0) + 1
    stage_counts = [
        SrsStageCount(stage=s, name=srs.stage_name(s), count=stage_counts_map[s])
        for s in range(1, 10)
    ]
    # Groups: Beginner (1-4), Familiar (5-6), Intermediate (7), Advanced (8), Fluent (9)
    stage_group_counts = {
        "beginner": sum(stage_counts_map[s] for s in (1, 2, 3, 4)),
        "familiar": sum(stage_counts_map[s] for s in (5, 6)),
        "intermediate": stage_counts_map[7],
        "advanced": stage_counts_map[8],
        "fluent": stage_counts_map[9],
    }

    # 7-slot forecast: today, then the next 6 days.
    labels = ["today", "mañana", "+2d", "+3d", "+4d", "+5d", "+6d"]
    buckets: list[ForecastBucket] = []
    for offset, label in enumerate(labels):
        if offset == 0:
            count = due
        else:
            start = now + dt.timedelta(days=offset)
            end = start + dt.timedelta(days=1)
            count = sum(1 for p in rows if p.next_review_at and start <= p.next_review_at < end)
        buckets.append(ForecastBucket(label=label, count=count))

    # When is the very next review, if none are due right now?
    upcoming = [p.next_review_at for p in rows
                if p.next_review_at and p.next_review_at > now
                and p.srs_stage < int(srs.Stage.fluent)]
    next_review = min(upcoming).isoformat() if upcoming and due == 0 else None

    return StatsOut(
        xp_total=int(xp_total), reviews_due=due, lessons_available=lessons_available,
        items_learned=len(rows), items_fluent=fluent, leeches=leeches,
        stage_group_counts=stage_group_counts, stage_counts=stage_counts,
        forecast=buckets, next_review_at=next_review,
    )


@router.post("/levels/{position}/lessons/{lesson_position}/quiz",
             response_model=QuizSessionOut)
def start_quiz(position: int, lesson_position: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """Begin the post-lesson quiz. Items only enter the SRS once answered
    correctly here (WaniKani-style gate)."""
    module = _module_or_404(db, position)
    _require_unlocked(db, user.id, module)
    try:
        session, prompts = lesson_svc.start_lesson_quiz(
            db, user_id=user.id, module=module, position=lesson_position,
        )
    except ValueError as exc:
        db.rollback()
        raise _err(str(exc), "not_found", 404) from exc
    db.commit()
    return QuizSessionOut(
        session_id=str(session.id),
        prompts=[QuizPromptOut(**p) for p in prompts],
    )


@router.post("/quiz/{session_id}/answers", response_model=QuizAnswerOut)
def answer_quiz(session_id: str, body: QuizAnswerRequest,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        out = lesson_svc.grade_quiz_answer(
            db, user_id=user.id, session_id=uuid.UUID(session_id),
            item_type=body.item_type, item_id=body.item_id, submitted=body.answer,
            idempotency_key=uuid.UUID(body.idempotency_key),
        )
    except ValueError as exc:
        db.rollback()
        raise _err(str(exc), "quiz_error", 400) from exc
    db.commit()
    return QuizAnswerOut(**out)

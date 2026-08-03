"""Testing service (spec §7, §12).

Starts an attempt on a map, hands out questions WITHOUT the answer, grades each
submission server-side, and awards 20 XP per correct answer (§12) idempotently.
The `app` map only offers questions at or below the level the learner has reached;
`cefr`/`life` filter by band/scenario. Questions come from the learner's active
language (slice 20). Admin authoring is capability-gated and audit-logged (§22).
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import testing as rules
from app.domain.xp import XpKind, xp_for
from app.models.curriculum import Module
from app.models.identity import User
from app.models.platform import AdminAuditLog
from app.models.progress import UserModuleState, XpEvent
from app.models.testing import TestAttempt, TestQuestion

PUBLISHED = "published"
DEFAULT_COUNT = 10


class TestingError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _uuid(value) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise TestingError("Not found.", "not_found", 404) from None


def _active_language_id(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    from app.services.languages import get_active
    lang = get_active(db, user_id=user_id)
    return lang.id if lang else None


def reached_level(db: Session, user_id: uuid.UUID) -> int:
    """Highest module position the learner has started (min 1)."""
    rows = db.execute(
        select(Module.position).join(
            UserModuleState, UserModuleState.module_id == Module.id
        ).where(UserModuleState.user_id == user_id)
    ).scalars().all()
    return max([*rows, 1])


def _question_public(q: TestQuestion) -> dict:
    # NB: correct_index is intentionally absent.
    return {
        "id": str(q.id),
        "caption": q.caption,
        "stem": q.stem,
        "options": [{"text": (o or {}).get("text", "") if isinstance(o, dict) else str(o)}
                    for o in (q.options or [])],
        "audio_asset_id": str(q.audio_asset_id) if q.audio_asset_id else None,
    }


def start_attempt(db: Session, *, user_id: uuid.UUID, map_name: str,
                  band: str = "", count: int = DEFAULT_COUNT, seed: int = 0) -> dict:
    if not rules.is_map(map_name):
        raise TestingError("Unknown testing map.", "unknown_map", 404)
    lang_id = _active_language_id(db, user_id)
    if lang_id is None:
        raise TestingError("No language available.", "no_language", 409)

    q = select(TestQuestion).where(
        TestQuestion.language_id == lang_id,
        TestQuestion.map == map_name,
        TestQuestion.status == PUBLISHED,
        TestQuestion.deleted_at.is_(None),
    )
    if map_name == "app":
        q = q.where(TestQuestion.app_level <= reached_level(db, user_id))
    elif band:
        q = q.where(TestQuestion.band == band)

    questions = db.execute(q).scalars().all()
    rng = random.Random(seed)
    rng.shuffle(questions)
    questions = questions[:count]

    attempt = TestAttempt(
        user_id=user_id, map=map_name, band=band, state="active",
        question_ids=[str(x.id) for x in questions], answers=[],
        score=0, total=len(questions),
    )
    db.add(attempt)
    db.flush()
    return {
        "attempt_id": str(attempt.id),
        "map": map_name,
        "questions": [_question_public(x) for x in questions],
    }


def answer(db: Session, *, user_id: uuid.UUID, attempt_id: str, question_id: str,
           chosen_index: int, idempotency_key: str) -> dict:
    attempt = db.get(TestAttempt, _uuid(attempt_id))
    if attempt is None or attempt.user_id != user_id:
        raise TestingError("Attempt not found.", "not_found", 404)
    if attempt.state != "active":
        raise TestingError("This attempt is finished.", "finished", 409)
    if str(question_id) not in (attempt.question_ids or []):
        raise TestingError("That question isn't part of this attempt.", "bad_question", 400)

    question = db.get(TestQuestion, _uuid(question_id))
    if question is None:
        raise TestingError("Question not found.", "not_found", 404)
    try:
        rules.validate_choice(chosen_index, len(question.options or []))
    except ValueError as e:
        raise TestingError(str(e), "bad_choice", 422) from e

    correct = rules.is_correct(chosen_index, question.correct_index)

    # Idempotent: a retry with the same key doesn't re-record or re-award.
    already = db.execute(
        select(XpEvent).where(XpEvent.idempotency_key == idempotency_key)
    ).scalar_one_or_none() is not None
    answered_ids = {a["question_id"] for a in (attempt.answers or [])}

    xp_awarded = 0
    if not already and str(question_id) not in answered_ids:
        attempt.answers = [*(attempt.answers or []),
                           {"question_id": str(question_id), "chosen": chosen_index,
                            "correct": correct}]
        attempt.score = rules.score_from_answers(attempt.answers)[0]
        if correct:
            xp_awarded = xp_for(XpKind.test_correct)
            db.add(XpEvent(user_id=user_id, amount=xp_awarded, kind="test",
                           source_table="test_attempts", idempotency_key=idempotency_key))
        db.flush()

    return {
        "correct": correct,
        "correct_index": question.correct_index,
        "explanation": question.explanation,
        "xp_awarded": xp_awarded,
        "already_answered": already or (str(question_id) in answered_ids),
    }


def complete(db: Session, *, user_id: uuid.UUID, attempt_id: str) -> dict:
    attempt = db.get(TestAttempt, _uuid(attempt_id))
    if attempt is None or attempt.user_id != user_id:
        raise TestingError("Attempt not found.", "not_found", 404)
    if attempt.state == "active":
        attempt.state = "completed"
        attempt.completed_at = _now()
        db.flush()
    correct, total = rules.score_from_answers(attempt.answers or [])
    return {
        "map": attempt.map,
        "score": correct,
        "total": attempt.total,
        "answered": total,
        "percentage": rules.percentage(correct, attempt.total),
    }


# --- admin authoring (audit-logged) ----------------------------------------

def _audit(db: Session, actor_id: uuid.UUID, action: str, target_id, before=None, after=None):
    db.add(AdminAuditLog(actor_id=actor_id, action=action, target_table="test_questions",
                         target_id=target_id, before=before or {}, after=after or {}))


def create_question(db: Session, *, actor_id: uuid.UUID, language_id: str, map_name: str,
                    stem: str, options: list, correct_index: int, band: str = "",
                    app_level: int = 1, caption: str = "", explanation: str = "") -> dict:
    if not rules.is_map(map_name):
        raise TestingError("Unknown map.", "unknown_map", 422)
    opts = options or []
    if len(opts) < 2:
        raise TestingError("A question needs at least two options.", "too_few_options", 422)
    if not (0 <= correct_index < len(opts)):
        raise TestingError("correct_index is out of range.", "bad_correct", 422)
    q = TestQuestion(
        language_id=_uuid(language_id), map=map_name, band=band, app_level=int(app_level),
        caption=caption, stem=stem,
        options=[o if isinstance(o, dict) else {"text": str(o)} for o in opts],
        correct_index=int(correct_index), explanation=explanation, status="draft",
    )
    db.add(q)
    db.flush()
    _audit(db, actor_id, "create_test_question", q.id, after={"map": map_name, "stem": stem})
    return {"id": str(q.id), "status": q.status}


def set_status(db: Session, *, actor_id: uuid.UUID, question_id: str, status: str) -> dict:
    if status not in ("draft", "in_review", "published", "archived"):
        raise TestingError("Invalid status.", "invalid", 422)
    q = db.get(TestQuestion, _uuid(question_id))
    if q is None:
        raise TestingError("Not found.", "not_found", 404)
    before = q.status
    q.status = status
    if status == "archived":
        q.deleted_at = _now()
    db.flush()
    _audit(db, actor_id, "set_test_question_status", q.id,
           before={"status": before}, after={"status": status})
    return {"id": str(q.id), "status": status}

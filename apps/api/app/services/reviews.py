"""Review sessions: building the queue, grading answers, resolving SRS pairs.

Key rules honoured here (PLANNING §10):
  - An item's SRS only changes once BOTH prompts of its pair are answered.
  - Promotion requires a clean pair (zero wrong attempts); any wrong attempt
    runs the demotion formula.
  - Exiting early keeps SRS changes for resolved pairs only; half-finished
    pairs revert (their answers are retained, flagged pair_incomplete).
  - Every submission is idempotent via a client-supplied key.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import leech as leech_mod
from app.domain import srs
from app.domain.answer_check import CheckMode, check_answer, expected_from_item
from app.domain.queue import Direction, QueueItem, ReviewOrder, build_queue
from app.domain.xp import XpKind, xp_for
from app.models.curriculum import GrammarPoint, VocabularyItem
from app.models.enums import ItemType, LeechState
from app.models.identity import UserSettings
from app.models.progress import (
    ReviewAnswer,
    ReviewSession,
    SrsReview,
    UserItemProgress,
    UserSynonym,
    XpEvent,
)


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class ReviewError(Exception):
    """User-safe review failure."""


@dataclass
class GradeResult:
    original_correct: bool
    final_correct: bool
    warnings: list[str]
    typo_forgiven: bool
    synonym_matched: bool
    expected: str
    pair_resolved: bool
    srs_stage_before: int | None = None
    srs_stage_after: int | None = None
    xp_awarded: int = 0
    answer_id: str | None = None
    message: str | None = None


# --- queue ---------------------------------------------------------------

def due_items(db: Session, user_id: uuid.UUID, *, now: dt.datetime | None = None,
              limit: int = 100) -> list[UserItemProgress]:
    now = now or _now()
    return list(db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.next_review_at.is_not(None),
            UserItemProgress.next_review_at <= now,
            UserItemProgress.srs_stage < int(srs.Stage.fluent),
        ).order_by(UserItemProgress.next_review_at).limit(limit)
    ).scalars().all())


def build_session_queue(
    db: Session, user_id: uuid.UUID, *, now: dt.datetime | None = None, seed: int = 0,
) -> list[dict]:
    settings = db.get(UserSettings, user_id)
    batch = settings.review_batch_size if settings and settings.review_batch_enabled else 20
    order = ReviewOrder(settings.review_order) if settings else ReviewOrder.random
    back_to_back = settings.back_to_back if settings else True
    first_dir = (Direction.es_to_en
                 if not settings or settings.back_to_back_order == "es_first"
                 else Direction.en_to_es)

    items = due_items(db, user_id, now=now, limit=batch)
    q_items = [
        QueueItem(
            item_type=p.item_type.value, item_id=str(p.item_id), srs_stage=p.srs_stage,
            unlocked_at_ts=(p.unlocked_at or _now()).timestamp(),
        )
        for p in items
    ]
    prompts = build_queue(
        q_items, order=order, back_to_back=back_to_back,
        first_direction=first_dir, seed=seed,
    )
    return [
        {"item_type": p.item_type, "item_id": p.item_id,
         "direction": p.direction.value, "srs_stage": p.srs_stage,
         "prompt_kind": srs.prompt_kind_for_stage(p.srs_stage)}
        for p in prompts
    ]


def start_session(db: Session, user_id: uuid.UUID, *, kind: str = "review",
                  seed: int = 0, now: dt.datetime | None = None) -> ReviewSession:
    now = now or _now()
    queue = build_session_queue(db, user_id, now=now, seed=seed)
    session = ReviewSession(
        user_id=user_id, kind=kind, state="active",
        queue_snapshot={"prompts": queue}, started_at=now,
    )
    db.add(session)
    db.flush()
    return session


# --- prompt payload ------------------------------------------------------

def prompt_payload(db: Session, item_type: str, item_id: str, direction: str) -> dict:
    """What the user sees. Never leaks accepted/rejected answers."""
    if item_type == "vocabulary":
        v = db.get(VocabularyItem, uuid.UUID(item_id))
        if v is None:
            raise ReviewError("item not found")
        article = v.article.value if v.article.value != "none" else None
        shown = v.term if direction == Direction.es_to_en.value else v.primary_translation
        return {
            "shown": shown,
            "article": article if direction == Direction.en_to_es.value else None,
            "part_of_speech": v.part_of_speech,
            "hint": v.pronunciation if direction == Direction.es_to_en.value else None,
        }
    g = db.get(GrammarPoint, uuid.UUID(item_id))
    if g is None:
        raise ReviewError("item not found")
    shown = g.title if direction == Direction.es_to_en.value else g.translation
    return {"shown": shown, "article": None, "part_of_speech": g.part_of_speech,
            "hint": g.structure_pattern or None}


def _expected_for(db: Session, user_id: uuid.UUID, item_type: str, item_id: str,
                  direction: str):
    """Build the expected-answer set for a direction."""
    user_syns = [
        s.synonym for s in db.execute(
            select(UserSynonym).where(
                UserSynonym.user_id == user_id,
                UserSynonym.item_type == ItemType(item_type),
                UserSynonym.item_id == uuid.UUID(item_id),
            )
        ).scalars().all()
    ]
    if item_type == "vocabulary":
        v = db.get(VocabularyItem, uuid.UUID(item_id))
        if v is None:
            raise ReviewError("item not found")
        if direction == Direction.es_to_en.value:
            return expected_from_item(
                primary=v.primary_translation, accepted=v.accepted_answers,
                rejected=v.rejected_answers, synonyms=v.synonyms, user_synonyms=user_syns,
            )
        return expected_from_item(
            primary=v.term, accepted=v.variations,
            rejected=v.rejected_answers, synonyms=[], user_synonyms=user_syns,
        )
    g = db.get(GrammarPoint, uuid.UUID(item_id))
    if g is None:
        raise ReviewError("item not found")
    if direction == Direction.es_to_en.value:
        return expected_from_item(
            primary=g.translation, accepted=g.accepted_answers,
            rejected=g.rejected_answers, synonyms=g.synonyms, user_synonyms=user_syns,
        )
    return expected_from_item(
        primary=g.title, accepted=g.accepted_answers,
        rejected=g.rejected_answers, synonyms=[], user_synonyms=user_syns,
    )


# --- grading -------------------------------------------------------------

def _pair_answers(db: Session, session_id: uuid.UUID, item_id: uuid.UUID) -> list[ReviewAnswer]:
    return list(db.execute(
        select(ReviewAnswer).where(
            ReviewAnswer.session_id == session_id, ReviewAnswer.item_id == item_id,
        ).order_by(ReviewAnswer.created_at)
    ).scalars().all())


def submit_answer(
    db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID,
    item_type: str, item_id: str, direction: str, submitted: str,
    idempotency_key: uuid.UUID, now: dt.datetime | None = None,
) -> GradeResult:
    now = now or _now()

    prior = db.execute(
        select(ReviewAnswer).where(ReviewAnswer.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if prior is not None:
        return GradeResult(
            original_correct=prior.original_correct, final_correct=prior.final_correct,
            warnings=list(prior.warning_flags or []), typo_forgiven=prior.typo_forgiven,
            synonym_matched=prior.synonym_matched, expected="",
            pair_resolved=prior.srs_stage_after is not None,
            srs_stage_before=prior.srs_stage_before,
            srs_stage_after=prior.srs_stage_after, answer_id=str(prior.id),
        )

    session = db.get(ReviewSession, session_id)
    if session is None or session.user_id != user_id:
        raise ReviewError("session not found")
    if session.state != "active":
        raise ReviewError("session is not active")

    settings = db.get(UserSettings, user_id)
    mode = CheckMode.normal
    allow_cheating = bool(settings.allow_cheating) if settings else False
    accept_user_syn = bool(settings.accept_user_synonyms) if settings else False

    expected = _expected_for(db, user_id, item_type, item_id, direction)
    result = check_answer(
        submitted, expected, mode=mode,
        accept_user_synonyms=accept_user_syn, allow_cheating=allow_cheating,
    )

    progress = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == ItemType(item_type),
            UserItemProgress.item_id == uuid.UUID(item_id),
        )
    ).scalar_one_or_none()
    if progress is None:
        raise ReviewError("item is not unlocked")

    answer = ReviewAnswer(
        session_id=session_id, user_id=user_id,
        item_type=ItemType(item_type), item_id=uuid.UUID(item_id),
        prompt_direction=direction,
        prompt_kind=srs.prompt_kind_for_stage(progress.srs_stage),
        submitted_answer=submitted[:2000],
        normalized_answer="",
        original_correct=result.correct, final_correct=result.correct,
        typo_forgiven=result.typo_forgiven, synonym_matched=result.synonym_matched,
        warning_flags=result.warning_values,
        srs_stage_before=progress.srs_stage,
        pair_incomplete=True,
        idempotency_key=idempotency_key, answered_at=now,
    )
    db.add(answer)
    db.flush()

    out = GradeResult(
        original_correct=result.correct, final_correct=result.correct,
        warnings=result.warning_values, typo_forgiven=result.typo_forgiven,
        synonym_matched=result.synonym_matched,
        expected=expected.primary, pair_resolved=False,
        srs_stage_before=progress.srs_stage, answer_id=str(answer.id),
        message=result.message,
    )

    answers = _pair_answers(db, session_id, uuid.UUID(item_id))
    directions = {a.prompt_direction for a in answers}
    if len(directions) >= 2:
        _resolve(db, user_id=user_id, session_id=session_id, progress=progress,
                 answers=answers, now=now, out=out)
    return out


def _resolve(db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID,
             progress: UserItemProgress, answers: list[ReviewAnswer],
             now: dt.datetime, out: GradeResult) -> None:
    """Both prompts answered → apply SRS, leech, and XP exactly once."""
    wrong = sum(1 for a in answers if not a.final_correct)
    stage_before = progress.srs_stage

    is_leech = leech_mod.is_leech(leech_mod.LeechState(progress.leech_state.value))
    outcome = srs.resolve_pair(
        stage_before=stage_before, wrong_answer_count=wrong, now=now, is_leech=is_leech,
    )

    progress.srs_stage = outcome.stage_after
    progress.next_review_at = outcome.next_review_at
    progress.total_reviews = (progress.total_reviews or 0) + 1
    progress.total_incorrect = (progress.total_incorrect or 0) + wrong
    if srs.is_fluent(outcome.stage_after) and progress.fluent_at is None:
        progress.fluent_at = now

    recent = leech_mod.push_result(list(progress.recent_results or []), wrong)
    progress.recent_results = recent
    score = leech_mod.leech_score(recent)
    settings = db.get(UserSettings, user_id)
    threshold = float(settings.leech_threshold) if settings else 1.0
    progress.leech_score = score
    progress.leech_state = LeechState(leech_mod.leech_state(score, threshold=threshold).value)

    for a in answers:
        a.pair_incomplete = False
        a.srs_stage_after = outcome.stage_after

    db.add(SrsReview(
        user_id=user_id, item_type=progress.item_type, item_id=progress.item_id,
        session_id=session_id, stage_before=stage_before, stage_after=outcome.stage_after,
        wrong_answer_count=wrong, promoted=outcome.promoted,
        penalty_factor=outcome.penalty or 1, occurred_at=now,
    ))

    kind = (XpKind.grammar_review if progress.item_type is ItemType.grammar
            else XpKind.vocab_review)
    amount = xp_for(kind)
    db.add(XpEvent(
        user_id=user_id, amount=amount, kind=kind.value,
        source_table="srs_reviews", source_id=progress.item_id,
        idempotency_key=uuid.uuid4(),
    ))

    out.pair_resolved = True
    out.srs_stage_before = stage_before
    out.srs_stage_after = outcome.stage_after
    out.xp_awarded = amount
    db.flush()


def undo_answer(db: Session, *, user_id: uuid.UUID, answer_id: uuid.UUID,
                reason: str | None = None, now: dt.datetime | None = None) -> dict:
    """Mark an answer correct after the fact (PLANNING §9).

    The original answer and its original correctness are always retained. Undo
    corrects the grading — and therefore the SRS outcome derived from it — but
    never touches XP, points, or the leech buffer.
    """
    now = now or _now()
    answer = db.get(ReviewAnswer, answer_id)
    if answer is None or answer.user_id != user_id:
        raise ReviewError("answer not found")

    settings = db.get(UserSettings, user_id)
    if settings is not None and not settings.undo_enabled:
        raise ReviewError("undo is disabled in your settings")

    if answer.final_correct and answer.undo_used:
        return {"already_undone": True}

    answer.final_correct = True
    answer.undo_used = True
    answer.undo_reason = reason

    # If the pair already resolved, replay the SRS transition from stage_before.
    if not answer.pair_incomplete and answer.srs_stage_after is not None:
        answers = _pair_answers(db, answer.session_id, answer.item_id)
        wrong = sum(1 for a in answers if not a.final_correct)
        progress = db.execute(
            select(UserItemProgress).where(
                UserItemProgress.user_id == user_id,
                UserItemProgress.item_type == answer.item_type,
                UserItemProgress.item_id == answer.item_id,
            )
        ).scalar_one_or_none()
        if progress is not None and answer.srs_stage_before is not None:
            corrected = srs.apply_srs(answer.srs_stage_before, wrong)
            progress.srs_stage = corrected
            progress.next_review_at = srs.next_review_at(corrected, now)
            for a in answers:
                a.srs_stage_after = corrected
    db.flush()
    return {"already_undone": False, "final_correct": True}


def complete_session(db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID,
                     abandoned: bool = False, now: dt.datetime | None = None) -> dict:
    """Finish a session. Unresolved pairs keep no SRS change (PLANNING §10)."""
    now = now or _now()
    session = db.get(ReviewSession, session_id)
    if session is None or session.user_id != user_id:
        raise ReviewError("session not found")
    session.state = "abandoned" if abandoned else "completed"
    session.completed_at = now
    resolved = db.execute(
        select(SrsReview).where(SrsReview.session_id == session_id)
    ).scalars().all()
    db.flush()
    return {"state": session.state, "items_resolved": len(resolved)}

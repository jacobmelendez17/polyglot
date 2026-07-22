"""Lesson flow: what's available, starting a lesson, completing it.

Completing a lesson is what UNLOCKS items into the SRS: it creates
UserItemProgress rows at Beginner 1 with a first review 4 hours out, and awards
XP through the idempotent ledger.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain import srs
from app.domain.answer_check import CheckMode, check_answer, expected_from_item
from app.domain.curriculum import PlannedItem, PlannedLesson, plan_level
from app.domain.xp import XpKind, xp_for
from app.models.curriculum import GrammarPoint, Module, VocabularyItem
from app.models.enums import CurriculumMode, ItemType
from app.models.identity import UserSettings
from app.models.progress import (
    ReviewAnswer,
    ReviewSession,
    UserItemProgress,
    UserModuleState,
    XpEvent,
)


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


@dataclass
class LessonView:
    position: int
    kind: str
    title: str
    items: list[dict]
    completed: bool


def _locked_mode(db: Session, user_id: uuid.UUID, module: Module) -> CurriculumMode:
    """The curriculum mode is fixed when the user starts a level (PLANNING §5)."""
    state = db.execute(
        select(UserModuleState).where(
            UserModuleState.user_id == user_id, UserModuleState.module_id == module.id
        )
    ).scalar_one_or_none()
    if state is not None:
        return CurriculumMode(state.curriculum_mode_locked)

    settings = db.get(UserSettings, user_id)
    mode = settings.curriculum_mode if settings else CurriculumMode.default_dispersed
    db.add(UserModuleState(
        user_id=user_id, module_id=module.id,
        curriculum_mode_locked=mode.value if hasattr(mode, "value") else str(mode),
        started_at=_now(),
    ))
    db.flush()
    return CurriculumMode(mode)


def _published_items(db: Session, module: Module) -> tuple[list, list]:
    vocab = db.execute(
        select(VocabularyItem).where(
            VocabularyItem.module_id == module.id,
            VocabularyItem.status == ContentStatus.published,
            VocabularyItem.deleted_at.is_(None),
        ).order_by(VocabularyItem.term)
    ).scalars().all()
    grammar = db.execute(
        select(GrammarPoint).where(
            GrammarPoint.module_id == module.id,
            GrammarPoint.status == ContentStatus.published,
            GrammarPoint.deleted_at.is_(None),
        ).order_by(GrammarPoint.title)
    ).scalars().all()
    return list(vocab), list(grammar)


def _batch_of(item: VocabularyItem) -> int | None:
    """The CSV batch isn't stored as a column; derive a stable grouping from
    difficulty_rank when present, else let the planner chunk evenly."""
    return item.difficulty_rank or None


def plan_for_user(db: Session, user_id: uuid.UUID, module: Module) -> list[PlannedLesson]:
    mode = _locked_mode(db, user_id, module)
    vocab, grammar = _published_items(db, module)
    seed = hash((str(user_id), str(module.id))) & 0xFFFFFFFF
    return plan_level(
        vocab=[PlannedItem("vocabulary", str(v.id), _batch_of(v)) for v in vocab],
        grammar=[PlannedItem("grammar", str(g.id)) for g in grammar],
        mode=mode, seed=seed,
    )


def _progress_map(db: Session, user_id: uuid.UUID) -> dict[tuple[str, str], UserItemProgress]:
    rows = db.execute(
        select(UserItemProgress).where(UserItemProgress.user_id == user_id)
    ).scalars().all()
    return {(p.item_type.value, str(p.item_id)): p for p in rows}


def list_lessons(db: Session, user_id: uuid.UUID, module: Module) -> list[LessonView]:
    plan = plan_for_user(db, user_id, module)
    progress = _progress_map(db, user_id)
    views: list[LessonView] = []
    for lesson in plan:
        item_dicts = []
        done = 0
        for it in lesson.items:
            p = progress.get((it.item_type, it.item_id))
            if p is not None and p.lesson_completed_at is not None:
                done += 1
            item_dicts.append({"item_type": it.item_type, "item_id": it.item_id})
        views.append(LessonView(
            position=lesson.position, kind=lesson.kind, title=lesson.title,
            items=item_dicts, completed=done == len(lesson.items) and len(lesson.items) > 0,
        ))
    return views


def get_lesson_items(db: Session, user_id: uuid.UUID, module: Module, position: int) -> list[dict]:
    """Full teaching payload for a lesson: everything the user needs to learn."""
    plan = plan_for_user(db, user_id, module)
    lesson = next((ls for ls in plan if ls.position == position), None)
    if lesson is None:
        return []
    out: list[dict] = []
    for it in lesson.items:
        if it.item_type == "vocabulary":
            v = db.get(VocabularyItem, uuid.UUID(it.item_id))
            if v is None:
                continue
            out.append({
                "item_type": "vocabulary", "item_id": str(v.id),
                "term": v.term, "translation": v.primary_translation,
                "pronunciation": v.pronunciation, "ipa": v.ipa,
                "part_of_speech": v.part_of_speech, "meaning": v.meaning,
                # Article only for nouns — enforced at the DB level too (§6).
                "article": v.article.value if v.article.value != "none" else None,
                "gender": v.grammatical_gender.value,
            })
        else:
            g = db.get(GrammarPoint, uuid.UUID(it.item_id))
            if g is None:
                continue
            out.append({
                "item_type": "grammar", "item_id": str(g.id),
                "term": g.title, "translation": g.translation,
                "structure": g.structure_pattern, "meaning": g.meaning,
                "explanation": g.explanation_rich,
            })
    return out


def complete_lesson(
    db: Session, *, user_id: uuid.UUID, module: Module, position: int,
    idempotency_key: uuid.UUID, now: dt.datetime | None = None,
    require_quiz: bool = True,
) -> dict:
    """Unlock the lesson's items into the SRS and award XP (idempotently).

    Items only unlock once the learner has answered them correctly in the
    lesson quiz (WaniKani-style gate). `require_quiz=False` exists for tests and
    for any future "skip quiz" setting.
    """
    now = now or _now()

    existing = db.execute(
        select(XpEvent).where(XpEvent.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if existing is not None:
        return {"xp_awarded": existing.amount, "unlocked": 0, "already_completed": True,
                "blocked_by_quiz": 0}

    plan = plan_for_user(db, user_id, module)
    lesson = next((ls for ls in plan if ls.position == position), None)
    if lesson is None:
        raise ValueError("lesson not found")

    passed = (
        quiz_passed_items(db, user_id=user_id, module=module, position=position)
        if require_quiz else None
    )

    progress = _progress_map(db, user_id)
    unlocked = 0
    blocked = 0
    grammar_count = vocab_count = 0

    for it in lesson.items:
        key = (it.item_type, it.item_id)
        if key in progress and progress[key].lesson_completed_at is not None:
            continue   # already learned; don't reset their SRS

        # The quiz gate: an item the learner hasn't proven yet stays out of the SRS.
        if passed is not None and key not in passed:
            blocked += 1
            continue

        if it.item_type == "grammar":
            grammar_count += 1
        else:
            vocab_count += 1

        p = progress.get(key)
        if p is None:
            p = UserItemProgress(
                user_id=user_id,
                item_type=ItemType(it.item_type),
                item_id=uuid.UUID(it.item_id),
                srs_stage=int(srs.Stage.beginner_1),
                recent_results=[],
            )
            db.add(p)
        p.unlocked_at = now
        p.lesson_completed_at = now
        p.next_review_at = srs.next_review_at(int(srs.Stage.beginner_1), now)
        unlocked += 1

    amount = (xp_for(XpKind.grammar_lesson, grammar_count)
              + xp_for(XpKind.vocab_lesson, vocab_count))
    if amount > 0:
        db.add(XpEvent(
            user_id=user_id, amount=amount, kind="lesson",
            source_table="lessons", idempotency_key=idempotency_key,
        ))
    db.flush()
    return {"xp_awarded": amount, "unlocked": unlocked,
            "already_completed": False, "blocked_by_quiz": blocked}


# --- Lesson quiz (WaniKani-style gate before items enter the SRS) ---------
#
# Teaching a word isn't proof you know it. After the lesson cards, the learner
# must answer each item correctly once; only then does complete_lesson unlock
# them into the SRS. Wrong answers simply cycle back — the quiz is a gate, not
# a filter, so nobody is punished, they just try again.

def start_lesson_quiz(
    db: Session, *, user_id: uuid.UUID, module: Module, position: int,
    now: dt.datetime | None = None,
) -> tuple[ReviewSession, list[dict]]:
    """Create (or reuse) a quiz session for this lesson and return its prompts."""
    now = now or _now()
    items = get_lesson_items(db, user_id, module, position)
    if not items:
        raise ValueError("lesson not found")

    session = ReviewSession(
        user_id=user_id, kind="lesson_quiz", state="active",
        queue_snapshot={"lesson": position, "module": str(module.id),
                        "items": [{"item_type": i["item_type"], "item_id": i["item_id"]}
                                  for i in items]},
        started_at=now,
    )
    db.add(session)
    db.flush()

    prompts = [
        {
            "item_type": i["item_type"],
            "item_id": i["item_id"],
            # Recognition direction: shown the Spanish, type the English.
            "shown": i["term"],
            "hint": i.get("part_of_speech") or "",
        }
        for i in items
    ]
    return session, prompts


def grade_quiz_answer(
    db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID,
    item_type: str, item_id: str, submitted: str,
    idempotency_key: uuid.UUID, now: dt.datetime | None = None,
) -> dict:
    """Grade one quiz answer server-side. Records it so complete_lesson can
    verify the learner actually passed before anything enters the SRS."""
    now = now or _now()

    session = db.get(ReviewSession, session_id)
    if session is None or session.user_id != user_id or session.kind != "lesson_quiz":
        raise ValueError("quiz session not found")

    prior = db.execute(
        select(ReviewAnswer).where(ReviewAnswer.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if prior is not None:
        return {"correct": prior.final_correct, "expected": "", "already_recorded": True}

    # Expected answer comes from the item — never from the client.
    if item_type == "vocabulary":
        v = db.get(VocabularyItem, uuid.UUID(item_id))
        if v is None:
            raise ValueError("item not found")
        expected = expected_from_item(
            primary=v.primary_translation, accepted=v.accepted_answers,
            rejected=v.rejected_answers, synonyms=v.synonyms,
        )
        primary = v.primary_translation
    else:
        g = db.get(GrammarPoint, uuid.UUID(item_id))
        if g is None:
            raise ValueError("item not found")
        expected = expected_from_item(
            primary=g.translation, accepted=g.accepted_answers,
            rejected=g.rejected_answers, synonyms=g.synonyms,
        )
        primary = g.translation

    result = check_answer(submitted, expected, mode=CheckMode.normal)

    db.add(ReviewAnswer(
        session_id=session_id, user_id=user_id,
        item_type=ItemType(item_type), item_id=uuid.UUID(item_id),
        prompt_direction="es_to_en", prompt_kind="translation",
        submitted_answer=submitted[:2000], normalized_answer="",
        original_correct=result.correct, final_correct=result.correct,
        typo_forgiven=result.typo_forgiven, synonym_matched=result.synonym_matched,
        warning_flags=result.warning_values,
        pair_incomplete=False,            # quiz answers stand alone
        idempotency_key=idempotency_key, answered_at=now,
    ))
    db.flush()

    return {
        "correct": result.correct,
        "expected": primary,
        "warnings": result.warning_values,
        "typo_forgiven": result.typo_forgiven,
        "already_recorded": False,
    }


def quiz_passed_items(
    db: Session, *, user_id: uuid.UUID, module: Module, position: int,
) -> set[tuple[str, str]]:
    """Every (item_type, item_id) the learner has answered correctly in any
    quiz session for this lesson."""
    sessions = db.execute(
        select(ReviewSession).where(
            ReviewSession.user_id == user_id,
            ReviewSession.kind == "lesson_quiz",
        )
    ).scalars().all()
    relevant = [
        s.id for s in sessions
        if (s.queue_snapshot or {}).get("lesson") == position
        and (s.queue_snapshot or {}).get("module") == str(module.id)
    ]
    if not relevant:
        return set()
    answers = db.execute(
        select(ReviewAnswer).where(
            ReviewAnswer.session_id.in_(relevant),
            ReviewAnswer.final_correct.is_(True),
        )
    ).scalars().all()
    return {(a.item_type.value, str(a.item_id)) for a in answers}

"""Per-item progress: SRS state, practice stages, and review history.

Backs the item detail page (a word's full history) and the "your items" list.
Read-only — nothing here mutates progress, unlike services/practice.py and
services/reviews.py.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain import srs
from app.domain.audio import StoredAsset, resolve_audio
from app.domain.practice import MAX_PRACTICE_STAGE, PERFECT_CATEGORIES, STAGE_GATE
from app.models.curriculum import AudioAsset, GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import ItemType, PracticeCategory
from app.models.progress import ReviewAnswer, UserItemPracticeStage, UserItemProgress

HISTORY_LIMIT = 25

# Leeches surface first, then the shakiest SRS stages — same "needs the most
# help first" ordering used for weak-item practice selection.
_LEECH_ORDER = {"critical": 0, "leech": 1, "watch": 2, "none": 3}


class ItemError(Exception):
    """User-safe item-progress failure."""


@dataclass
class PracticeStageView:
    category: str
    stage: int
    max_stage: int
    stage_name: str
    stage_reached_at: dt.datetime | None
    next_stage_at: dt.datetime | None
    live: bool   # False for categories without a shipped practice mode yet


@dataclass
class HistoryEntry:
    answered_at: dt.datetime | None
    direction: str
    prompt_kind: str
    correct: bool
    undo_used: bool
    srs_stage_before: int | None
    srs_stage_after: int | None


@dataclass
class ItemProgressView:
    item_type: str
    item_id: str
    term: str
    translation: str
    part_of_speech: str
    level: int | None
    audio: dict | None
    srs_stage: int
    srs_stage_name: str
    next_review_at: dt.datetime | None
    total_reviews: int
    total_incorrect: int
    accuracy: float | None
    leech_state: str
    leech_score: float
    unlocked_at: dt.datetime | None
    lesson_completed_at: dt.datetime | None
    fluent_at: dt.datetime | None
    perfect_at: dt.datetime | None
    practice_stages: list[PracticeStageView]
    history: list[HistoryEntry]


@dataclass
class ItemSummaryView:
    item_type: str
    item_id: str
    term: str
    translation: str
    level: int | None
    srs_stage: int
    srs_stage_name: str
    next_review_at: dt.datetime | None
    leech_state: str
    practice_stage: int
    perfect: bool


def _audio_for(db: Session, text: str, content_id, content_type: str) -> dict | None:
    if not text:
        return None
    row = db.execute(
        select(AudioAsset).where(
            AudioAsset.content_type == content_type,
            AudioAsset.content_id == content_id,
        ).limit(1)
    ).scalar_one_or_none()
    asset = None
    if row is not None:
        asset = StoredAsset(storage_path=row.storage_path, locale=row.locale,
                            voice_id=row.voice_id, source=row.source)
    return resolve_audio(text, asset=asset).to_dict()


def get_item_progress(
    db: Session, user_id: uuid.UUID, *, item_type: str, item_id: str,
    now: dt.datetime | None = None,
) -> ItemProgressView:
    now = now or dt.datetime.now(tz=dt.timezone.utc)
    try:
        it = ItemType(item_type)
        iid = uuid.UUID(item_id)
    except ValueError:
        raise ItemError("item not found") from None

    if it is ItemType.vocabulary:
        v = db.get(VocabularyItem, iid)
        if v is None or v.deleted_at is not None:
            raise ItemError("item not found")
        term, translation = v.term, v.primary_translation
        pos, module_id = v.part_of_speech, v.module_id
        content_type = "vocabulary"
    else:
        g = db.get(GrammarPoint, iid)
        if g is None or g.deleted_at is not None:
            raise ItemError("item not found")
        term, translation, pos, module_id = g.title, g.translation, g.part_of_speech, g.module_id
        content_type = "grammar"

    progress = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == it, UserItemProgress.item_id == iid,
        )
    ).scalar_one_or_none()
    if progress is None:
        raise ItemError("you haven't started this item yet")

    module = db.get(Module, module_id)
    level = module.position if module else None
    language = db.get(Language, module.language_id) if module else None
    stage_names = (language.stage_names if language else None) or []

    stage_rows = {
        r.category: r for r in db.execute(
            select(UserItemPracticeStage).where(
                UserItemPracticeStage.user_id == user_id,
                UserItemPracticeStage.item_type == it, UserItemPracticeStage.item_id == iid,
            )
        ).scalars().all()
    }
    practice_stages: list[PracticeStageView] = []
    for cat in PracticeCategory:
        row = stage_rows.get(cat)
        stage = row.stage if row else 0
        reached = row.stage_reached_at if row else None
        next_at = reached + STAGE_GATE if reached and stage < MAX_PRACTICE_STAGE else None
        name = stage_names[stage - 1] if 1 <= stage <= len(stage_names) else ""
        practice_stages.append(PracticeStageView(
            category=cat.value, stage=stage, max_stage=MAX_PRACTICE_STAGE,
            stage_name=name, stage_reached_at=reached, next_stage_at=next_at,
            live=cat.value in PERFECT_CATEGORIES,
        ))

    history_rows = db.execute(
        select(ReviewAnswer).where(
            ReviewAnswer.user_id == user_id,
            ReviewAnswer.item_type == it, ReviewAnswer.item_id == iid,
        ).order_by(ReviewAnswer.answered_at.desc()).limit(HISTORY_LIMIT)
    ).scalars().all()
    history = [
        HistoryEntry(
            answered_at=a.answered_at, direction=a.prompt_direction, prompt_kind=a.prompt_kind,
            correct=a.final_correct, undo_used=a.undo_used,
            srs_stage_before=a.srs_stage_before, srs_stage_after=a.srs_stage_after,
        )
        for a in history_rows
    ]

    # Accuracy over ALL-time answers (not just the fetched history page),
    # based on the original grading — undo overrides how the SRS treated the
    # attempt, not whether the learner actually knew it unaided.
    total_answers = db.execute(
        select(func.count()).select_from(ReviewAnswer).where(
            ReviewAnswer.user_id == user_id, ReviewAnswer.item_type == it,
            ReviewAnswer.item_id == iid,
        )
    ).scalar_one()
    correct_answers = db.execute(
        select(func.count()).select_from(ReviewAnswer).where(
            ReviewAnswer.user_id == user_id, ReviewAnswer.item_type == it,
            ReviewAnswer.item_id == iid, ReviewAnswer.original_correct.is_(True),
        )
    ).scalar_one()
    accuracy = round(100 * correct_answers / total_answers, 1) if total_answers else None

    return ItemProgressView(
        item_type=it.value, item_id=str(iid), term=term, translation=translation,
        part_of_speech=pos, level=level,
        audio=_audio_for(db, term, iid, content_type),
        srs_stage=progress.srs_stage, srs_stage_name=srs.stage_name(progress.srs_stage),
        next_review_at=progress.next_review_at,
        total_reviews=progress.total_reviews or 0, total_incorrect=progress.total_incorrect or 0,
        accuracy=accuracy,
        leech_state=progress.leech_state.value, leech_score=float(progress.leech_score or 0),
        unlocked_at=progress.unlocked_at, lesson_completed_at=progress.lesson_completed_at,
        fluent_at=progress.fluent_at, perfect_at=progress.perfect_at,
        practice_stages=practice_stages, history=history,
    )


def list_item_summaries(db: Session, user_id: uuid.UUID) -> list[ItemSummaryView]:
    rows = db.execute(
        select(UserItemProgress).where(UserItemProgress.user_id == user_id)
    ).scalars().all()
    if not rows:
        return []

    vocab_ids = [r.item_id for r in rows if r.item_type is ItemType.vocabulary]
    grammar_ids = [r.item_id for r in rows if r.item_type is ItemType.grammar]
    vocabs = {
        v.id: v for v in db.execute(
            select(VocabularyItem).where(VocabularyItem.id.in_(vocab_ids))
        ).scalars().all()
    } if vocab_ids else {}
    grammars = {
        g.id: g for g in db.execute(
            select(GrammarPoint).where(GrammarPoint.id.in_(grammar_ids))
        ).scalars().all()
    } if grammar_ids else {}
    modules = {m.id: m for m in db.execute(select(Module)).scalars().all()}

    stage_by_item: dict[tuple[ItemType, uuid.UUID], dict[str, int]] = {}
    for s in db.execute(
        select(UserItemPracticeStage).where(UserItemPracticeStage.user_id == user_id)
    ).scalars().all():
        stage_by_item.setdefault((s.item_type, s.item_id), {})[s.category.value] = s.stage

    out: list[ItemSummaryView] = []
    for p in rows:
        if p.item_type is ItemType.vocabulary:
            v = vocabs.get(p.item_id)
            if v is None:
                continue
            term, translation, module_id = v.term, v.primary_translation, v.module_id
        else:
            g = grammars.get(p.item_id)
            if g is None:
                continue
            term, translation, module_id = g.title, g.translation, g.module_id
        module = modules.get(module_id)
        cats = stage_by_item.get((p.item_type, p.item_id), {})
        headline_stage = min(cats.get(c, 0) for c in PERFECT_CATEGORIES)
        out.append(ItemSummaryView(
            item_type=p.item_type.value, item_id=str(p.item_id),
            term=term, translation=translation, level=module.position if module else None,
            srs_stage=p.srs_stage, srs_stage_name=srs.stage_name(p.srs_stage),
            next_review_at=p.next_review_at, leech_state=p.leech_state.value,
            practice_stage=headline_stage, perfect=p.perfect_at is not None,
        ))

    out.sort(key=lambda r: (_LEECH_ORDER.get(r.leech_state, 3), r.srs_stage, r.term))
    return out

"""Feature-unlock service (spec §7).

Turns the pure schedule into per-learner state. `completed_levels` counts, in the
learner's active language, how many published levels have *every* item at Familiar
or beyond — that's the honest "you've completed this level" signal the unlock schedule
keys off. `require_feature` is the reusable server-side gate: a practice entry point
can call it to 403 a locked feature rather than trusting the UI to hide it.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import feature_unlock as fu
from app.models.curriculum import GrammarPoint, Module, VocabularyItem
from app.models.progress import UserItemProgress

# Familiar 1 is SRS stage 5 (Beginner 1-4 = 1-4, Familiar 1 = 5). A level counts as
# completed once all its published items have reached it.
FAMILIAR_STAGE = 5
PUBLISHED = "published"


def _active_language_id(db: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    from app.services.languages import get_active
    lang = get_active(db, user_id=user_id)
    return lang.id if lang else None


def _published_status(model):
    # status is stored as an enum elsewhere but compared by value; support both.
    return model.status == PUBLISHED


def completed_levels(db: Session, user_id: uuid.UUID) -> int:
    """How many published levels the learner has fully brought to Familiar+."""
    lang_id = _active_language_id(db, user_id)
    if lang_id is None:
        return 0
    modules = db.execute(
        select(Module).where(Module.language_id == lang_id).order_by(Module.position)
    ).scalars().all()
    if not modules:
        return 0

    stages = {
        p.item_id: p.srs_stage
        for p in db.execute(
            select(UserItemProgress).where(UserItemProgress.user_id == user_id)
        ).scalars().all()
    }

    done = 0
    for m in modules:
        vocab_ids = db.execute(
            select(VocabularyItem.id).where(
                VocabularyItem.module_id == m.id, VocabularyItem.status == PUBLISHED,
                VocabularyItem.deleted_at.is_(None))
        ).scalars().all()
        grammar_ids = db.execute(
            select(GrammarPoint.id).where(
                GrammarPoint.module_id == m.id, GrammarPoint.status == PUBLISHED,
                GrammarPoint.deleted_at.is_(None))
        ).scalars().all()
        item_ids = [*vocab_ids, *grammar_ids]
        if item_ids and all(stages.get(i, 0) >= FAMILIAR_STAGE for i in item_ids):
            done += 1
    return done


def list_features(db: Session, user_id: uuid.UUID) -> dict:
    done = completed_levels(db, user_id)
    return {"completed_levels": done, "features": fu.feature_states(done)}


def require_feature(db: Session, *, user_id: uuid.UUID, feature: str) -> None:
    """Raise 403 if `feature` isn't unlocked yet for this learner."""
    done = completed_levels(db, user_id)
    if not fu.is_unlocked(feature, completed_levels=done):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "feature_locked",
                              "message": "This feature unlocks as you complete levels.",
                              "feature": feature,
                              "unlock_level": fu.unlock_level(feature),
                              "completed_levels": done}},
        )

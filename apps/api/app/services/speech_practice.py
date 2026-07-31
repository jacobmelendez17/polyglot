"""Speaking practice service (spec §7).

A "say the phrase" loop over words the learner has already met. The browser
transcribes the utterance; only the transcript is sent here. We resolve the
expected phrase SERVER-SIDE (the client never declares what counts as right),
score it through the provider seam, and — on a pass — advance the *speaking*
practice stage (Uno..Cinco) and award XP. Like the rest of practice, this never
touches the SRS schedule; it's extra drilling toward "Perfect" status.

No audio is stored: the request carries a text transcript and nothing else.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.practice import advance_practice_stage, is_perfect
from app.domain.xp import XpKind, xp_for
from app.models.curriculum import GrammarPoint, VocabularyItem
from app.models.enums import ItemType, PracticeCategory
from app.models.progress import UserItemPracticeStage, UserItemProgress, XpEvent
from app.services.speech import SpeechScorer, get_scorer


class SpeechPracticeError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _accepted_texts(item: VocabularyItem) -> list[str]:
    out: list[str] = []
    for a in (item.accepted_answers or []):
        if isinstance(a, dict) and a.get("text"):
            out.append(str(a["text"]))
        elif isinstance(a, str):
            out.append(a)
    if getattr(item, "latam_variant", ""):
        out.append(item.latam_variant)
    return out


def _learned_item_ids(db: Session, user_id: uuid.UUID, item_type: ItemType) -> set[uuid.UUID]:
    rows = db.execute(
        select(UserItemProgress.item_id).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == item_type,
        )
    ).scalars().all()
    return {r if isinstance(r, uuid.UUID) else uuid.UUID(str(r)) for r in rows}


def build_prompts(db: Session, *, user_id: uuid.UUID, limit: int = 10,
                  seed: int = 0) -> list[dict]:
    """Speaking prompts drawn from vocabulary the learner has already met."""
    learned = _learned_item_ids(db, user_id, ItemType.vocabulary)
    if not learned:
        return []
    items = db.execute(
        select(VocabularyItem).where(VocabularyItem.id.in_(learned))
    ).scalars().all()
    items = [v for v in items if v.term and getattr(v, "deleted_at", None) is None]
    rng = random.Random(seed)
    rng.shuffle(items)
    prompts = []
    for idx, v in enumerate(items[:limit]):
        prompts.append({
            "idx": idx, "item_type": "vocabulary", "item_id": str(v.id),
            "prompt": v.term, "prompt_lang": "es",
            "hint": v.primary_translation or "",
        })
    return prompts


def _resolve_expected(db: Session, item_type: str, item_id: uuid.UUID) -> tuple[str, list[str]]:
    if item_type == "vocabulary":
        item = db.get(VocabularyItem, item_id)
        if item is None:
            raise SpeechPracticeError("Item not found.", "not_found", 404)
        return item.term, _accepted_texts(item)
    if item_type == "grammar":
        item = db.get(GrammarPoint, item_id)
        if item is None:
            raise SpeechPracticeError("Item not found.", "not_found", 404)
        return item.title, []
    raise SpeechPracticeError("Unknown item type.", "bad_request", 400)


def score_item(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str,
    transcript: str, idempotency_key: str, scorer: SpeechScorer | None = None,
    now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    scorer = scorer or get_scorer()
    try:
        iid = uuid.UUID(str(item_id))
    except (ValueError, AttributeError):
        raise SpeechPracticeError("Item not found.", "not_found", 404) from None

    itype = ItemType(item_type) if item_type in ("vocabulary", "grammar") else None
    if itype is None:
        raise SpeechPracticeError("Unknown item type.", "bad_request", 400)
    # Practice only covers what the learner has met.
    if iid not in _learned_item_ids(db, user_id, itype):
        raise SpeechPracticeError("You haven't learned this item yet.", "not_learned", 403)

    expected, accepted = _resolve_expected(db, item_type, iid)
    result = scorer.score(transcript, expected, accepted)

    # Idempotent: a retry with the same key must not re-award XP or re-advance the
    # stage. Scoring is deterministic, so we can recompute the result safely and
    # skip the writes when this key already awarded XP.
    already = db.execute(
        select(XpEvent).where(XpEvent.idempotency_key == idempotency_key)
    ).scalar_one_or_none() is not None

    stage_row = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.user_id == user_id,
            UserItemPracticeStage.item_type == itype,
            UserItemPracticeStage.item_id == iid,
            UserItemPracticeStage.category == PracticeCategory.speaking,
        )
    ).scalar_one_or_none()
    current_stage = stage_row.stage if stage_row else 0

    xp_awarded = 0
    if result.passed and not already:
        if stage_row is None:
            stage_row = UserItemPracticeStage(
                user_id=user_id, item_type=itype, item_id=iid,
                category=PracticeCategory.speaking, stage=0,
            )
            db.add(stage_row)
            db.flush()
        new_stage = advance_practice_stage(stage_row.stage, correct=True)
        if new_stage != stage_row.stage:
            stage_row.stage = new_stage
            stage_row.stage_reached_at = now
        current_stage = stage_row.stage
        xp_awarded = xp_for(XpKind.test_correct)
        db.add(XpEvent(
            user_id=user_id, amount=xp_awarded, kind="practice",
            source_table="practice_sessions", idempotency_key=idempotency_key,
        ))
        db.flush()

    return {
        "score": result.score,
        "passed": result.passed,
        "expected": result.expected,
        "heard": result.heard,
        "words": [{"word": w.word, "matched": w.matched} for w in result.words],
        "missed": result.missed,
        "extra": result.extra,
        "xp_awarded": xp_awarded,
        "practice_stage": current_stage,
        "perfect": is_perfect(current_stage),
        "already_scored": already,
    }

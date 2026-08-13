"""Item detail, review history, user synonyms, and level progression.

This is the read model behind "what do I actually know about this word?" —
SRS stage and history, mistakes, practice stages (Uno..Cinco), leech state, and
the learner's own synonyms.

Two rules govern everything in this file:

  * **Private fields stay private.** `accepted_answers` and `rejected_answers`
    are the answer key (spec §6). They are never serialised here, at any level
    of authorisation, and a test asserts it.
  * **Every read is scoped twice.** By user (progress, history, synonyms are
    per-user rows) and by level (an item in a locked level is a 403, not a
    quiet empty page).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain import practice_stages as ps
from app.domain import srs
from app.domain.audio import StoredAsset, resolve_audio
from app.domain.normalize import normalize_term
from app.models.curriculum import (
    AudioAsset,
    GrammarPoint,
    Language,
    Module,
    Sentence,
    SentenceLink,
    VocabularyItem,
)
from app.models.enums import ItemType, PracticeCategory
from app.models.progress import (
    ReviewAnswer,
    UserItemPracticeStage,
    UserItemProgress,
    UserSynonym,
)
from app.services.levels import all_level_states, state_for_module

# A level holds ~60 items; the cap is a backstop against an unbounded response
# if a level is ever mis-imported with thousands of rows.
MAX_LEVEL_ITEMS = 300
MAX_HISTORY_PAGE = 100
MAX_USER_SYNONYMS_PER_ITEM = 25
MAX_SYNONYM_LENGTH = 60


class ItemError(Exception):
    """User-safe failure with an API error code and HTTP status."""

    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    """Serialise a timestamp, treating naive columns as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def _enum_value(value: object) -> str:
    return getattr(value, "value", value) if value is not None else ""


# --- lookup + authorization ---------------------------------------------

def _load_item(db: Session, item_type: str, item_id: str):
    try:
        pk = uuid.UUID(item_id)
    except (ValueError, AttributeError):
        raise ItemError("Item not found.", "not_found", 404) from None
    model = VocabularyItem if item_type == "vocabulary" else GrammarPoint
    row = db.get(model, pk)
    if row is None or row.deleted_at is not None:
        raise ItemError("Item not found.", "not_found", 404)
    if row.status != ContentStatus.published:
        # Unpublished content is invisible to learners; admins use the admin UI.
        raise ItemError("Item not found.", "not_found", 404)
    return row


def _require_visible(db: Session, user_id: uuid.UUID, row) -> Module:
    """An item is readable only when its level is unlocked for this user."""
    module = db.get(Module, row.module_id)
    if module is None:
        raise ItemError("Item not found.", "not_found", 404)
    state = state_for_module(
        all_level_states(db, user_id, module.language_id), module.id
    )
    if state is None or not state.unlocked:
        raise ItemError(
            "Finish the previous level to unlock this one.", "level_locked", 403
        )
    return module


def _stage_names(db: Session, language_id: uuid.UUID) -> list[str]:
    lang = db.get(Language, language_id)
    names = list(lang.stage_names or []) if lang else []
    return names or list(ps.DEFAULT_STAGE_NAMES)


def _audio_for(db: Session, asset_id: uuid.UUID | None, text: str, locale: str) -> dict:
    asset = db.get(AudioAsset, asset_id) if asset_id else None
    stored = (
        StoredAsset(
            storage_path=asset.storage_path, locale=asset.locale,
            voice_id=asset.voice_id or "", source=asset.source or "tts",
        )
        if asset is not None
        else None
    )
    return resolve_audio(text, locale=locale, asset=stored).to_dict()


# --- practice stages -----------------------------------------------------

def _practice_rows(
    db: Session, user_id: uuid.UUID, item_type: str, item_ids: list[uuid.UUID],
) -> dict[tuple[uuid.UUID, str], UserItemPracticeStage]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.user_id == user_id,
            UserItemPracticeStage.item_type == ItemType(item_type),
            UserItemPracticeStage.item_id.in_(item_ids),
        )
    ).scalars().all()
    return {(r.item_id, _enum_value(r.category)): r for r in rows}


def _stage_map(
    rows: dict[tuple[uuid.UUID, str], UserItemPracticeStage], item_id: uuid.UUID,
) -> dict[str, int]:
    return {
        category: ps.clamp_stage(rows[(item_id, category)].stage)
        if (item_id, category) in rows else 0
        for category in ps.PRACTICE_CATEGORIES
    }


def _practice_view(
    rows: dict[tuple[uuid.UUID, str], UserItemPracticeStage],
    item_id: uuid.UUID,
    names: list[str],
    srs_stage: int,
    now: dt.datetime,
) -> dict:
    stages: list[dict] = []
    raw: dict[str, int] = {}
    for category in ps.PRACTICE_CATEGORIES:
        row = rows.get((item_id, category))
        stage = ps.clamp_stage(row.stage if row else 0)
        raw[category] = stage
        reached = row.stage_reached_at if row else None
        complete = ps.category_complete(stage)
        on_cooldown = (not complete) and ps.cooldown_active(reached, now)
        stages.append({
            "category": category,
            "stage": stage,
            "max_stage": ps.MAX_PRACTICE_STAGE,
            "label": ps.stage_label(stage, names),
            "complete": complete,
            "on_cooldown": on_cooldown,
            "next_available_at": (
                None if complete else _iso(ps.next_available_at(reached))
            ),
            "stage_reached_at": _iso(reached),
        })
    summary = ps.perfect_progress(raw, srs_stage)
    return {"stages": stages, **summary}


# --- item detail ---------------------------------------------------------

def get_item_detail(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str,
    now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    row = _load_item(db, item_type, item_id)
    module = _require_visible(db, user_id, row)
    names = _stage_names(db, row.language_id)
    lang = db.get(Language, row.language_id)
    locale = lang.code if lang else "es-MX"

    is_vocab = item_type == "vocabulary"
    term = row.term if is_vocab else row.title
    translation = row.primary_translation if is_vocab else row.translation

    progress = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == ItemType(item_type),
            UserItemProgress.item_id == row.id,
        )
    ).scalar_one_or_none()

    answers_total, answers_correct, first_wrong = _answer_stats(
        db, user_id, item_type, row.id
    )

    srs_stage = int(progress.srs_stage) if progress else 0
    practice_rows = _practice_rows(db, user_id, item_type, [row.id])
    practice = _practice_view(practice_rows, row.id, names, srs_stage, now)

    detail: dict = {
        "item_type": item_type,
        "item_id": str(row.id),
        "term": term,
        "translation": translation,
        "part_of_speech": row.part_of_speech or "",
        "meaning": row.meaning or "",
        "level": module.position,
        "level_title": module.title,
        "synonyms": _string_list(row.synonyms),
        "audio": _audio_for(db, row.audio_asset_id, term, locale),
        "examples": _examples(db, item_type, row.id, locale),
        "user_synonyms": list_user_synonyms(db, user_id=user_id,
                                            item_type=item_type, item_id=str(row.id)),
        "progress": {
            "learned": progress is not None and progress.lesson_completed_at is not None,
            "srs_stage": srs_stage,
            "srs_stage_name": srs.stage_name(srs_stage) if srs_stage else "Not learned",
            "next_review_at": _iso(progress.next_review_at) if progress else None,
            "unlocked_at": _iso(progress.unlocked_at) if progress else None,
            "lesson_completed_at": (
                _iso(progress.lesson_completed_at) if progress else None
            ),
            "fluent": bool(progress and progress.fluent_at is not None),
            "fluent_at": _iso(progress.fluent_at) if progress else None,
            "perfect": bool(progress and progress.perfect_at is not None),
            "perfect_at": _iso(progress.perfect_at) if progress else None,
            "total_reviews": int(progress.total_reviews or 0) if progress else 0,
            "total_incorrect": int(progress.total_incorrect or 0) if progress else 0,
            "answers_total": answers_total,
            "answers_correct": answers_correct,
            "accuracy": (
                round(answers_correct / answers_total, 3) if answers_total else None
            ),
            "mistakes": first_wrong,
            "leech_state": _enum_value(progress.leech_state) if progress else "none",
            "leech_score": float(progress.leech_score or 0) if progress else 0.0,
        },
        "practice": practice,
    }

    if is_vocab:
        article = _enum_value(row.article)
        gender = _enum_value(row.grammatical_gender)
        detail.update({
            "pronunciation": row.pronunciation or "",
            "ipa": row.ipa or "",
            # Only nouns carry an article (spec §6) — the DB constraint enforces
            # it, and "none" is normalised away so the UI never renders "el" for
            # a verb by accident.
            "article": article if article and article != "none" else None,
            "gender": gender if gender and gender != "none" else None,
            "variations": _string_list(row.variations),
            "castilian_variant": row.castilian_variant or "",
            "latam_variant": row.latam_variant or "",
            "context": row.context or [],
        })
    else:
        detail.update({
            "structure": row.structure_pattern or "",
            "explanation": row.explanation_rich or "",
        })
    return detail


def _string_list(value) -> list[str]:
    """JSON columns hold either ["str"] or [{"text": "..."}]; flatten both."""
    out: list[str] = []
    for entry in value or []:
        if isinstance(entry, str) and entry.strip():
            out.append(entry.strip())
        elif isinstance(entry, dict):
            text = str(entry.get("text") or "").strip()
            if text:
                out.append(text)
    return out


def _examples(db: Session, item_type: str, item_id: uuid.UUID, locale: str) -> list[dict]:
    links = db.execute(
        select(SentenceLink).where(
            SentenceLink.item_type == ItemType(item_type),
            SentenceLink.item_id == item_id,
        )
    ).scalars().all()
    out: list[dict] = []
    for link in links:
        sentence = db.get(Sentence, link.sentence_id)
        if sentence is None or sentence.deleted_at is not None:
            continue
        if sentence.status != ContentStatus.published:
            continue
        out.append({
            "id": str(sentence.id),
            "text_es": sentence.text_es,
            "text_en": sentence.text_en or "",
            "difficulty": sentence.difficulty or "phrase",
            "role": link.role or "example",
            "audio": _audio_for(db, sentence.audio_asset_id, sentence.text_es, locale),
        })
    return out


def _answer_stats(
    db: Session, user_id: uuid.UUID, item_type: str, item_id: uuid.UUID,
) -> tuple[int, int, int]:
    """(answers, final-correct answers, originally-wrong answers)."""
    stmt: Select = select(
        func.count(ReviewAnswer.id),
        func.count(ReviewAnswer.id).filter(ReviewAnswer.final_correct.is_(True)),
        func.count(ReviewAnswer.id).filter(ReviewAnswer.original_correct.is_(False)),
    ).where(
        ReviewAnswer.user_id == user_id,
        ReviewAnswer.item_type == ItemType(item_type),
        ReviewAnswer.item_id == item_id,
    )
    total, correct, wrong = db.execute(stmt).one()
    return int(total or 0), int(correct or 0), int(wrong or 0)


# --- review history ------------------------------------------------------

def list_review_history(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str,
    limit: int = 20, offset: int = 0,
) -> dict:
    row = _load_item(db, item_type, item_id)
    _require_visible(db, user_id, row)
    limit = max(1, min(int(limit), MAX_HISTORY_PAGE))
    offset = max(0, int(offset))

    total = db.execute(
        select(func.count(ReviewAnswer.id)).where(
            ReviewAnswer.user_id == user_id,
            ReviewAnswer.item_type == ItemType(item_type),
            ReviewAnswer.item_id == row.id,
        )
    ).scalar_one()

    rows = db.execute(
        select(ReviewAnswer).where(
            ReviewAnswer.user_id == user_id,
            ReviewAnswer.item_type == ItemType(item_type),
            ReviewAnswer.item_id == row.id,
        ).order_by(ReviewAnswer.created_at.desc()).limit(limit).offset(offset)
    ).scalars().all()

    return {
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "id": str(a.id),
                "direction": a.prompt_direction,
                "prompt_kind": a.prompt_kind,
                "submitted_answer": a.submitted_answer or "",
                "original_correct": bool(a.original_correct),
                "final_correct": bool(a.final_correct),
                "typo_forgiven": bool(a.typo_forgiven),
                "synonym_matched": bool(a.synonym_matched),
                "undo_used": bool(a.undo_used),
                "warnings": list(a.warning_flags or []),
                "srs_stage_before": a.srs_stage_before,
                "srs_stage_after": a.srs_stage_after,
                "pair_incomplete": bool(a.pair_incomplete),
                "answered_at": _iso(a.answered_at or a.created_at),
            }
            for a in rows
        ],
    }


# --- user synonyms -------------------------------------------------------

def list_user_synonyms(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str,
) -> list[dict]:
    rows = db.execute(
        select(UserSynonym).where(
            UserSynonym.user_id == user_id,
            UserSynonym.item_type == ItemType(item_type),
            UserSynonym.item_id == uuid.UUID(item_id),
        ).order_by(UserSynonym.created_at)
    ).scalars().all()
    return [{"id": str(r.id), "synonym": r.synonym} for r in rows]


def add_user_synonym(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str, synonym: str,
) -> dict:
    row = _load_item(db, item_type, item_id)
    _require_visible(db, user_id, row)

    cleaned = " ".join((synonym or "").split())
    if not cleaned:
        raise ItemError("Enter a synonym first.", "invalid", 400)
    if len(cleaned) > MAX_SYNONYM_LENGTH:
        raise ItemError(
            f"Keep synonyms under {MAX_SYNONYM_LENGTH} characters.", "invalid", 400
        )

    normalized = normalize_term(cleaned)
    if not normalized:
        raise ItemError("That synonym is empty once normalised.", "invalid", 400)

    existing = db.execute(
        select(UserSynonym).where(
            UserSynonym.user_id == user_id,
            UserSynonym.item_type == ItemType(item_type),
            UserSynonym.item_id == row.id,
            UserSynonym.normalized == normalized,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {"id": str(existing.id), "synonym": existing.synonym, "created": False}

    count = db.execute(
        select(func.count(UserSynonym.id)).where(
            UserSynonym.user_id == user_id,
            UserSynonym.item_type == ItemType(item_type),
            UserSynonym.item_id == row.id,
        )
    ).scalar_one()
    if int(count or 0) >= MAX_USER_SYNONYMS_PER_ITEM:
        raise ItemError(
            f"You can add up to {MAX_USER_SYNONYMS_PER_ITEM} synonyms per item.",
            "limit_reached", 400,
        )

    record = UserSynonym(
        user_id=user_id, item_type=ItemType(item_type), item_id=row.id,
        synonym=cleaned, normalized=normalized,
    )
    db.add(record)
    db.flush()
    return {"id": str(record.id), "synonym": record.synonym, "created": True}


def delete_user_synonym(
    db: Session, *, user_id: uuid.UUID, synonym_id: str,
) -> None:
    try:
        pk = uuid.UUID(synonym_id)
    except (ValueError, AttributeError):
        raise ItemError("Synonym not found.", "not_found", 404) from None
    record = db.get(UserSynonym, pk)
    # Scoped by user: one learner can never delete another's synonym.
    if record is None or record.user_id != user_id:
        raise ItemError("Synonym not found.", "not_found", 404)
    db.delete(record)
    db.flush()


# --- level progression ---------------------------------------------------

def get_level_progress(
    db: Session, *, user_id: uuid.UUID, position: int,
    now: dt.datetime | None = None, language_code: str = "es-MX",
) -> dict:
    """Every item in a level with its current state — the progression page."""
    now = now or _now()
    lang = db.execute(
        select(Language).where(Language.code == language_code)
    ).scalar_one_or_none()
    if lang is None:
        raise ItemError("Curriculum not set up yet.", "no_language", 409)

    states = all_level_states(db, user_id, lang.id)
    state = next((s for s in states if s.module.position == position), None)
    if state is None:
        raise ItemError("Level not found.", "not_found", 404)
    if not state.unlocked:
        raise ItemError(
            "Finish the previous level to unlock this one.", "level_locked", 403
        )

    names = _stage_names(db, lang.id)
    vocab_ids = state.vocab_ids[:MAX_LEVEL_ITEMS]
    grammar_ids = state.grammar_ids[:MAX_LEVEL_ITEMS]

    progress_rows = {
        (_enum_value(p.item_type), p.item_id): p
        for p in db.execute(
            select(UserItemProgress).where(
                UserItemProgress.user_id == user_id,
                UserItemProgress.item_id.in_(vocab_ids + grammar_ids or [uuid.uuid4()]),
            )
        ).scalars().all()
    }
    vocab_practice = _practice_rows(db, user_id, "vocabulary", vocab_ids)
    grammar_practice = _practice_rows(db, user_id, "grammar", grammar_ids)

    items: list[dict] = []
    if vocab_ids:
        for v in db.execute(
            select(VocabularyItem).where(VocabularyItem.id.in_(vocab_ids))
            .order_by(VocabularyItem.difficulty_rank, VocabularyItem.term)
        ).scalars().all():
            items.append(_progress_tile(
                "vocabulary", v.id, v.term, v.primary_translation,
                v.part_of_speech or "",
                _enum_value(v.article), progress_rows, vocab_practice, names, now,
            ))
    if grammar_ids:
        for g in db.execute(
            select(GrammarPoint).where(GrammarPoint.id.in_(grammar_ids))
            .order_by(GrammarPoint.title)
        ).scalars().all():
            items.append(_progress_tile(
                "grammar", g.id, g.title, g.translation, g.part_of_speech or "",
                "none", progress_rows, grammar_practice, names, now,
            ))

    learned = sum(1 for i in items if i["learned"])
    return {
        "position": state.module.position,
        "title": state.module.title,
        "unlocked": state.unlocked,
        "totals": {
            "items": len(items),
            "learned": learned,
            "not_started": len(items) - learned,
            "familiar_plus": sum(1 for i in items if i["srs_stage"] >= 5),
            "fluent": sum(1 for i in items if i["srs_stage"] >= ps.FLUENT_SRS_STAGE),
            "perfect": sum(1 for i in items if i["perfect"]),
            "leeches": sum(1 for i in items if i["leech_state"] in ("leech", "critical")),
        },
        "items": items,
    }


def _progress_tile(
    item_type: str, item_id: uuid.UUID, term: str, translation: str,
    part_of_speech: str, article: str,
    progress_rows: dict, practice_rows: dict, names: list[str], now: dt.datetime,
) -> dict:
    p = progress_rows.get((item_type, item_id))
    srs_stage = int(p.srs_stage) if p else 0
    stages = _stage_map(practice_rows, item_id)
    summary = ps.perfect_progress(stages, srs_stage)
    return {
        "item_type": item_type,
        "item_id": str(item_id),
        "term": term,
        "translation": translation or "",
        "part_of_speech": part_of_speech,
        "article": article if article and article != "none" else None,
        "learned": bool(p and p.lesson_completed_at is not None),
        "srs_stage": srs_stage,
        "srs_stage_name": srs.stage_name(srs_stage) if srs_stage else "Not learned",
        "next_review_at": _iso(p.next_review_at) if p else None,
        "leech_state": _enum_value(p.leech_state) if p else "none",
        "practice_stages": stages,
        "practice_labels": {
            c: ps.stage_label(stages[c], names) for c in ps.PRACTICE_CATEGORIES
        },
        "categories_complete": summary["categories_complete"],
        "perfect": bool(p and p.perfect_at is not None),
    }


# --- perfect status ------------------------------------------------------

def refresh_perfect_status(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: uuid.UUID,
    now: dt.datetime | None = None,
) -> bool:
    """Set `perfect_at` when every category is at Cinco and the item is Fluent.

    Called after practice grading. Idempotent: once earned, `perfect_at` is left
    alone (it records when the learner got there, not whether they still are).
    """
    now = now or _now()
    progress = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == ItemType(item_type),
            UserItemProgress.item_id == item_id,
        )
    ).scalar_one_or_none()
    if progress is None:
        return False
    if progress.perfect_at is not None:
        return True

    rows = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.user_id == user_id,
            UserItemPracticeStage.item_type == ItemType(item_type),
            UserItemPracticeStage.item_id == item_id,
        )
    ).scalars().all()
    stages = {_enum_value(r.category): ps.clamp_stage(r.stage) for r in rows}
    if ps.qualifies_for_perfect(stages, int(progress.srs_stage or 0)):
        progress.perfect_at = now
        db.flush()
        return True
    return False


def practice_category_for(category: str) -> PracticeCategory:
    return PracticeCategory(category)

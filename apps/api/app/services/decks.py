"""Decks — a browsable, read-only view of what the learner has unlocked.

A "deck" is a collection you can flip through: all your vocabulary, all your
grammar, all the intermissions you've seen. This is the reference surface the
header now points at, replacing the reviews link (reviews still exist; they just
aren't the top-level nav item any more).

Everything is read-only and scoped to unlocked content. A deck never reveals an
item from a locked level, and it never carries the private answer key — the same
rules the item detail endpoint follows.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain import srs
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.platform import Intermission, UserIntermissionView
from app.models.progress import UserItemProgress
from app.services.levels import all_level_states

DECK_TYPES = ("vocabulary", "grammar", "intermissions")
MAX_PAGE = 100


class DeckError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


def _enum_value(value: object) -> str:
    return getattr(value, "value", value) if value is not None else ""


def _spanish(db: Session) -> Language | None:
    return db.execute(
        select(Language).where(Language.code == "es-MX")
    ).scalar_one_or_none()


def _unlocked_module_ids(db: Session, user_id: uuid.UUID, lang_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        s.module.id
        for s in all_level_states(db, user_id, lang_id)
        if s.unlocked
    ]


def list_decks(db: Session, *, user_id: uuid.UUID) -> list[dict]:
    """The three decks with a live count for each."""
    lang = _spanish(db)
    if lang is None:
        return _empty_decks()

    module_ids = _unlocked_module_ids(db, user_id, lang.id)

    vocab_count = 0
    grammar_count = 0
    if module_ids:
        vocab_count = db.execute(
            select(func.count(VocabularyItem.id)).where(
                VocabularyItem.module_id.in_(module_ids),
                VocabularyItem.status == ContentStatus.published,
                VocabularyItem.deleted_at.is_(None),
            )
        ).scalar_one()
        grammar_count = db.execute(
            select(func.count(GrammarPoint.id)).where(
                GrammarPoint.module_id.in_(module_ids),
                GrammarPoint.status == ContentStatus.published,
                GrammarPoint.deleted_at.is_(None),
            )
        ).scalar_one()

    intermission_count = db.execute(
        select(func.count(UserIntermissionView.id)).where(
            UserIntermissionView.user_id == user_id,
            UserIntermissionView.viewed_at.isnot(None),
        )
    ).scalar_one()

    return [
        {"type": "vocabulary", "title": "vocabulary",
         "description": "every word you've unlocked, in one place",
         "count": int(vocab_count or 0)},
        {"type": "grammar", "title": "grammar",
         "description": "the grammar points you've unlocked",
         "count": int(grammar_count or 0)},
        {"type": "intermissions", "title": "intermissions",
         "description": "the short readings you've come across",
         "count": int(intermission_count or 0)},
    ]


def _empty_decks() -> list[dict]:
    return [
        {"type": "vocabulary", "title": "vocabulary",
         "description": "every word you've unlocked, in one place", "count": 0},
        {"type": "grammar", "title": "grammar",
         "description": "the grammar points you've unlocked", "count": 0},
        {"type": "intermissions", "title": "intermissions",
         "description": "the short readings you've come across", "count": 0},
    ]


def deck_items(
    db: Session, *, user_id: uuid.UUID, deck_type: str,
    limit: int = 50, offset: int = 0,
) -> dict:
    if deck_type not in DECK_TYPES:
        raise DeckError("Unknown deck.", "not_found", 404)
    limit = max(1, min(int(limit), MAX_PAGE))
    offset = max(0, int(offset))

    if deck_type == "intermissions":
        return _intermission_deck(db, user_id, limit, offset)

    lang = _spanish(db)
    if lang is None:
        return {"type": deck_type, "total": 0, "limit": limit, "offset": offset, "items": []}
    module_ids = _unlocked_module_ids(db, user_id, lang.id)
    if not module_ids:
        return {"type": deck_type, "total": 0, "limit": limit, "offset": offset, "items": []}

    return (
        _vocab_deck(db, user_id, module_ids, limit, offset)
        if deck_type == "vocabulary"
        else _grammar_deck(db, user_id, module_ids, limit, offset)
    )


def _progress_map(
    db: Session, user_id: uuid.UUID, item_type: str, ids: list[uuid.UUID],
) -> dict[uuid.UUID, UserItemProgress]:
    if not ids:
        return {}
    rows = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == ItemType(item_type),
            UserItemProgress.item_id.in_(ids),
        )
    ).scalars().all()
    return {p.item_id: p for p in rows}


def _srs_summary(p: UserItemProgress | None) -> dict:
    stage = int(p.srs_stage) if p else 0
    return {
        "learned": bool(p and p.lesson_completed_at is not None),
        "srs_stage": stage,
        "srs_stage_name": srs.stage_name(stage) if stage else "not learned",
        "next_review_at": _iso(p.next_review_at) if p else None,
    }


def _vocab_deck(db, user_id, module_ids, limit, offset) -> dict:
    total = db.execute(
        select(func.count(VocabularyItem.id)).where(
            VocabularyItem.module_id.in_(module_ids),
            VocabularyItem.status == ContentStatus.published,
            VocabularyItem.deleted_at.is_(None),
        )
    ).scalar_one()
    rows = db.execute(
        select(VocabularyItem, Module.position)
        .join(Module, Module.id == VocabularyItem.module_id)
        .where(
            VocabularyItem.module_id.in_(module_ids),
            VocabularyItem.status == ContentStatus.published,
            VocabularyItem.deleted_at.is_(None),
        )
        .order_by(Module.position, VocabularyItem.difficulty_rank, VocabularyItem.term)
        .limit(limit).offset(offset)
    ).all()

    progress = _progress_map(db, user_id, "vocabulary", [v.id for v, _ in rows])
    items = []
    for v, position in rows:
        article = _enum_value(v.article)
        items.append({
            "item_type": "vocabulary", "item_id": str(v.id),
            "term": v.term, "translation": v.primary_translation or "",
            "part_of_speech": v.part_of_speech or "",
            "article": article if article and article != "none" else None,
            "level": position,
            **_srs_summary(progress.get(v.id)),
        })
    return {"type": "vocabulary", "total": int(total or 0),
            "limit": limit, "offset": offset, "items": items}


def _grammar_deck(db, user_id, module_ids, limit, offset) -> dict:
    total = db.execute(
        select(func.count(GrammarPoint.id)).where(
            GrammarPoint.module_id.in_(module_ids),
            GrammarPoint.status == ContentStatus.published,
            GrammarPoint.deleted_at.is_(None),
        )
    ).scalar_one()
    rows = db.execute(
        select(GrammarPoint, Module.position)
        .join(Module, Module.id == GrammarPoint.module_id)
        .where(
            GrammarPoint.module_id.in_(module_ids),
            GrammarPoint.status == ContentStatus.published,
            GrammarPoint.deleted_at.is_(None),
        )
        .order_by(Module.position, GrammarPoint.title)
        .limit(limit).offset(offset)
    ).all()

    progress = _progress_map(db, user_id, "grammar", [g.id for g, _ in rows])
    items = []
    for g, position in rows:
        items.append({
            "item_type": "grammar", "item_id": str(g.id),
            "term": g.title, "translation": g.translation or "",
            "part_of_speech": g.part_of_speech or "",
            "article": None, "level": position,
            **_srs_summary(progress.get(g.id)),
        })
    return {"type": "grammar", "total": int(total or 0),
            "limit": limit, "offset": offset, "items": items}


def _intermission_deck(db, user_id, limit, offset) -> dict:
    base = (
        select(Intermission, UserIntermissionView.viewed_at)
        .join(UserIntermissionView,
              UserIntermissionView.intermission_id == Intermission.id)
        .where(
            UserIntermissionView.user_id == user_id,
            UserIntermissionView.viewed_at.isnot(None),
            Intermission.deleted_at.is_(None),
        )
    )
    total = db.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()
    rows = db.execute(
        base.order_by(UserIntermissionView.viewed_at.desc()).limit(limit).offset(offset)
    ).all()
    items = [
        {
            "item_type": "intermission", "item_id": str(row.id),
            "term": row.title or "", "translation": "",
            "body": row.body_rich or "",
            "kind": (row.trigger or {}).get("category", "note")
            if isinstance(row.trigger, dict) else "note",
            "viewed_at": _iso(viewed),
        }
        for row, viewed in rows
    ]
    return {"type": "intermissions", "total": int(total or 0),
            "limit": limit, "offset": offset, "items": items}

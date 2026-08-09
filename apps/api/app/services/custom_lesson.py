"""Selectable items for the Customize Lessons page (§15/§20, by request).

Read-only: lists the published items in the learner's active language that they
haven't started yet (no UserItemProgress row), grouped by level. Each item carries
what the customize UI needs to show and filter it — term, translation, item type,
and part of speech (used as the "theme" grouping until real lesson themes are
stored). No writes, no side effects — safe to call on a GET.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.models.curriculum import GrammarPoint, Module, VocabularyItem
from app.models.progress import UserItemProgress


def _started_keys(db: Session, user_id: uuid.UUID) -> set[tuple[str, str]]:
    rows = db.execute(
        select(UserItemProgress.item_type, UserItemProgress.item_id)
        .where(UserItemProgress.user_id == user_id)
    ).all()
    out: set[tuple[str, str]] = set()
    for item_type, item_id in rows:
        t = item_type.value if hasattr(item_type, "value") else str(item_type)
        out.add((t, str(item_id)))
    return out


def _published(db: Session, model, module_id) -> list:
    return db.execute(
        select(model).where(
            model.module_id == module_id,
            model.status == ContentStatus.published,
            model.deleted_at.is_(None),
        )
    ).scalars().all()


def selectable_items(db: Session, user_id: uuid.UUID) -> list[dict]:
    from app.services.languages import get_active

    lang = get_active(db, user_id=user_id)
    if lang is None:
        return []
    modules = db.execute(
        select(Module).where(
            Module.language_id == lang.id,
            Module.status == ContentStatus.published,
        ).order_by(Module.position)
    ).scalars().all()

    started = _started_keys(db, user_id)
    levels: list[dict] = []
    for m in modules:
        items: list[dict] = []
        for v in _published(db, VocabularyItem, m.id):
            if ("vocabulary", str(v.id)) in started:
                continue
            items.append({
                "item_type": "vocabulary",
                "item_id": str(v.id),
                "term": v.term,
                "translation": v.primary_translation or "",
                "part_of_speech": (v.part_of_speech or "other"),
            })
        for g in _published(db, GrammarPoint, m.id):
            if ("grammar", str(g.id)) in started:
                continue
            items.append({
                "item_type": "grammar",
                "item_id": str(g.id),
                "term": getattr(g, "title", "") or "",
                "translation": (getattr(g, "primary_translation", None)
                                or getattr(g, "summary", None) or ""),
                "part_of_speech": "grammar",
            })
        if items:
            levels.append({"level": m.position, "title": m.title, "items": items})
    return levels

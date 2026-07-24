"""Level unlock state — one shared source of truth.

This logic used to live as `_all_level_states` inside `api/routes/learn.py`.
Slice 8 added two more consumers (the item detail page and the level progression
page), and three copies of an unlock rule is how a gate quietly stops matching
itself. It moves here; `learn.py` now delegates.

Level 1 is always open. Level N opens once level N-1 reaches the Familiar-1
threshold (see `domain.curriculum.level_unlock_progress`). Everything is loaded
up front — modules, published item ids, the user's progress — so evaluating ten
levels is three queries, not thirty.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain.curriculum import level_unlock_progress
from app.models.curriculum import GrammarPoint, Module, VocabularyItem
from app.models.progress import UserItemProgress


@dataclass
class LevelState:
    module: Module
    vocab_ids: list[uuid.UUID]
    grammar_ids: list[uuid.UUID]
    unlocked: bool
    progress: dict | None


def all_level_states(
    db: Session, user_id: uuid.UUID, lang_id: uuid.UUID,
) -> list[LevelState]:
    """Unlock state for every level, computed in one pass."""
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

    states: list[LevelState] = []
    prev_state: LevelState | None = None
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
        state = LevelState(module=m, vocab_ids=v_ids, grammar_ids=g_ids,
                           unlocked=unlocked, progress=progress)
        states.append(state)
        prev_state = state
    return states


def state_for_module(
    states: list[LevelState], module_id: uuid.UUID,
) -> LevelState | None:
    for st in states:
        if st.module.id == module_id:
            return st
    return None


def is_module_unlocked(
    db: Session, user_id: uuid.UUID, module: Module,
) -> bool:
    """Server-side gate for anything scoped to a single level."""
    st = state_for_module(
        all_level_states(db, user_id, module.language_id), module.id
    )
    return bool(st and st.unlocked)

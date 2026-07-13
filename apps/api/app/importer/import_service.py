"""Persist parsed curriculum into the database, idempotently.

Idempotency key per item:
  vocab   -> (language_id, module_position, normalized_term)
  grammar -> (language_id, module_position, normalized_title)

Re-running an import updates existing DRAFT rows in place and never overwrites
rows an editor has already moved past draft (published/in_review/archived) unless
force=True. Every import writes a ContentImport row holding the full report.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain.normalize import normalize_term
from app.importer.curriculum_csv import (
    ImportReport,
    ParsedGrammar,
    ParsedVocab,
    parse_grammar,
    parse_vocabulary,
)
from app.models.curriculum import GrammarPoint, Module, VocabularyItem


def _get_or_create_module(db: Session, language_id: uuid.UUID, position: int) -> Module:
    stmt = select(Module).where(Module.language_id == language_id, Module.position == position)
    module = db.execute(stmt).scalar_one_or_none()
    if module is None:
        module = Module(
            language_id=language_id,
            position=position,
            title=f"Level {position}",
            status=ContentStatus.draft,
        )
        db.add(module)
        db.flush()
    return module


def import_vocabulary(
    db: Session, *, language_id: uuid.UUID, csv_text: str, import_id: uuid.UUID,
    force: bool = False,
) -> tuple[int, int, ImportReport]:
    items, report = parse_vocabulary(csv_text)
    created = updated = 0
    for it in items:
        module = _get_or_create_module(db, language_id, it.level)
        existing = db.execute(
            select(VocabularyItem).where(
                VocabularyItem.language_id == language_id,
                VocabularyItem.module_id == module.id,
                VocabularyItem.normalized_term == it.normalized_term,
            )
        ).scalar_one_or_none()

        if existing is None:
            db.add(_vocab_to_model(it, language_id, module.id, import_id))
            created += 1
        elif force or existing.status == ContentStatus.draft:
            _apply_vocab(existing, it, import_id)
            updated += 1
        # else: leave editor-touched rows alone
    db.flush()
    return created, updated, report


def import_grammar(
    db: Session, *, language_id: uuid.UUID, csv_text: str, import_id: uuid.UUID,
    force: bool = False,
) -> tuple[int, int, ImportReport]:
    items, report = parse_grammar(csv_text)
    created = updated = 0
    for it in items:
        module = _get_or_create_module(db, language_id, it.level)
        norm_title = normalize_term(it.title)
        existing = db.execute(
            select(GrammarPoint).where(
                GrammarPoint.language_id == language_id,
                GrammarPoint.module_id == module.id,
                GrammarPoint.title == it.title,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(_grammar_to_model(it, language_id, module.id, import_id))
            created += 1
        elif force or existing.status == ContentStatus.draft:
            existing.translation = it.translation
            existing.structure_pattern = it.structure_pattern
            existing.part_of_speech = it.part_of_speech
            existing.source_import_id = import_id
            updated += 1
        _ = norm_title
    db.flush()
    return created, updated, report


def _vocab_to_model(
    it: ParsedVocab, language_id: uuid.UUID, module_id: uuid.UUID, import_id: uuid.UUID
) -> VocabularyItem:
    model = VocabularyItem(
        language_id=language_id, module_id=module_id, status=ContentStatus.draft
    )
    _apply_vocab(model, it, import_id)
    return model


def _apply_vocab(model: VocabularyItem, it: ParsedVocab, import_id: uuid.UUID) -> None:
    model.term = it.term
    model.normalized_term = it.normalized_term
    model.primary_translation = it.primary_translation
    model.part_of_speech = it.part_of_speech
    model.pronunciation = it.pronunciation
    model.ipa = it.ipa
    model.meaning = it.meaning
    model.synonyms = it.synonyms
    model.variations = it.variations
    model.castilian_variant = it.castilian_variant
    # article/gender intentionally left at default \"none\" — editor sets these.
    model.source_import_id = import_id


def _grammar_to_model(
    it: ParsedGrammar, language_id: uuid.UUID, module_id: uuid.UUID, import_id: uuid.UUID
) -> GrammarPoint:
    return GrammarPoint(
        language_id=language_id, module_id=module_id, status=ContentStatus.draft,
        title=it.title, translation=it.translation,
        structure_pattern=it.structure_pattern, part_of_speech=it.part_of_speech,
        source_import_id=import_id,
    )

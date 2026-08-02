"""DEMO SEED — Tagalog (spec §1, second language).

Registers Tagalog as a selectable language and adds a small, clearly-marked demo
Level 1 (a handful of published words + one grammar point) so selecting Tagalog
shows real content immediately. This is DEMO data, not the production curriculum —
production Tagalog is expected to arrive via an admin CSV import, exactly like
Spanish. Delete or skip this if you'll import a real CSV. Idempotent.

Run standalone:  python -m app.db.seed_tagalog
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem

CODE = "tl-PH"

# Tagalog counts one..five — used for practice-stage names (§10).
_STAGE_NAMES = ["Isa", "Dalawa", "Tatlo", "Apat", "Lima"]

# DEMO vocabulary (original, hand-written; safe to delete).
_VOCAB = [
    {"term": "kumusta", "translation": "hello / how are you", "pos": "interjection"},
    {"term": "salamat", "translation": "thank you", "pos": "interjection"},
    {"term": "oo", "translation": "yes", "pos": "adverb"},
    {"term": "hindi", "translation": "no / not", "pos": "adverb"},
    {"term": "tubig", "translation": "water", "pos": "noun"},
    {"term": "pagkain", "translation": "food", "pos": "noun"},
]

_GRAMMAR = [
    {
        "title": "ang (subject marker)",
        "translation": "the (marks the subject)",
        "meaning": "Ang marks the subject/topic of a Tagalog sentence, e.g. "
                   "'Ang tubig' = 'the water'.",
    },
]


def seed_tagalog(db: Session, *, with_content: bool = True) -> dict:
    """Ensure Tagalog exists (and, by default, a demo Level 1). Returns a summary."""
    lang = db.execute(select(Language).where(Language.code == CODE)).scalar_one_or_none()
    created_lang = False
    if lang is None:
        lang = Language(code=CODE, name="Tagalog", native_name="Tagalog",
                        stage_names=_STAGE_NAMES, enabled=True)
        db.add(lang)
        db.flush()
        created_lang = True

    summary = {"language": created_lang, "vocab": 0, "grammar": 0}
    if not with_content:
        db.commit()
        return summary

    module = db.execute(
        select(Module).where(Module.language_id == lang.id, Module.position == 1)
    ).scalar_one_or_none()
    if module is None:
        module = Module(language_id=lang.id, position=1, title="Level 1",
                        description="Demo Tagalog basics.", status=ContentStatus.published)
        db.add(module)
        db.flush()

    existing_terms = set(db.execute(
        select(VocabularyItem.normalized_term).where(VocabularyItem.language_id == lang.id)
    ).scalars().all())
    for i, v in enumerate(_VOCAB):
        if v["term"] in existing_terms:
            continue
        db.add(VocabularyItem(
            language_id=lang.id, module_id=module.id, term=v["term"],
            normalized_term=v["term"], primary_translation=v["translation"],
            part_of_speech=v["pos"], difficulty_rank=i + 1, status=ContentStatus.published,
        ))
        summary["vocab"] += 1

    existing_titles = set(db.execute(
        select(GrammarPoint.title).where(GrammarPoint.language_id == lang.id)
    ).scalars().all())
    for g in _GRAMMAR:
        if g["title"] in existing_titles:
            continue
        db.add(GrammarPoint(
            language_id=lang.id, module_id=module.id, title=g["title"],
            translation=g["translation"], meaning=g["meaning"], status=ContentStatus.published,
        ))
        summary["grammar"] += 1

    db.commit()
    return summary


if __name__ == "__main__":  # pragma: no cover
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        result = seed_tagalog(session)
        print(f"tagalog seed: {result}")

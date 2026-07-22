"""Seed practice data: verb conjugations and example sentences.

The source CSV leaves part-of-speech blank on nearly every row, so conjugation
practice would find no verbs and fill-in-the-blank would find no sentences. This
script fixes both against whatever vocabulary is already imported:

  1. tags known verbs with part_of_speech='verb'
  2. writes their conjugation tables into verbs_meta
  3. creates example sentences and links them to the words they exercise
     (with an explicit cloze_answer so the blank is unambiguous)

Idempotent: safe to re-run. Only touches words that actually exist in the DB.

Usage:  docker compose exec api python -m app.db.seed_practice
"""
from __future__ import annotations

import sys
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.db.seed_data.practice_data import EXAMPLE_SENTENCES, all_conjugations
from app.db.session import SessionLocal
from app.models.curriculum import Language, Sentence, SentenceLink, VerbMeta, VocabularyItem
from app.models.enums import ItemType

LANGUAGE_CODE = "es-MX"


def _language(db: Session) -> Language:
    lang = db.execute(
        select(Language).where(Language.code == LANGUAGE_CODE)
    ).scalar_one_or_none()
    if lang is None:
        raise SystemExit("Language es-MX not found. Run `python -m app.db.seed` first.")
    return lang


def seed_verbs(db: Session, language_id: uuid.UUID) -> tuple[int, int]:
    """Tag verbs and store their conjugations. Returns (tagged, conjugated)."""
    tables = all_conjugations()
    tagged = conjugated = 0

    for infinitive, data in tables.items():
        item = db.execute(
            select(VocabularyItem).where(
                VocabularyItem.language_id == language_id,
                VocabularyItem.term == infinitive,
                VocabularyItem.deleted_at.is_(None),
            )
        ).scalars().first()
        if item is None:
            continue   # this verb isn't in the user's curriculum; skip quietly

        if (item.part_of_speech or "").lower() != "verb":
            item.part_of_speech = "verb"
            tagged += 1

        meta = db.get(VerbMeta, item.id)
        if meta is None:
            meta = VerbMeta(vocabulary_item_id=item.id)
            db.add(meta)
        meta.conjugation_class = data["class"]
        meta.is_regular = data["regular"]
        meta.conjugations = data["conjugations"]
        conjugated += 1

    return tagged, conjugated


def seed_sentences(db: Session, language_id: uuid.UUID) -> int:
    """Create example sentences and link them to the words they contain."""
    created = 0
    for text_es, text_en, target in EXAMPLE_SENTENCES:
        item = db.execute(
            select(VocabularyItem).where(
                VocabularyItem.language_id == language_id,
                VocabularyItem.term == target,
                VocabularyItem.deleted_at.is_(None),
            )
        ).scalars().first()
        if item is None:
            continue   # target word not in this curriculum

        existing = db.execute(
            select(Sentence).where(
                Sentence.language_id == language_id, Sentence.text_es == text_es
            )
        ).scalars().first()
        if existing is None:
            existing = Sentence(
                language_id=language_id, text_es=text_es, text_en=text_en,
                difficulty="sentence", status=ContentStatus.published,
            )
            db.add(existing)
            db.flush()
            created += 1
        elif existing.status != ContentStatus.published:
            existing.status = ContentStatus.published

        link = db.execute(
            select(SentenceLink).where(
                SentenceLink.sentence_id == existing.id,
                SentenceLink.item_type == ItemType.vocabulary,
                SentenceLink.item_id == item.id,
            )
        ).scalars().first()
        if link is None:
            db.add(SentenceLink(
                sentence_id=existing.id, item_type=ItemType.vocabulary,
                item_id=item.id, role="example", cloze_answer=target,
            ))
    return created


def main() -> None:
    with SessionLocal() as db:
        lang = _language(db)

        total_vocab = db.execute(
            select(VocabularyItem).where(VocabularyItem.language_id == lang.id).limit(1)
        ).scalars().first()
        if total_vocab is None:
            print("No vocabulary found. Run `python -m app.db.seed_curriculum` first.")
            sys.exit(1)

        print("→ Seeding verb conjugations…")
        tagged, conjugated = seed_verbs(db, lang.id)
        print(f"  tagged {tagged} words as verbs, wrote {conjugated} conjugation tables")

        print("→ Seeding example sentences…")
        created = seed_sentences(db, lang.id)
        print(f"  created {created} sentences (linked to matching words)")

        db.commit()
        print("✓ Practice data seeded.")
        print("  fill-in-the-blank and conjugation practice now have content.")


if __name__ == "__main__":  # pragma: no cover
    main()

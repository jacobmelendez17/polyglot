"""Seed the Spanish curriculum from the bundled CSVs and publish it.

Unlike the admin import (which loads content as *drafts* for review), this script
is meant to get a working, playable curriculum into the database in one step:
it imports every vocabulary and grammar row, then PUBLISHES the items and their
modules so lessons and reviews are immediately available.

Idempotent: re-running re-imports (updating existing draft rows) and re-publishes.
It never clobbers items an editor has manually moved to a non-draft state unless
--force is passed.

Usage (from apps/api):
    python -m app.db.seed_curriculum
    python -m app.db.seed_curriculum --force        # also overwrite edited rows
    python -m app.db.seed_curriculum --drafts-only   # import but don't publish

Inside Docker:
    docker compose exec api python -m app.db.seed_curriculum
"""
from __future__ import annotations

import argparse
import pathlib
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.db.session import SessionLocal
from app.importer.import_service import import_grammar, import_vocabulary
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem

DATA_DIR = pathlib.Path(__file__).parent / "seed_data"
VOCAB_CSV = DATA_DIR / "spanish_vocabulary.csv"
GRAMMAR_CSV = DATA_DIR / "spanish_grammar.csv"
LANGUAGE_CODE = "es-MX"


def _language(db: Session) -> Language:
    lang = db.execute(
        select(Language).where(Language.code == LANGUAGE_CODE)
    ).scalar_one_or_none()
    if lang is None:
        raise SystemExit(
            f"Language {LANGUAGE_CODE} not found. Run `python -m app.db.seed` first "
            "to create the base languages."
        )
    return lang


def _publish_all(db: Session, language_id: uuid.UUID) -> tuple[int, int, int]:
    """Publish every draft vocab item, grammar point, and their modules."""
    vocab_published = db.execute(
        update(VocabularyItem)
        .where(
            VocabularyItem.language_id == language_id,
            VocabularyItem.status == ContentStatus.draft,
            VocabularyItem.deleted_at.is_(None),
        )
        .values(status=ContentStatus.published)
    ).rowcount
    grammar_published = db.execute(
        update(GrammarPoint)
        .where(
            GrammarPoint.language_id == language_id,
            GrammarPoint.status == ContentStatus.draft,
            GrammarPoint.deleted_at.is_(None),
        )
        .values(status=ContentStatus.published)
    ).rowcount
    modules_published = db.execute(
        update(Module)
        .where(
            Module.language_id == language_id,
            Module.status == ContentStatus.draft,
        )
        .values(status=ContentStatus.published)
    ).rowcount
    return vocab_published, grammar_published, modules_published


def seed_curriculum(*, force: bool = False, publish: bool = True) -> None:
    if not VOCAB_CSV.exists():
        raise SystemExit(f"Missing {VOCAB_CSV}")

    with SessionLocal() as db:
        lang = _language(db)

        print("→ Importing vocabulary…")
        v_created, v_updated, v_report = import_vocabulary(
            db, language_id=lang.id, csv_text=VOCAB_CSV.read_text(encoding="utf-8-sig"),
            import_id=uuid.uuid4(), force=force,
        )
        print(f"  vocabulary: {v_created} created, {v_updated} updated, "
              f"{len(v_report.errors)} errors, {len(v_report.warnings)} warnings")

        if GRAMMAR_CSV.exists():
            print("→ Importing grammar…")
            g_created, g_updated, g_report = import_grammar(
                db, language_id=lang.id, csv_text=GRAMMAR_CSV.read_text(encoding="utf-8-sig"),
                import_id=uuid.uuid4(), force=force,
            )
            print(f"  grammar: {g_created} created, {g_updated} updated, "
                  f"{len(g_report.errors)} errors, {len(g_report.warnings)} warnings")

        if publish:
            print("→ Publishing content…")
            vp, gp, mp = _publish_all(db, lang.id)
            print(f"  published: {vp} vocab, {gp} grammar, {mp} modules")
        else:
            print("→ Skipping publish (--drafts-only): content stays as draft.")

        db.commit()
        print("✓ Curriculum seed complete.")
        if publish:
            print("  Lessons should now appear under 'levels' in the app.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed and publish the Spanish curriculum.")
    parser.add_argument("--force", action="store_true",
                        help="overwrite items an editor already moved past draft")
    parser.add_argument("--drafts-only", action="store_true",
                        help="import but do not publish (leave everything as draft)")
    args = parser.parse_args()
    seed_curriculum(force=args.force, publish=not args.drafts_only)


if __name__ == "__main__":  # pragma: no cover
    main()

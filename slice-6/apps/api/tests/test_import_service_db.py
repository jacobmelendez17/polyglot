"""DB-backed tests: importing into Postgres is idempotent, creates drafts,
and respects the noun-only-article constraint. Uses real uploaded CSVs."""
import uuid

from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.importer.import_service import import_grammar, import_vocabulary
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem


def _spanish(db):
    seed(db)
    return db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()


def test_import_creates_drafts_and_modules(db, real_csvs):
    lang = _spanish(db)
    imp = uuid.uuid4()
    created, updated, rep = import_vocabulary(
        db, language_id=lang.id, csv_text=real_csvs["vocab"], import_id=imp
    )
    db.commit()
    # 468 CSV rows - 1 hard error (nosotros) - 2 in-level duplicates
    # (el martes @L3, algo @L10, both merged) = 465 distinct items.
    assert created == 465
    assert updated == 0
    # 10 levels of modules created
    module_count = db.execute(select(func.count()).select_from(Module)).scalar_one()
    assert module_count == 10
    # everything is draft
    non_draft = db.execute(
        select(func.count()).select_from(VocabularyItem).where(
            VocabularyItem.status != ContentStatus.draft
        )
    ).scalar_one()
    assert non_draft == 0


def test_import_is_idempotent(db, real_csvs):
    lang = _spanish(db)
    import_vocabulary(db, language_id=lang.id, csv_text=real_csvs["vocab"], import_id=uuid.uuid4())
    db.commit()
    first = db.execute(select(func.count()).select_from(VocabularyItem)).scalar_one()
    # second run: no duplicates, all updates
    created, updated, _ = import_vocabulary(
        db, language_id=lang.id, csv_text=real_csvs["vocab"], import_id=uuid.uuid4()
    )
    db.commit()
    second = db.execute(select(func.count()).select_from(VocabularyItem)).scalar_one()
    assert first == second
    assert created == 0
    assert updated == first


def test_import_does_not_overwrite_published(db, real_csvs):
    lang = _spanish(db)
    import_vocabulary(db, language_id=lang.id, csv_text=real_csvs["vocab"], import_id=uuid.uuid4())
    db.commit()
    item = db.execute(select(VocabularyItem)).scalars().first()
    item.status = ContentStatus.published
    item.primary_translation = "EDITOR VALUE"
    db.commit()
    # re-import should skip the published row
    import_vocabulary(db, language_id=lang.id, csv_text=real_csvs["vocab"], import_id=uuid.uuid4())
    db.commit()
    db.refresh(item)
    assert item.primary_translation == "EDITOR VALUE"


def test_grammar_import(db, real_csvs):
    lang = _spanish(db)
    created, _, rep = import_grammar(
        db, language_id=lang.id, csv_text=real_csvs["grammar"], import_id=uuid.uuid4()
    )
    db.commit()
    assert created == 59
    assert db.execute(select(func.count()).select_from(GrammarPoint)).scalar_one() == 59


def test_article_constraint_rejects_non_noun(db):
    """DB-level guard: a non-noun cannot carry an article (PLANNING §6)."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    lang = _spanish(db)
    module = Module(language_id=lang.id, position=1, title="L1")
    db.add(module)
    db.flush()
    bad = VocabularyItem(
        language_id=lang.id, module_id=module.id, term="comer",
        normalized_term="comer", part_of_speech="verb", article="el",
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_seed_is_idempotent(db):
    seed(db)
    seed(db)  # second call must not duplicate
    langs = db.execute(select(func.count()).select_from(Language)).scalar_one()
    assert langs == 2

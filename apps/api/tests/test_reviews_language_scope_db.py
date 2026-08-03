"""The review queue follows the active language (§1, §32, R-64).

Items you've studied in one language shouldn't surface while you're studying
another. `due_items` scopes to the learner's active language, so switching the
header language switches which reviews are due.
"""
import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from app.db.seed import seed
from app.db.seed_tagalog import seed_tagalog
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.identity import Profile
from app.models.progress import UserItemProgress
from app.services import reviews as review_svc
from app.services.languages import set_active


def _due_row(user_id, item_id):
    return UserItemProgress(
        user_id=user_id, item_type=ItemType.vocabulary, item_id=item_id,
        srs_stage=1, next_review_at=dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=1),
    )


def _vocab(db, lang_id, module_id, term):
    v = VocabularyItem(language_id=lang_id, module_id=module_id, term=term,
                       normalized_term=term, primary_translation=term + "-en",
                       part_of_speech="noun", status="published", difficulty_rank=1)
    db.add(v); db.flush()
    return v


@pytest.fixture()
def two_languages(db):
    seed(db)
    seed_tagalog(db, with_content=False)
    es = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    tl = db.execute(select(Language).where(Language.code == "tl-PH")).scalar_one()
    es_mod = Module(language_id=es.id, position=1, title="ES 1", status="published")
    tl_mod = Module(language_id=tl.id, position=1, title="TL 1", status="published")
    db.add_all([es_mod, tl_mod]); db.flush()
    return es, tl, es_mod, tl_mod


def test_due_items_scope_to_active_language(db, two_languages):
    es, tl, es_mod, tl_mod = two_languages
    uid = uuid.uuid4()
    db.add(Profile(user_id=uid, active_language_code="es-MX"))
    es_item = _vocab(db, es.id, es_mod.id, "hola")
    tl_item = _vocab(db, tl.id, tl_mod.id, "kumusta")
    db.add_all([_due_row(uid, es_item.id), _due_row(uid, tl_item.id)])
    db.commit()

    # active = Spanish → only the Spanish item is due
    due = review_svc.due_items(db, uid)
    assert {p.item_id for p in due} == {es_item.id}

    # switch to Tagalog → only the Tagalog item is due
    set_active(db, user_id=uid, code="tl-PH"); db.commit()
    due = review_svc.due_items(db, uid)
    assert {p.item_id for p in due} == {tl_item.id}


def test_scoping_respects_limit_after_filtering(db, two_languages):
    """The limit is applied AFTER language filtering, so a flood of other-language
    items can't crowd out the active language's due reviews."""
    es, tl, es_mod, tl_mod = two_languages
    uid = uuid.uuid4()
    db.add(Profile(user_id=uid, active_language_code="es-MX"))
    # many Tagalog items with earlier due times, one Spanish item
    for i in range(5):
        it = _vocab(db, tl.id, tl_mod.id, f"tl{i}")
        r = _due_row(uid, it.id)
        r.next_review_at = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=2)
        db.add(r)
    es_item = _vocab(db, es.id, es_mod.id, "hola")
    db.add(_due_row(uid, es_item.id))
    db.commit()

    due = review_svc.due_items(db, uid, limit=3)
    assert [p.item_id for p in due] == [es_item.id]  # Spanish survives the limit

"""Feature unlock end-to-end: completed-levels counting drives what's unlocked."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.identity import User
from app.models.progress import UserItemProgress


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="feat@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "F", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def _level_with_items(db, position, n=2):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m = Module(language_id=lang.id, position=position, title=f"L{position}",
               status=ContentStatus.published)
    db.add(m); db.flush()
    items = []
    for i in range(n):
        v = VocabularyItem(language_id=lang.id, module_id=m.id, term=f"l{position}w{i}",
                           normalized_term=f"l{position}w{i}", primary_translation=f"w{i}",
                           part_of_speech="noun", status=ContentStatus.published,
                           difficulty_rank=1)
        db.add(v); items.append(v)
    db.flush()
    return m, items


def _bring_to_familiar(db, uid, items):
    for it in items:
        db.add(UserItemProgress(user_id=uid, item_type=ItemType.vocabulary,
                                item_id=it.id, srs_stage=5))  # Familiar 1
    db.commit()


def test_features_requires_auth(client):
    assert client.get("/api/v1/features").status_code == 401


def test_fresh_user_has_only_level_one_features(client, db):
    hdr, _ = _signup(client)
    body = client.get("/api/v1/features", headers=hdr).json()
    assert body["completed_levels"] == 0
    by = {f["feature"]: f for f in body["features"]}
    # nothing completed yet → even reviews (unlock 1) shows locked
    assert by["reviews"]["unlocked"] is False
    assert by["listening"]["unlocked"] is False


def test_completing_levels_unlocks_features(client, db):
    hdr, uid = _signup(client, "prog@example.com")
    _, items1 = _level_with_items(db, 1)
    _, items2 = _level_with_items(db, 2)
    # complete level 1 only
    _bring_to_familiar(db, uid, items1)

    body = client.get("/api/v1/features", headers=hdr).json()
    assert body["completed_levels"] == 1
    by = {f["feature"]: f for f in body["features"]}
    assert by["reviews"]["unlocked"] and by["reading"]["unlocked"]
    assert not by["listening"]["unlocked"]           # needs 2

    # complete level 2 as well
    _bring_to_familiar(db, uid, items2)
    body = client.get("/api/v1/features", headers=hdr).json()
    assert body["completed_levels"] == 2
    by = {f["feature"]: f for f in body["features"]}
    assert by["listening"]["unlocked"] and by["testing_app"]["unlocked"]
    assert not by["speaking"]["unlocked"]            # needs 3


def test_partial_level_does_not_count_as_completed(client, db):
    hdr, uid = _signup(client, "partial@example.com")
    _, items = _level_with_items(db, 1, n=3)
    _bring_to_familiar(db, uid, items[:2])           # only 2 of 3 at Familiar
    body = client.get("/api/v1/features", headers=hdr).json()
    assert body["completed_levels"] == 0             # not fully complete → doesn't count


def test_require_feature_gate(client, db):
    from app.services.features import require_feature
    from fastapi import HTTPException
    hdr, uid = _signup(client, "gate@example.com")
    _, items = _level_with_items(db, 1)
    _bring_to_familiar(db, uid, items)               # 1 completed level

    require_feature(db, user_id=uid, feature="reading")   # unlocked → no raise
    with pytest.raises(HTTPException) as ex:
        require_feature(db, user_id=uid, feature="speaking")  # needs 3
    assert ex.value.detail["error"]["code"] == "feature_locked"
    assert ex.value.detail["error"]["unlock_level"] == 3

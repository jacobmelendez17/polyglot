"""Selectable-items endpoint: auth, not-started filtering, grouping by level."""
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
from app.models.progress import UserItemProgress


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="cust@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "C", "password": "Supersecret1!"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def _level(db, position):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m = Module(language_id=lang.id, position=position, title=f"L{position}",
               status=ContentStatus.published)
    db.add(m); db.flush()
    return lang, m


def _vocab(db, lang, m, term):
    v = VocabularyItem(language_id=lang.id, module_id=m.id, term=term,
                       normalized_term=term, primary_translation=term + "-en",
                       part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1)
    db.add(v); db.flush()
    return v


def test_selectable_requires_auth(client):
    assert client.get("/api/v1/lessons/selectable").status_code == 401


def test_selectable_lists_unstarted_items_by_level(client, db):
    hdr, uid = _signup(client)
    lang, m1 = _level(db, 1)
    a = _vocab(db, lang, m1, "gato")
    b = _vocab(db, lang, m1, "perro")
    # mark one as started -> excluded
    db.add(UserItemProgress(user_id=uid, item_type=ItemType.vocabulary, item_id=a.id, srs_stage=1))
    db.commit()

    body = client.get("/api/v1/lessons/selectable", headers=hdr).json()
    lvl1 = [l for l in body["levels"] if l["level"] == 1]
    assert lvl1, body
    terms = {i["term"] for i in lvl1[0]["items"]}
    assert "perro" in terms and "gato" not in terms

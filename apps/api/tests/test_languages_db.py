"""Active language end-to-end: selection, fallback, and that /levels follows it."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.seed_tagalog import seed_tagalog
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.services import languages as svc


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="lang@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "L", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def _publish_spanish_level(db):
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    m = Module(language_id=lang.id, position=1, title="Nivel 1", status=ContentStatus.published)
    db.add(m); db.flush()
    db.add(VocabularyItem(language_id=lang.id, module_id=m.id, term="hola",
                          normalized_term="hola", primary_translation="hello",
                          part_of_speech="interjection", status=ContentStatus.published,
                          difficulty_rank=1))
    db.commit()


# --- service ---------------------------------------------------------------

def test_get_active_defaults_to_spanish(client, db):
    _, uid = _signup(client)
    lang = svc.get_active(db, user_id=uid)
    assert lang is not None and lang.code == "es-MX"


def test_set_active_requires_enabled_language(client, db):
    _, uid = _signup(client)
    seed_tagalog(db, with_content=False)
    svc.set_active(db, user_id=uid, code="tl-PH")
    assert svc.get_active(db, user_id=uid).code == "tl-PH"
    with pytest.raises(svc.LanguageError):
        svc.set_active(db, user_id=uid, code="zz-ZZ")  # unknown → rejected


def test_disabled_language_falls_back(client, db):
    _, uid = _signup(client)
    # point the profile at a disabled language; get_active must not blow up
    tl = seed_tagalog(db, with_content=False)  # noqa: F841
    lang = db.execute(select(Language).where(Language.code == "tl-PH")).scalar_one()
    from app.models.identity import Profile
    db.get(Profile, uid).active_language_code = "tl-PH"
    lang.enabled = False
    db.commit()
    assert svc.get_active(db, user_id=uid).code == "es-MX"  # falls back to default


# --- API -------------------------------------------------------------------

def test_language_routes_require_auth(client):
    assert client.get("/api/v1/languages").status_code == 401
    assert client.get("/api/v1/me/language").status_code == 401


def test_list_and_switch_language_via_api(client, db):
    seed_tagalog(db, with_content=False)
    hdr, _ = _signup(client)
    langs = {l["code"] for l in client.get("/api/v1/languages", headers=hdr).json()}
    assert {"es-MX", "tl-PH"} <= langs

    assert client.get("/api/v1/me/language", headers=hdr).json()["code"] == "es-MX"
    put = client.put("/api/v1/me/language", headers=hdr, json={"code": "tl-PH"})
    assert put.status_code == 200 and put.json()["code"] == "tl-PH"
    assert client.get("/api/v1/me/language", headers=hdr).json()["code"] == "tl-PH"

    # unknown language rejected
    assert client.put("/api/v1/me/language", headers=hdr, json={"code": "zz"}).status_code == 422


# --- the point of the slice: /levels follows the active language -----------

def test_levels_reflect_the_active_language(client, db):
    _publish_spanish_level(db)
    seed_tagalog(db)  # demo Tagalog Level 1 with content
    hdr, _ = _signup(client)

    # default (Spanish)
    es_levels = client.get("/api/v1/levels", headers=hdr).json()
    assert any(l["title"] == "Nivel 1" for l in es_levels)
    assert all(l["title"] != "Level 1" for l in es_levels)  # not showing Tagalog's

    # switch to Tagalog → levels change
    client.put("/api/v1/me/language", headers=hdr, json={"code": "tl-PH"})
    tl_levels = client.get("/api/v1/levels", headers=hdr).json()
    assert any(l["title"] == "Level 1" for l in tl_levels)
    assert tl_levels[0]["vocab_count"] >= 5  # the demo words
    assert all(l["title"] != "Nivel 1" for l in tl_levels)  # Spanish no longer shown

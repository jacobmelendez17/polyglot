"""Integration tests for per-item user notes (slice 44)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def world(client, db):
    seed(db)
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=lang.id, position=1, title="L1", status=ContentStatus.published)
    db.add(module); db.flush()
    v = VocabularyItem(
        language_id=lang.id, module_id=module.id, status=ContentStatus.published,
        term="casa", normalized_term="casa", primary_translation="house",
        part_of_speech="noun", difficulty_rank=1,
    )
    db.add(v); db.flush()
    r = client.post("/api/v1/auth/signup",
                    json={"email": "noter@example.com", "name": "N", "password": "supersecret1"})
    db.commit()
    return {"hdr": {"Authorization": f"Bearer {r.json()['access_token']}"}, "vid": str(v.id)}


def test_note_starts_empty_then_saves_and_reloads(client, db, world):
    hdr, vid = world["hdr"], world["vid"]
    got = client.get(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr).json()
    assert got["body"] == ""

    put = client.put(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr,
                     json={"body": "casa = house, feminine"})
    assert put.status_code == 200 and put.json()["body"] == "casa = house, feminine"

    again = client.get(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr).json()
    assert again["body"] == "casa = house, feminine"


def test_note_can_be_cleared(client, db, world):
    hdr, vid = world["hdr"], world["vid"]
    client.put(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr, json={"body": "something"})
    client.put(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr, json={"body": ""})
    assert client.get(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr).json()["body"] == ""


def test_note_rejects_over_250_words(client, db, world):
    hdr, vid = world["hdr"], world["vid"]
    r = client.put(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr,
                   json={"body": " ".join(["w"] * 251)})
    assert r.status_code == 422


def test_note_requires_auth(client, db, world):
    assert client.get(f"/api/v1/items/vocabulary/{world['vid']}/note").status_code in (401, 403)


def test_note_is_per_user(client, db, world):
    hdr, vid = world["hdr"], world["vid"]
    client.put(f"/api/v1/items/vocabulary/{vid}/note", headers=hdr, json={"body": "mine"})
    other = client.post("/api/v1/auth/signup",
                        json={"email": "other@example.com", "name": "O", "password": "supersecret1"}).json()
    got = client.get(f"/api/v1/items/vocabulary/{vid}/note",
                     headers={"Authorization": f"Bearer {other['access_token']}"}).json()
    assert got["body"] == ""

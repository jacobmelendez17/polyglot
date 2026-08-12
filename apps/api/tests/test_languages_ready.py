"""Integration test for language readiness (slice 41).

`GET /api/v1/languages` reports `ready=false` for an enabled language that has no
published content (e.g. Tagalog before its curriculum lands), and `ready=true`
once it has a published item.
"""
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


def _token(client):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "reader@example.com", "name": "R", "password": "supersecret1"})
    return r.json()["access_token"]


def test_ready_reflects_published_content(client, db):
    seed(db)  # seeds es-MX + tl languages (both enabled, no content)
    tok = _token(client)
    hdr = {"Authorization": f"Bearer {tok}"}

    langs = {l["code"]: l for l in client.get("/api/v1/languages", headers=hdr).json()}
    # With no published content yet, enabled languages are not "ready".
    assert langs  # at least one enabled language
    assert all(l["ready"] is False for l in langs.values())

    # Publish one vocab item under es-MX → it becomes ready; others stay not-ready.
    es = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()
    module = Module(language_id=es.id, position=1, title="Level 1", status=ContentStatus.published)
    db.add(module)
    db.flush()
    db.add(VocabularyItem(
        language_id=es.id, module_id=module.id, status=ContentStatus.published,
        term="gato", normalized_term="gato", primary_translation="cat",
        part_of_speech="noun", difficulty_rank=1,
    ))
    db.commit()

    langs2 = {l["code"]: l for l in client.get("/api/v1/languages", headers=hdr).json()}
    assert langs2["es-MX"]["ready"] is True
    if "tl" in langs2:
        assert langs2["tl"]["ready"] is False

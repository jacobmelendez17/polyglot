"""The admin CSV importer targets any language (§1, R-63).

Proves the multilingual schema in practice: the same importer that loads Spanish
loads Tagalog when told to, keeps the two curricula separate, and rejects an unknown
language — while defaulting to es-MX for backward compatibility.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.seed import seed
from app.db.seed_tagalog import seed_tagalog
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, VocabularyItem
from app.models.enums import UserRole
from app.models.identity import User

_VOCAB_CSV = "Word,Translation,Level,Batch\n" \
    "kumusta,hello,1,1\n" \
    "salamat,thank you,1,1\n" \
    "tubig,water,1,1\n"


@pytest.fixture()
def client(db):
    seed(db)
    seed_tagalog(db, with_content=False)  # register Tagalog, no demo content
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _editor(client, db, email="ed@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "Ed", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    db.get(User, __import__("uuid").UUID(me["id"])).role = UserRole.content_editor
    db.commit()
    return {"Authorization": f"Bearer {tok}"}


def _lang_id(db, code):
    return db.execute(select(Language.id).where(Language.code == code)).scalar_one()


def test_import_targets_the_requested_language(client, db):
    hdr = _editor(client)
    r = client.post("/api/v1/admin/imports/vocabulary?language=tl-PH", headers=hdr,
                    files={"file": ("tl.csv", _VOCAB_CSV, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 3

    tl = _lang_id(db, "tl-PH")
    es = _lang_id(db, "es-MX")
    tl_count = db.execute(select(func.count()).select_from(VocabularyItem)
                          .where(VocabularyItem.language_id == tl)).scalar_one()
    es_count = db.execute(select(func.count()).select_from(VocabularyItem)
                          .where(VocabularyItem.language_id == es)).scalar_one()
    assert tl_count == 3          # created under Tagalog
    assert es_count == 0          # nothing leaked into Spanish

    terms = db.execute(select(VocabularyItem.term)
                       .where(VocabularyItem.language_id == tl)).scalars().all()
    assert "kumusta" in terms


def test_import_defaults_to_spanish(client, db):
    hdr = _editor(client, "ed2@example.com")
    r = client.post("/api/v1/admin/imports/vocabulary", headers=hdr,
                    files={"file": ("es.csv", "Word,Translation,Level,Batch\nhola,hello,1,1\n",
                                    "text/csv")})
    assert r.status_code == 200
    es = _lang_id(db, "es-MX")
    assert db.execute(select(func.count()).select_from(VocabularyItem)
                      .where(VocabularyItem.language_id == es)).scalar_one() == 1


def test_unknown_language_is_rejected(client, db):
    hdr = _editor(client, "ed3@example.com")
    r = client.post("/api/v1/admin/imports/vocabulary?language=zz-ZZ", headers=hdr,
                    files={"file": ("x.csv", _VOCAB_CSV, "text/csv")})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "unknown_language"


def test_import_still_requires_capability(client, db):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "plain@example.com", "name": "P", "password": "supersecret1"})
    tok = r.json()["access_token"]
    resp = client.post("/api/v1/admin/imports/vocabulary?language=tl-PH",
                       headers={"Authorization": f"Bearer {tok}"},
                       files={"file": ("x.csv", _VOCAB_CSV, "text/csv")})
    assert resp.status_code == 403

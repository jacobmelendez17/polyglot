"""Reading resource end-to-end: library, reader gate, lookup, annotations, admin."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import Language, Module, VocabularyItem
from app.models.enums import UserRole
from app.models.identity import User
from app.models.platform import AdminAuditLog
from app.models.reading import ReadingText


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email, role=UserRole.user, db=None):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": email.split("@")[0], "password": "supersecret1"})
    tok = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {tok}"}
    if role != UserRole.user and db is not None:
        me = client.get("/api/v1/auth/me", headers=hdr).json()
        u = db.get(User, uuid.UUID(me["id"])); u.role = role; db.commit()
    return hdr


def _lang(db):
    return db.execute(select(Language).where(Language.code == "es-MX")).scalar_one()


def _text(db, *, status="published", source_type="original",
          body="El gato mira la luna.", title="cuento"):
    t = ReadingText(language_id=_lang(db).id, title=title, source_type=source_type,
                    body=body, external_url="", status=status, level=1)
    db.add(t); db.commit()
    return t


def test_reading_requires_auth(client):
    assert client.get("/api/v1/reading").status_code == 401


def test_library_lists_only_published(client, db):
    _text(db, status="published", title="visible")
    _text(db, status="draft", title="hidden-draft")
    hdr = _signup(client, "reader@example.com")
    lib = client.get("/api/v1/reading", headers=hdr).json()
    titles = {t["title"] for t in lib}
    assert "visible" in titles and "hidden-draft" not in titles


def test_draft_is_404_for_users_but_readable_by_editor(client, db):
    t = _text(db, status="draft", title="wip")
    user = _signup(client, "u@example.com")
    assert client.get(f"/api/v1/reading/{t.id}", headers=user).status_code == 404
    editor = _signup(client, "ed@example.com", UserRole.content_editor, db)
    assert client.get(f"/api/v1/reading/{t.id}", headers=editor).status_code == 200


def test_word_lookup_reuses_vocabulary(client, db):
    lang = _lang(db)
    m = Module(language_id=lang.id, position=1, title="L1", status=ContentStatus.published)
    db.add(m); db.flush()
    db.add(VocabularyItem(language_id=lang.id, module_id=m.id, term="gato",
                          normalized_term="gato", primary_translation="cat",
                          part_of_speech="noun", status=ContentStatus.published, difficulty_rank=1))
    db.commit()
    hdr = _signup(client, "look@example.com")
    # accented / punctuated input still matches the normalized term
    hit = client.get("/api/v1/reading/lookup?word=Gato.", headers=hdr).json()
    assert hit["found"] is True and hit["translation"] == "cat"
    miss = client.get("/api/v1/reading/lookup?word=zzzz", headers=hdr).json()
    assert miss["found"] is False


def test_annotation_lifecycle_and_server_side_quote(client, db):
    t = _text(db, body="El gato mira la luna.")  # 'gato' at 3..7
    hdr = _signup(client, "note@example.com")
    r = client.post(f"/api/v1/reading/{t.id}/annotations", headers=hdr,
                    json={"start": 3, "end": 7, "note": "the cat"})
    assert r.status_code == 200
    ann = r.json()
    assert ann["quote"] == "gato"  # sliced from the server body, not the client
    # appears in the list
    lst = client.get(f"/api/v1/reading/{t.id}/annotations", headers=hdr).json()
    assert len(lst) == 1
    # delete
    assert client.delete(f"/api/v1/reading/annotations/{ann['id']}", headers=hdr).status_code == 200
    assert client.get(f"/api/v1/reading/{t.id}/annotations", headers=hdr).json() == []


def test_out_of_range_annotation_is_rejected(client, db):
    t = _text(db, body="corto")  # len 5
    hdr = _signup(client, "bad@example.com")
    r = client.post(f"/api/v1/reading/{t.id}/annotations", headers=hdr,
                    json={"start": 0, "end": 99, "note": "x"})
    assert r.status_code == 422


def test_cannot_see_another_users_annotations(client, db):
    t = _text(db)
    ha = _signup(client, "a@example.com")
    hb = _signup(client, "b@example.com")
    client.post(f"/api/v1/reading/{t.id}/annotations", headers=ha,
                json={"start": 0, "end": 2, "note": "mine"})
    # B sees none of A's annotations
    assert client.get(f"/api/v1/reading/{t.id}/annotations", headers=hb).json() == []


def test_external_links_cannot_be_annotated(client, db):
    t = _text(db, source_type="external", body="", title="ext")
    t.external_url = "https://example.com"; db.commit()
    hdr = _signup(client, "ext@example.com")
    r = client.post(f"/api/v1/reading/{t.id}/annotations", headers=hdr,
                    json={"start": 0, "end": 1, "note": "x"})
    assert r.status_code == 400


def test_admin_create_and_publish_is_gated_and_audited(client, db):
    user = _signup(client, "plain@example.com")
    editor = _signup(client, "editor2@example.com", UserRole.content_editor, db)

    # a normal user can't author
    assert client.post("/api/v1/admin/reading", headers=user,
                       json={"title": "x", "source_type": "original", "body": "hola"}).status_code == 403

    created = client.post("/api/v1/admin/reading", headers=editor,
                          json={"title": "nuevo", "source_type": "original",
                                "body": "Un texto nuevo.", "level": 1}).json()
    tid = created["id"]
    assert created["status"] == "draft"
    # not visible to readers until published
    assert client.get(f"/api/v1/reading/{tid}", headers=user).status_code == 404
    # publish (content_publish — editor has it)
    client.patch(f"/api/v1/admin/reading/{tid}/status", headers=editor, json={"status": "published"})
    assert client.get(f"/api/v1/reading/{tid}", headers=user).status_code == 200

    # both mutations were audited
    logs = db.execute(
        select(func.count()).select_from(AdminAuditLog)
        .where(AdminAuditLog.target_table == "reading_texts")
    ).scalar_one()
    assert logs >= 2

"""Integration tests for the in-app curriculum editor (slice 39).

Runs against a real database (the project's testcontainers Postgres fixture).
Covers create/edit/move/soft-delete/restore for vocabulary and grammar, the
batch column, capability gating, and audit-log writes.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.base import ContentStatus
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import GrammarPoint, Module, VocabularyItem
from app.models.enums import UserRole
from app.models.platform import AdminAuditLog


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _token(client, db, email, role):
    """Sign up a user and elevate their role (mirrors other admin tests)."""
    from app.models.identity import User

    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "Ed", "password": "supersecret1"})
    tok = r.json()["access_token"]
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.role = role
    db.commit()
    return tok


@pytest.fixture()
def editor(client, db):
    seed(db)
    return _token(client, db, "editor@example.com", UserRole.content_editor)


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_create_edit_move_delete_restore_vocab(client, db, editor):
    hdr = _hdr(editor)

    # create at level 1 / batch 1
    r = client.post("/api/v1/admin/content/vocabulary", headers=hdr,
                    json={"term": "gato", "translation": "cat", "level": 1, "batch": 1,
                          "part_of_speech": "noun", "article": "el", "gender": "masculine"})
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["batch"] == 1 and item["level"] == 1 and item["article"] == "el"
    vid = item["id"]

    # edit translation
    r = client.patch(f"/api/v1/admin/content/vocabulary/{vid}", headers=hdr,
                     json={"translation": "the cat"})
    assert r.status_code == 200
    assert r.json()["translation"] == "the cat"

    # move to level 3 / batch 2 (creates the module if needed)
    r = client.post(f"/api/v1/admin/content/vocabulary/{vid}/move", headers=hdr,
                    json={"level": 3, "batch": 2})
    assert r.status_code == 200
    assert r.json()["level"] == 3 and r.json()["batch"] == 2

    # soft delete -> archived + deleted_at set
    r = client.request("DELETE", f"/api/v1/admin/content/vocabulary/{vid}", headers=hdr)
    assert r.status_code == 200 and r.json()["archived"] is True
    row = db.get(VocabularyItem, __import__("uuid").UUID(vid))
    assert row.deleted_at is not None and row.status == ContentStatus.archived

    # it no longer appears in the default editor list, but does with include_archived
    lst = client.get("/api/v1/admin/content/vocabulary/editor", headers=hdr).json()
    assert vid not in [i["id"] for i in lst["items"]]
    lst2 = client.get("/api/v1/admin/content/vocabulary/editor?include_archived=true", headers=hdr).json()
    assert vid in [i["id"] for i in lst2["items"]]

    # restore
    r = client.post(f"/api/v1/admin/content/vocabulary/{vid}/restore", headers=hdr)
    assert r.status_code == 200 and r.json()["archived"] is False


def test_article_forced_off_for_non_nouns(client, db, editor):
    hdr = _hdr(editor)
    r = client.post("/api/v1/admin/content/vocabulary", headers=hdr,
                    json={"term": "correr", "translation": "to run", "level": 1,
                          "part_of_speech": "verb", "article": "el"})
    assert r.status_code == 201
    # verb cannot carry an article (respects the DB CHECK + §6 rule)
    assert r.json()["article"] == "none"


def test_create_move_grammar(client, db, editor):
    hdr = _hdr(editor)
    r = client.post("/api/v1/admin/content/grammar", headers=hdr,
                    json={"term": "ser vs estar", "translation": "to be", "level": 2})
    assert r.status_code == 201
    gid = r.json()["id"]
    assert r.json()["level"] == 2
    r = client.post(f"/api/v1/admin/content/grammar/{gid}/move", headers=hdr, json={"level": 5})
    assert r.status_code == 200 and r.json()["level"] == 5


def test_bad_level_and_batch_rejected(client, db, editor):
    hdr = _hdr(editor)
    r = client.post("/api/v1/admin/content/vocabulary", headers=hdr,
                    json={"term": "x", "translation": "y", "level": 0, "batch": 1})
    assert r.status_code == 422
    r = client.post("/api/v1/admin/content/vocabulary", headers=hdr,
                    json={"term": "x", "translation": "y", "level": 1, "batch": 9})
    assert r.status_code == 422


def test_editor_requires_capability(client, db):
    tok = _token(client, db, "plainuser@example.com", UserRole.user)
    r = client.post("/api/v1/admin/content/vocabulary", headers=_hdr(tok),
                    json={"term": "gato", "translation": "cat", "level": 1})
    assert r.status_code in (401, 403)
    # moderator has admin_panel but NOT content_edit
    seed(db)
    mtok = _token(client, db, "mod@example.com", UserRole.moderator)
    r = client.get("/api/v1/admin/content/vocabulary/editor", headers=_hdr(mtok))
    assert r.status_code == 403


def test_mutations_write_audit_log(client, db, editor):
    hdr = _hdr(editor)
    client.post("/api/v1/admin/content/grammar", headers=hdr,
                json={"term": "gustar", "translation": "to like", "level": 1})
    n = db.execute(
        select(func.count()).select_from(AdminAuditLog)
        .where(AdminAuditLog.action == "create", AdminAuditLog.target_table == "grammar_points")
    ).scalar_one()
    assert n >= 1

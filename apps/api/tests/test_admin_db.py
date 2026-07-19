"""Admin endpoint tests: import, content listing/publishing, user management,
and authorization gates. Uses real Postgres + FastAPI TestClient."""
import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth import service
from app.core.config import get_settings
from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.curriculum import VocabularyItem
from app.models.enums import UserRole
from app.models.platform import AdminAuditLog


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _token(client, db, email, role):
    settings = get_settings()
    service.create_account(db, email=email, password="supersecret1",
                           display_name="Admin", settings=settings, role=role)
    db.commit()
    return client.post("/api/v1/auth/login",
                       json={"email": email, "password": "supersecret1"}).json()["access_token"]


@pytest.fixture()
def real_csvs():
    base = pathlib.Path("/mnt/user-data/uploads")
    v = base / "Spanish_Stuff_-_Everything__1_.csv"
    g = base / "Spanish_Stuff_-_Grammar__1_.csv"
    if not v.exists():
        pytest.skip("real CSVs not present")
    return {"vocab": v.read_text(), "grammar": g.read_text()}


def test_import_requires_capability(client, db):
    seed(db)
    tok = _token(client, db, "user@example.com", UserRole.user)
    r = client.post("/api/v1/admin/imports/vocabulary",
                    headers={"Authorization": f"Bearer {tok}"},
                    files={"file": ("v.csv", "Word,Translation,Level,Batch\n", "text/csv")})
    assert r.status_code == 403


def test_import_vocab_as_content_editor(client, db, real_csvs):
    seed(db)
    tok = _token(client, db, "ed@example.com", UserRole.content_editor)
    r = client.post("/api/v1/admin/imports/vocabulary",
                    headers={"Authorization": f"Bearer {tok}"},
                    files={"file": ("everything.csv", real_csvs["vocab"], "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 465
    assert body["report"]["error_count"] == 1  # nosotros
    # items land as draft
    drafts = db.execute(
        select(func.count()).select_from(VocabularyItem)
        .where(VocabularyItem.status == __import__("app.db.base", fromlist=["ContentStatus"]).ContentStatus.draft)
    ).scalar_one()
    assert drafts == 465


def test_import_writes_audit_log(client, db, real_csvs):
    seed(db)
    tok = _token(client, db, "ed2@example.com", UserRole.content_editor)
    client.post("/api/v1/admin/imports/grammar",
                headers={"Authorization": f"Bearer {tok}"},
                files={"file": ("g.csv", real_csvs["grammar"], "text/csv")})
    logs = db.execute(select(func.count()).select_from(AdminAuditLog)
                      .where(AdminAuditLog.action == "import_grammar")).scalar_one()
    assert logs == 1


def test_list_and_publish_content(client, db, real_csvs):
    seed(db)
    tok = _token(client, db, "ed3@example.com", UserRole.content_editor)
    hdr = {"Authorization": f"Bearer {tok}"}
    client.post("/api/v1/admin/imports/vocabulary", headers=hdr,
                files={"file": ("v.csv", real_csvs["vocab"], "text/csv")})
    lst = client.get("/api/v1/admin/content/vocabulary?level=1&limit=5", headers=hdr).json()
    assert lst["total"] >= 40
    item_id = lst["items"][0]["id"]
    assert lst["items"][0]["status"] == "draft"
    pub = client.patch(f"/api/v1/admin/content/vocabulary/{item_id}/status",
                       headers=hdr, json={"status": "published"})
    assert pub.status_code == 200
    assert pub.json()["status"] == "published"


def test_user_management_gated(client, db):
    seed(db)
    ed = _token(client, db, "editor@example.com", UserRole.content_editor)
    # content_editor cannot manage users
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {ed}"}).status_code == 403
    admin = _token(client, db, "admin@example.com", UserRole.admin)
    assert client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {admin}"}).status_code == 200


def test_only_owner_manages_owner_role(client, db):
    seed(db)
    admin = _token(client, db, "admin2@example.com", UserRole.admin)
    # make a target user
    settings = get_settings()
    target = service.create_account(db, email="target@example.com", password="supersecret1",
                                    display_name="T", settings=settings, role=UserRole.user)
    db.commit()
    # admin cannot promote to owner
    r = client.patch(f"/api/v1/admin/users/{target.id}/role",
                     headers={"Authorization": f"Bearer {admin}"}, json={"role": "owner"})
    assert r.status_code == 403
    # admin can promote to moderator
    r2 = client.patch(f"/api/v1/admin/users/{target.id}/role",
                      headers={"Authorization": f"Bearer {admin}"}, json={"role": "moderator"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "moderator"


def test_signup_captures_name(client, db):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "named@example.com", "name": "Jacob", "password": "supersecret1"})
    assert r.status_code == 201
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["name"] == "Jacob"

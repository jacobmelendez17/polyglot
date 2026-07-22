"""End-to-end auth: signup, login, refresh rotation, reuse detection, logout,
and capability-gated access. Uses a real Postgres via the db fixture and the
FastAPI TestClient with a DB dependency override."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import service
from app.auth.capabilities import Capability
from app.auth.deps import require
from app.core.config import get_settings
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import User


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    # a protected probe route to test capability enforcement
    from fastapi import Depends

    @app.get("/api/v1/_probe/content")
    def _probe(user: User = Depends(require(Capability.content_edit))):
        return {"ok": True, "user": str(user.id)}

    return TestClient(app)


def test_signup_returns_tokens_and_creates_user(client, db):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "a@example.com", "name": "Test User", "password": "supersecret1"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    user = db.execute(select(User).where(User.email == "a@example.com")).scalar_one()
    assert user.password_hash and user.password_hash != "supersecret1"  # hashed


def test_duplicate_signup_rejected(client):
    client.post("/api/v1/auth/signup", json={"email": "d@example.com", "name": "Test User", "password": "supersecret1"})
    r = client.post("/api/v1/auth/signup", json={"email": "d@example.com", "name": "Test User", "password": "supersecret1"})  # noqa: E501
    assert r.status_code == 400


def test_login_wrong_password_is_401_and_uniform(client):
    client.post("/api/v1/auth/signup", json={"email": "e@example.com", "name": "Test User", "password": "supersecret1"})
    r = client.post("/api/v1/auth/login", json={"email": "e@example.com", "name": "Test User", "password": "WRONG"})
    assert r.status_code == 401
    # message must not reveal whether the email exists
    assert "email or password" in r.json()["detail"]["error"]["message"].lower()


def test_login_unknown_email_is_401(client):
    r = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "name": "Test User", "password": "whatever12"})  # noqa: E501
    assert r.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_identity_and_capabilities(client):
    tok = client.post("/api/v1/auth/signup",
                      json={"email": "m@example.com", "name": "Test User", "password": "supersecret1"}).json()["access_token"]  # noqa: E501
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "m@example.com"
    assert body["role"] == "user"
    assert body["capabilities"] == []  # regular user


def test_refresh_rotates_and_old_token_is_dead(client, db):
    signup = client.post("/api/v1/auth/signup",
                         json={"email": "r@example.com", "name": "Test User", "password": "supersecret1"}).json()
    old_refresh = signup["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert r.status_code == 200
    new_refresh = r.json()["refresh_token"]
    assert new_refresh != old_refresh
    # reusing the old (now rotated) refresh token must fail...
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


def test_reuse_detection_revokes_chain(client, db):
    signup = client.post("/api/v1/auth/signup",
                         json={"email": "chain@example.com", "name": "Test User", "password": "supersecret1"}).json()
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": signup["refresh_token"]}).json()
    # r1 is now the live token; reuse the original again -> triggers chain revocation
    client.post("/api/v1/auth/refresh", json={"refresh_token": signup["refresh_token"]})
    # the previously-live r1 token should now also be revoked
    after = client.post("/api/v1/auth/refresh", json={"refresh_token": r1["refresh_token"]})
    assert after.status_code == 401


def test_logout_kills_session_access(client, db):
    signup = client.post("/api/v1/auth/signup",
                         json={"email": "o@example.com", "name": "Test User", "password": "supersecret1"}).json()
    access, refresh = signup["access_token"], signup["refresh_token"]
    # /me works before logout
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code == 200  # noqa: E501
    client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    # after logout the access token is rejected because its session is revoked
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}).status_code == 401  # noqa: E501


def test_capability_gate_forbids_regular_user(client):
    tok = client.post("/api/v1/auth/signup",
                      json={"email": "p@example.com", "name": "Test User", "password": "supersecret1"}).json()["access_token"]  # noqa: E501
    r = client.get("/api/v1/_probe/content", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_capability_gate_allows_content_editor(client, db):
    # promote a user to content_editor and re-login to get a token with the role
    settings = get_settings()
    service.create_account(db, email="ed@example.com", password="supersecret1",
                           settings=settings, role=UserRole.content_editor)
    db.commit()
    tok = client.post("/api/v1/auth/login",
                      json={"email": "ed@example.com", "name": "Test User", "password": "supersecret1"}).json()["access_token"]  # noqa: E501
    r = client.get("/api/v1/_probe/content", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["ok"] is True

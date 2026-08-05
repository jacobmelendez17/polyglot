"""Settings + profile endpoints end-to-end."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.identity import Profile


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="acct@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "Ana", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def test_account_routes_require_auth(client):
    assert client.get("/api/v1/me/settings").status_code == 401
    assert client.get("/api/v1/me/profile").status_code == 401


def test_settings_default_and_update(client):
    hdr, _ = _signup(client)
    s = client.get("/api/v1/me/settings", headers=hdr).json()
    assert s["theme"] == "system" and s["lesson_batch_size"] == 5
    assert s["review_batch_size"] == 20 and s["immersion_unlocked"] is False

    r = client.patch("/api/v1/me/settings", headers=hdr,
                     json={"theme": "dark", "lesson_batch_size": 8, "allow_cheating": True})
    assert r.status_code == 200
    body = r.json()
    assert body["theme"] == "dark" and body["lesson_batch_size"] == 8 and body["allow_cheating"]
    # persisted
    assert client.get("/api/v1/me/settings", headers=hdr).json()["theme"] == "dark"


def test_invalid_settings_return_field_errors(client):
    hdr, _ = _signup(client, "bad@example.com")
    r = client.patch("/api/v1/me/settings", headers=hdr,
                     json={"theme": "neon", "lesson_batch_size": 0})
    assert r.status_code == 422
    errs = r.json()["detail"]["error"]["field_errors"]
    assert "theme" in errs and "lesson_batch_size" in errs


def test_immersion_toggle_gated_until_unlocked(client, db):
    hdr, uid = _signup(client, "imm@example.com")
    # locked → rejected
    r = client.patch("/api/v1/me/settings", headers=hdr, json={"immersion_mode": True})
    assert r.status_code == 422
    assert "immersion_mode" in r.json()["detail"]["error"]["field_errors"]

    # unlock it, then it's accepted
    import datetime as dt
    db.get(Profile, uid).immersion_unlocked_at = dt.datetime.now(tz=dt.timezone.utc)
    db.commit()
    assert client.get("/api/v1/me/settings", headers=hdr).json()["immersion_unlocked"] is True
    ok = client.patch("/api/v1/me/settings", headers=hdr, json={"immersion_mode": True})
    assert ok.status_code == 200 and ok.json()["immersion_mode"] is True


def test_profile_get_and_update(client, db):
    hdr, _ = _signup(client, "prof@example.com")
    p = client.get("/api/v1/me/profile", headers=hdr).json()
    assert p["display_name"] == "Ana" and p["xp_total"] == 0

    r = client.patch("/api/v1/me/profile", headers=hdr,
                     json={"display_name": "Anita", "bio": "aprendiendo español"})
    assert r.status_code == 200
    body = r.json()
    assert body["display_name"] == "Anita" and body["bio"] == "aprendiendo español"
    assert client.get("/api/v1/me/profile", headers=hdr).json()["display_name"] == "Anita"


def test_profile_cannot_write_server_controlled_fields(client, db):
    hdr, _ = _signup(client, "xp@example.com")
    # xp_total isn't an accepted field; it's ignored, not written
    client.patch("/api/v1/me/profile", headers=hdr,
                 json={"display_name": "Z", "xp_total": 999999})
    assert client.get("/api/v1/me/profile", headers=hdr).json()["xp_total"] == 0

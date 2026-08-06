"""Password policy + OAuth providers — pure rules, signup enforcement, and the
configured-providers endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.db.seed import seed
from app.db.session import get_db
from app.domain.password import PasswordError, check_password, validate_password
from app.main import create_app


# --- pure policy -----------------------------------------------------------

def test_strong_password_passes():
    assert all(check_password("Supersecret1!").values())
    validate_password("Supersecret1!")  # no raise


@pytest.mark.parametrize("pw,missing", [
    ("supersecret1", ["an uppercase letter", "a special character"]),
    ("Short1!", ["at least 8 characters"]),
    ("alllower1!", ["an uppercase letter"]),
    ("NoNumber!", ["a number"]),
    ("NoSpecial1", ["a special character"]),
    ("With Space1A", ["a special character"]),  # space is not special
])
def test_weak_passwords_report_what_is_missing(pw, missing):
    with pytest.raises(PasswordError) as ex:
        validate_password(pw)
    assert ex.value.failed == missing


# --- signup enforcement ----------------------------------------------------

@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_signup_rejects_weak_password(client):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "weak@example.com", "name": "W", "password": "supersecret1"})
    assert r.status_code == 422
    assert r.json()["detail"]["error"]["code"] == "weak_password"


def test_signup_accepts_strong_password(client):
    r = client.post("/api/v1/auth/signup",
                    json={"email": "strong@example.com", "name": "S", "password": "Supersecret1!"})
    assert r.status_code == 201, r.text
    assert r.json()["access_token"]


# --- oauth providers -------------------------------------------------------

def test_oauth_providers_all_false_by_default(client, monkeypatch):
    for p in ("GOOGLE", "DISCORD", "GITHUB"):
        monkeypatch.delenv(f"OAUTH_{p}_CLIENT_ID", raising=False)
        monkeypatch.delenv(f"OAUTH_{p}_CLIENT_SECRET", raising=False)
    body = client.get("/api/v1/auth/oauth/providers").json()
    assert body["providers"] == {"google": False, "discord": False, "github": False}


def test_oauth_provider_configured_when_env_set(client, monkeypatch):
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_ID", "abc")
    monkeypatch.setenv("OAUTH_GITHUB_CLIENT_SECRET", "xyz")
    body = client.get("/api/v1/auth/oauth/providers").json()
    assert body["providers"]["github"] is True


def test_oauth_start_unconfigured_is_503(client, monkeypatch):
    monkeypatch.delenv("OAUTH_GOOGLE_CLIENT_ID", raising=False)
    r = client.get("/api/v1/auth/oauth/google/start")
    assert r.status_code == 503
    assert r.json()["detail"]["error"]["code"] == "oauth_not_configured"


def test_oauth_start_unknown_provider_is_404(client):
    assert client.get("/api/v1/auth/oauth/myspace/start").status_code == 404

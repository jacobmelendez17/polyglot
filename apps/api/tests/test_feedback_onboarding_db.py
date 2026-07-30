"""Feedback inbox, onboarding persistence, and dev reset — DB + API flow."""
import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import Profile, User


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture()
def world(client, db):
    seed(db)
    db.commit()


def _signup(client, email="user@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "User", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _promote(db, email: str, role: UserRole) -> None:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.role = role
    db.commit()


# --- feedback submit ------------------------------------------------------

def test_submit_feedback_requires_auth(client, world):
    r = client.post("/api/v1/feedback", json={"category": "bug", "body": "broken"})
    assert r.status_code == 401


def test_a_user_can_submit_feedback(client, world):
    headers = _signup(client)
    r = client.post("/api/v1/feedback", headers=headers, json={
        "category": "bug", "body": "the button does nothing",
        "route": "/dashboard", "browser": "Firefox",
    })
    assert r.status_code == 201
    assert r.json()["state"] == "unanswered"


def test_feedback_body_is_sanitized(client, db, world):
    headers = _signup(client)
    client.post("/api/v1/feedback", headers=headers, json={
        "category": "other", "body": "<script>x</script>hola",
    })
    from app.models.platform import FeedbackTicket
    ticket = db.execute(select(FeedbackTicket)).scalars().first()
    assert "<script>" not in ticket.body


def test_invalid_category_is_rejected(client, world):
    headers = _signup(client)
    r = client.post("/api/v1/feedback", headers=headers,
                    json={"category": "nonsense", "body": "x"})
    assert r.status_code == 422


# --- admin inbox ----------------------------------------------------------

def test_normal_user_cannot_see_the_inbox(client, world):
    headers = _signup(client)
    assert client.get("/api/v1/admin/feedback", headers=headers).status_code == 403


def test_admin_lists_and_filters_and_responds(client, db, world):
    user = _signup(client, "reporter@example.com")
    client.post("/api/v1/feedback", headers=user,
                json={"category": "bug", "body": "something is off"})

    _signup(client, "mod@example.com")
    _promote(db, "mod@example.com", UserRole.moderator)
    mod = _signup(client, "mod@example.com")

    inbox = client.get("/api/v1/admin/feedback", headers=mod)
    assert inbox.status_code == 200
    body = inbox.json()
    assert body["total"] >= 1
    assert body["counts"]["unanswered"] >= 1
    tid = body["tickets"][0]["id"]

    # filter by unanswered
    filtered = client.get("/api/v1/admin/feedback?state=unanswered", headers=mod)
    assert filtered.json()["total"] >= 1

    # respond → becomes answered
    resp = client.post(f"/api/v1/admin/feedback/{tid}/respond", headers=mod,
                       json={"response": "thanks, fixing it"})
    assert resp.status_code == 200
    assert resp.json()["state"] == "answered"
    assert resp.json()["admin_response"] == "thanks, fixing it"

    # pin
    pin = client.post(f"/api/v1/admin/feedback/{tid}/pin", headers=mod,
                     json={"pinned": True})
    assert pin.json()["pinned"] is True


# --- onboarding persistence ----------------------------------------------

def test_new_signup_has_not_completed_onboarding(client, world):
    headers = _signup(client, "newbie@example.com")
    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["onboarding_completed"] is False


def test_completing_onboarding_persists(client, db, world):
    headers = _signup(client, "learner@example.com")
    r = client.post("/api/v1/me/onboarding/complete", headers=headers)
    assert r.status_code == 200
    assert r.json()["completed"] is True

    me = client.get("/api/v1/auth/me", headers=headers).json()
    assert me["onboarding_completed"] is True


# --- dev reset ------------------------------------------------------------

def test_reset_is_forbidden_to_normal_users(client, world):
    headers = _signup(client)
    assert client.post("/api/v1/dev/reset-progress", headers=headers).status_code == 403


def test_owner_reset_clears_onboarding(client, db, world):
    _signup(client, "owner2@example.com")
    _promote(db, "owner2@example.com", UserRole.owner)
    owner = _signup(client, "owner2@example.com")

    # complete onboarding first
    client.post("/api/v1/me/onboarding/complete", headers=owner)
    assert client.get("/api/v1/auth/me", headers=owner).json()["onboarding_completed"] is True

    # reset → onboarding flag cleared
    r = client.post("/api/v1/dev/reset-progress", headers=owner)
    assert r.status_code == 200
    assert r.json()["detail"]["onboarding_will_show_on_next_sign_in"] is True
    assert client.get("/api/v1/auth/me", headers=owner).json()["onboarding_completed"] is False

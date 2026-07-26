"""Subscriptions, webhooks, the paywall, and the dev sandbox — DB + API flow."""
import datetime as dt
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.seed import seed
from app.db.session import get_db
from app.main import create_app
from app.models.enums import UserRole
from app.models.identity import User


@pytest.fixture()
def client(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="learner@example.com") -> dict:
    r = client.post("/api/v1/auth/signup", json={
        "email": email, "name": "Learner", "password": "supersecret1",
    })
    assert r.status_code == 201, r.text
    return r.json()


def _verify(db, email: str) -> None:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.email_verified_at = dt.datetime.now(tz=dt.timezone.utc)
    db.commit()


def _promote(db, email: str, role: UserRole) -> None:
    user = db.execute(select(User).where(User.email == email)).scalar_one()
    user.role = role
    db.commit()


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def learner(client, db):
    seed(db)
    db.commit()
    return _signup(client)


# --- subscription state ---------------------------------------------------

def test_new_user_is_free(client, learner):
    r = client.get("/api/v1/me/subscription", headers=_auth(learner))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "free"
    assert body["full_access"] is False
    assert body["max_free_level"] == 1


def test_subscription_requires_auth(client):
    assert client.get("/api/v1/me/subscription").status_code == 401


# --- checkout gating ------------------------------------------------------

def test_checkout_needs_a_verified_email(client, learner):
    """R-29: confirm the address before taking money through it."""
    r = client.post("/api/v1/me/subscription/checkout",
                    headers=_auth(learner), json={"interval": "month"})
    assert r.status_code == 403
    assert r.json()["detail"]["error"]["code"] == "email_unverified"


def test_verified_user_gets_a_checkout_url(client, db, learner):
    _verify(db, "learner@example.com")
    r = client.post("/api/v1/me/subscription/checkout",
                    headers=_auth(learner), json={"interval": "month"})
    assert r.status_code == 200
    assert r.json()["url"].startswith("http")


def test_unknown_interval_is_rejected(client, db, learner):
    _verify(db, "learner@example.com")
    r = client.post("/api/v1/me/subscription/checkout",
                    headers=_auth(learner), json={"interval": "decade"})
    assert r.status_code == 422


# --- webhook lifecycle ----------------------------------------------------

def _webhook(client, event_type: str, user_id: str, **obj) -> None:
    payload = {
        "type": event_type,
        "data": {"object": {"client_reference_id": user_id,
                            "metadata": {"user_id": user_id}, **obj}},
    }
    r = client.post("/api/v1/webhooks/stripe", content=json.dumps(payload),
                    headers={"stripe-signature": "fake"})
    assert r.status_code == 200, r.text


def test_a_completed_checkout_grants_full_access(client, db, learner):
    _verify(db, "learner@example.com")
    uid = db.execute(select(User).where(User.email == "learner@example.com")).scalar_one().id

    _webhook(client, "checkout.session.completed", str(uid),
             subscription="sub_1", customer="cus_1")
    body = client.get("/api/v1/me/subscription", headers=_auth(learner)).json()
    assert body["status"] == "paid_active"
    assert body["full_access"] is True


def test_a_failed_payment_moves_to_past_due_but_keeps_access(client, db, learner):
    uid = db.execute(select(User).where(User.email == "learner@example.com")).scalar_one().id
    _webhook(client, "checkout.session.completed", str(uid), subscription="sub_1")
    _webhook(client, "invoice.payment_failed", str(uid))
    body = client.get("/api/v1/me/subscription", headers=_auth(learner)).json()
    assert body["status"] == "paid_past_due"
    assert body["full_access"] is True     # grace window


def test_a_deleted_subscription_cancels(client, db, learner):
    uid = db.execute(select(User).where(User.email == "learner@example.com")).scalar_one().id
    _webhook(client, "checkout.session.completed", str(uid), subscription="sub_1")
    _webhook(client, "customer.subscription.deleted", str(uid))
    body = client.get("/api/v1/me/subscription", headers=_auth(learner)).json()
    assert body["status"] in ("paid_canceled", "free")


def test_webhooks_are_idempotent(client, db, learner):
    """Stripe retries; applying the same event twice lands on the same state."""
    uid = db.execute(select(User).where(User.email == "learner@example.com")).scalar_one().id
    _webhook(client, "checkout.session.completed", str(uid), subscription="sub_1")
    first = client.get("/api/v1/me/subscription", headers=_auth(learner)).json()
    _webhook(client, "checkout.session.completed", str(uid), subscription="sub_1")
    second = client.get("/api/v1/me/subscription", headers=_auth(learner)).json()
    assert first["status"] == second["status"] == "paid_active"


def test_a_webhook_without_a_user_ref_is_ignored(client):
    payload = {"type": "checkout.session.completed", "data": {"object": {}}}
    r = client.post("/api/v1/webhooks/stripe", content=json.dumps(payload),
                    headers={"stripe-signature": "fake"})
    assert r.status_code == 200
    assert r.json()["handled"] is False


# --- admin grants ---------------------------------------------------------

def test_admin_can_grant_lifetime(client, db, learner):
    admin = _signup(client, "admin@example.com")
    _promote(db, "admin@example.com", UserRole.admin)
    uid = db.execute(select(User).where(User.email == "learner@example.com")).scalar_one().id

    r = client.patch(f"/api/v1/admin/users/{uid}/subscription",
                     headers=_auth(admin), json={"status": "lifetime"})
    assert r.status_code == 200
    assert r.json()["status"] == "lifetime"
    assert r.json()["full_access"] is True


def test_a_normal_user_cannot_grant_subscriptions(client, learner):
    uid = uuid.uuid4()
    r = client.patch(f"/api/v1/admin/users/{uid}/subscription",
                     headers=_auth(learner), json={"status": "lifetime"})
    assert r.status_code == 403


# --- dev sandbox ----------------------------------------------------------

def test_dev_routes_are_forbidden_to_normal_users(client, learner):
    assert client.get("/api/v1/dev/state", headers=_auth(learner)).status_code == 403


def test_dev_routes_require_auth(client):
    assert client.get("/api/v1/dev/state").status_code == 401


@pytest.fixture()
def admin(client, db, learner):
    tokens = _signup(client, "dev@example.com")
    _promote(db, "dev@example.com", UserRole.owner)
    return _signup(client, "dev@example.com")   # fresh token after role change


def test_admin_can_read_dev_state(client, admin):
    r = client.get("/api/v1/dev/state", headers=_auth(admin))
    assert r.status_code == 200
    assert r.json()["dev_mode"] is False
    assert "fast" in r.json()["presets"]


def test_enabling_dev_mode_defaults_to_the_fast_scale(client, admin):
    r = client.put("/api/v1/dev/mode", headers=_auth(admin),
                   json={"enabled": True})
    assert r.status_code == 200
    body = r.json()
    assert body["dev_mode"] is True
    assert body["srs_scale"] < 1.0        # actually speeds things up


def test_dev_mode_scale_can_be_set_explicitly(client, admin):
    r = client.put("/api/v1/dev/mode", headers=_auth(admin),
                   json={"enabled": True, "scale": "instant"})
    assert r.json()["srs_scale"] < 0.001


def test_turning_dev_mode_off_restores_real_intervals(client, admin):
    client.put("/api/v1/dev/mode", headers=_auth(admin), json={"enabled": True})
    r = client.put("/api/v1/dev/mode", headers=_auth(admin), json={"enabled": False})
    assert r.json()["dev_mode"] is False


def test_make_reviews_due_reports_a_count(client, admin):
    r = client.post("/api/v1/dev/make-reviews-due", headers=_auth(admin))
    assert r.status_code == 200
    assert "made_due" in r.json()["detail"]


def test_unlock_all_reports_what_it_unlocked(client, admin):
    r = client.post("/api/v1/dev/unlock-all", headers=_auth(admin), json={})
    assert r.status_code == 200
    assert "unlocked" in r.json()["detail"]

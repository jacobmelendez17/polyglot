"""Billing end-to-end: entitlements, fake checkout, webhook transitions, paywall."""
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
from app.models.platform import Subscription
from app.services.payments import reset_provider


@pytest.fixture(autouse=True)
def _fake_provider(monkeypatch):
    monkeypatch.setenv("PAYMENT_PROVIDER", "fake")
    reset_provider()
    yield
    reset_provider()


@pytest.fixture()
def client(db):
    seed(db)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _signup(client, email="pay@example.com"):
    r = client.post("/api/v1/auth/signup",
                    json={"email": email, "name": "P", "password": "supersecret1"})
    tok = r.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, uuid.UUID(me["id"])


def _set_tier(db, uid, *, tier, status="active"):
    row = db.get(Subscription, uid)
    if row is None:
        row = Subscription(user_id=uid, tier=tier, status=status)
        db.add(row)
    else:
        row.tier, row.status = tier, status
    db.commit()


def test_entitlements_require_auth(client):
    assert client.get("/api/v1/me/entitlements").status_code == 401


def test_new_user_is_entitled_by_beta_default(client):
    hdr, _ = _signup(client)
    ent = client.get("/api/v1/me/entitlements", headers=hdr).json()
    # no Subscription row yet → beta default → entitled
    assert ent["entitled"] is True and ent["free_max_level"] == 1


def test_plain_free_user_is_gated(client, db):
    hdr, uid = _signup(client, "free@example.com")
    _set_tier(db, uid, tier="free", status="active")
    ent = client.get("/api/v1/me/entitlements", headers=hdr).json()
    assert ent["entitled"] is False and ent["tier"] == "free"


def test_plans_are_listed(client):
    hdr, _ = _signup(client, "plans@example.com")
    plans = {p["plan"]: p for p in client.get("/api/v1/billing/plans", headers=hdr).json()}
    assert plans["monthly"]["amount"] == 700 and plans["annual"]["amount"] == 6000


def test_fake_checkout_returns_a_url(client):
    hdr, uid = _signup(client, "checkout@example.com")
    r = client.post("/api/v1/billing/checkout", headers=hdr, json={"plan": "monthly"})
    assert r.status_code == 200
    assert str(uid) in r.json()["url"] and "plan=monthly" in r.json()["url"]
    # bad plan rejected by schema
    assert client.post("/api/v1/billing/checkout", headers=hdr,
                       json={"plan": "weekly"}).status_code == 422


def test_webhook_activates_then_cancels_subscription(client, db):
    hdr, uid = _signup(client, "hook@example.com")
    _set_tier(db, uid, tier="free", status="active")  # start gated

    # subscription created → monthly / active → entitled
    created = {"type": "customer.subscription.created", "user_id": str(uid),
               "customer_id": "cus_123", "tier": "monthly", "status": "active"}
    r = client.post("/api/v1/billing/webhook", content=json.dumps(created))
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert client.get("/api/v1/me/entitlements", headers=hdr).json()["entitled"] is True

    row = db.get(Subscription, uid)
    assert row.tier == "monthly" and row.stripe_customer_id == "cus_123"

    # payment failed → past_due → gated again
    client.post("/api/v1/billing/webhook", content=json.dumps(
        {"type": "invoice.payment_failed", "customer_id": "cus_123"}))
    db.expire_all()
    assert client.get("/api/v1/me/entitlements", headers=hdr).json()["entitled"] is False

    # subscription deleted → canceled
    client.post("/api/v1/billing/webhook", content=json.dumps(
        {"type": "customer.subscription.deleted", "customer_id": "cus_123"}))
    db.expire_all()
    row = db.get(Subscription, uid)
    assert row.status == "canceled" and row.canceled_at is not None


def test_admin_grant_lifetime_is_gated_and_audited(client, db):
    hdr_user, uid = _signup(client, "target@example.com")
    _set_tier(db, uid, tier="free", status="active")
    hdr_admin, admin_id = _signup(client, "boss@example.com")
    db.get(User, admin_id).role = UserRole.owner
    db.commit()

    # a normal user cannot grant
    assert client.post(f"/api/v1/admin/billing/{uid}/grant-lifetime",
                       headers=hdr_user).status_code == 403
    # owner can
    r = client.post(f"/api/v1/admin/billing/{uid}/grant-lifetime", headers=hdr_admin)
    assert r.status_code == 200 and r.json()["tier"] == "lifetime"
    assert client.get("/api/v1/me/entitlements", headers=hdr_user).json()["entitled"] is True

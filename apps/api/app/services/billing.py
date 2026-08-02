"""Billing service (spec §19).

Reads and mutates the `Subscription` row and resolves entitlements through the pure
engine. Complements the existing subscriptions router; all Stripe contact goes
through the provider seam. Key guarantees:

- A learner with no `Subscription` row is treated as the beta default (free_beta /
  active) so nobody who predates billing is locked out.
- Subscription state only ever changes from a verified webhook (or an admin grant) —
  never from a client-supplied claim (§12/§25).
- `require_entitlement_for_level` is the single gate the curriculum calls to enforce
  the paywall.
"""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.entitlements import FREE_MAX_LEVEL, can_access_level, is_entitled
from app.models.identity import User
from app.models.platform import AdminAuditLog, Subscription
from app.services.payments import PLANS, PaymentError, get_provider

# tier a checkout plan maps to
_PLAN_TIER = {"monthly": "monthly", "annual": "annual"}


class BillingError(Exception):
    def __init__(self, message: str, code: str = "billing_error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(v: dt.datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=dt.timezone.utc)
    return v.isoformat()


def _get_or_default(db: Session, user_id: uuid.UUID) -> tuple[str, str, Subscription | None]:
    """Return (tier, status, row-or-None). Missing row → beta default."""
    row = db.get(Subscription, user_id)
    if row is None:
        return "free_beta", "active", None
    return row.tier, row.status, row


def get_entitlements(db: Session, *, user: User) -> dict:
    tier, status, row = _get_or_default(db, user.id)
    entitled = is_entitled(role=user.role.value, tier=tier, status=status)
    return {
        "tier": tier,
        "status": status,
        "entitled": entitled,
        "free_max_level": FREE_MAX_LEVEL,
        "current_period_end": _iso(row.current_period_end) if row else None,
        "canceled_at": _iso(row.canceled_at) if row else None,
    }


def require_entitlement_for_level(db: Session, *, user_id: uuid.UUID, level: int) -> None:
    """Raise 402 when `level` is beyond the free tier and the user isn't entitled.

    Takes a user_id (what the curriculum's unlock check has on hand) and loads the
    role itself.
    """
    user = db.get(User, user_id)
    role = user.role.value if user else "user"
    tier, status, _ = _get_or_default(db, user_id)
    entitled = is_entitled(role=role, tier=tier, status=status)
    if not can_access_level(level, entitled=entitled):
        raise HTTPException(
            status_code=402,
            detail={"error": {"code": "paywall",
                              "message": "This level is part of the paid plan.",
                              "free_max_level": FREE_MAX_LEVEL}},
        )


def plans() -> list[dict]:
    return [{"plan": key, "label": cfg["label"], "amount": cfg["amount"],
             "currency": cfg["currency"], "interval": cfg["interval"]}
            for key, cfg in PLANS.items()]


def start_checkout(db: Session, *, user: User, plan: str,
                   success_url: str, cancel_url: str) -> dict:
    if plan not in PLANS:
        raise BillingError("Unknown plan.", "unknown_plan", 422)
    try:
        url = get_provider().create_checkout(
            user_id=str(user.id), email=user.email, plan=plan,
            success_url=success_url, cancel_url=cancel_url)
    except PaymentError as e:
        raise BillingError(e.message, e.code, e.status) from e
    return {"url": url}


def open_portal(db: Session, *, user: User, return_url: str) -> dict:
    _, _, row = _get_or_default(db, user.id)
    if row is None or not row.stripe_customer_id:
        raise BillingError("No billing account yet — subscribe first.", "no_customer", 409)
    try:
        url = get_provider().create_portal(
            customer_id=row.stripe_customer_id, return_url=return_url)
    except PaymentError as e:
        raise BillingError(e.message, e.code, e.status) from e
    return {"url": url}


def _upsert(db: Session, user_id: uuid.UUID) -> Subscription:
    row = db.get(Subscription, user_id)
    if row is None:
        row = Subscription(user_id=user_id, tier="free_beta", status="active")
        db.add(row)
        db.flush()
    return row


def _period_end(ts) -> dt.datetime | None:
    if ts is None:
        return None
    try:
        return dt.datetime.fromtimestamp(int(ts), tz=dt.timezone.utc)
    except (ValueError, TypeError, OSError):
        return None


def handle_webhook(db: Session, event: dict) -> dict:
    """Apply a normalized provider event to the subscriber's row.

    The event carries a `user_id` (from checkout metadata) or a `customer_id` we
    stored earlier. State transitions here are the ONLY way a subscription becomes
    active/canceled/past_due.
    """
    etype = event.get("type", "")
    user_id = event.get("user_id") or (event.get("metadata") or {}).get("user_id")
    customer_id = event.get("customer_id")
    plan = event.get("tier") or event.get("plan")

    row = None
    if user_id:
        try:
            row = _upsert(db, uuid.UUID(str(user_id)))
        except ValueError:
            row = None
    if row is None and customer_id:
        row = db.query(Subscription).filter(
            Subscription.stripe_customer_id == customer_id).first()
    if row is None:
        return {"handled": False, "reason": "no matching subscriber"}

    if customer_id:
        row.stripe_customer_id = customer_id

    if etype in ("checkout.session.completed", "customer.subscription.created",
                 "customer.subscription.updated"):
        if plan in _PLAN_TIER:
            row.tier = _PLAN_TIER[plan]
        # trust provider status when present; else assume active on completion
        row.status = event.get("status") or "active"
        if row.status not in ("active", "trialing", "past_due", "canceled"):
            row.status = "active"
        row.current_period_end = _period_end(event.get("current_period_end")) or row.current_period_end
        row.canceled_at = None
    elif etype in ("customer.subscription.deleted",):
        row.status = "canceled"
        row.canceled_at = _now()
    elif etype in ("invoice.payment_failed",):
        row.status = "past_due"

    db.flush()
    return {"handled": True, "tier": row.tier, "status": row.status}


# --- admin (subscription_manage) -------------------------------------------

def grant_lifetime(db: Session, *, actor: User, user_id: str) -> dict:
    try:
        uid = uuid.UUID(str(user_id))
    except ValueError:
        raise BillingError("User not found.", "not_found", 404) from None
    if db.get(User, uid) is None:
        raise BillingError("User not found.", "not_found", 404)
    row = _upsert(db, uid)
    before = {"tier": row.tier, "status": row.status}
    row.tier = "lifetime"
    row.status = "active"
    row.canceled_at = None
    db.add(AdminAuditLog(
        actor_id=actor.id, action="grant_lifetime", target_table="subscriptions",
        target_id=uid, before=before, after={"tier": "lifetime", "status": "active"}))
    db.flush()
    return {"user_id": str(uid), "tier": row.tier, "status": row.status}

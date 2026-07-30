"""Subscription lifecycle and entitlement resolution (spec §19).

The read path (`entitlement_for`) is what gates every protected route: it turns
a user's subscription row plus the clock into an Entitlement. The write path
(checkout + webhook) keeps that row in step with Stripe.

Verification gate (R-29 from slice 11): starting checkout requires a verified
email. This is the natural home for that gate — you should confirm you own an
address before you pay through it.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import entitlements as ent
from app.domain.entitlements import Entitlement, SubStatus
from app.models.identity import User
from app.models.subscriptions import Subscription
from app.services.billing_provider import BillingProvider

log = logging.getLogger(__name__)

PRICES = {
    "month": {"amount": 7_00, "label": "$7 / month"},
    "year": {"amount": 60_00, "label": "$60 / year"},
}


class BillingError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _get_or_create(db: Session, user_id: uuid.UUID) -> Subscription:
    row = db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        row = Subscription(user_id=user_id, status=SubStatus.free.value)
        db.add(row)
        db.flush()
    return row


def entitlement_for(
    db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None,
) -> Entitlement:
    """The single read used by every gate. No row → free."""
    now = now or _now()
    row = db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        return ent.resolve_entitlement(SubStatus.free, now=now)
    return ent.resolve_entitlement(
        row.status, current_period_end=row.current_period_end, now=now,
    )


def subscription_state(db: Session, *, user_id: uuid.UUID) -> dict:
    entitlement = entitlement_for(db, user_id=user_id)
    row = db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()
    return {
        **entitlement.to_dict(),
        "cancel_at_period_end": bool(row.cancel_at_period_end) if row else False,
        "price_interval": row.price_interval if row else None,
        "prices": {k: v["label"] for k, v in PRICES.items()},
    }


# --- checkout -------------------------------------------------------------

def start_checkout(
    db: Session, *, user: User, interval: str, provider: BillingProvider,
    frontend_url: str,
) -> str:
    if interval not in PRICES:
        raise BillingError("Unknown plan.", "invalid_plan", 400)

    # R-29: confirm the address before taking money through it.
    if user.email_verified_at is None:
        raise BillingError(
            "Please verify your email before subscribing.",
            "email_unverified", 403,
        )

    entitlement = entitlement_for(db, user_id=user.id)
    if entitlement.full_access:
        raise BillingError(
            "You already have full access.", "already_subscribed", 409,
        )

    session = provider.create_checkout(
        user_id=str(user.id), email=user.email, interval=interval,
        success_url=f"{frontend_url}/pricing?status=success",
        cancel_url=f"{frontend_url}/pricing?status=canceled",
    )
    row = _get_or_create(db, user.id)
    row.stripe_customer_id = session.customer_id
    row.price_interval = interval
    db.flush()
    return session.url


def billing_portal(
    db: Session, *, user_id: uuid.UUID, provider: BillingProvider, frontend_url: str,
) -> str:
    row = db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    ).scalar_one_or_none()
    if row is None or not row.stripe_customer_id:
        raise BillingError("No billing account yet.", "no_customer", 404)
    return provider.create_billing_portal(
        customer_id=row.stripe_customer_id, return_url=f"{frontend_url}/pricing",
    )


# --- webhook --------------------------------------------------------------

def apply_webhook_event(db: Session, event: dict, *, now: dt.datetime | None = None) -> dict:
    """Translate a Stripe event into a subscription-row change.

    Written to be idempotent: Stripe retries webhooks, so applying the same
    event twice must land on the same state. Every branch here is a set-to-value,
    never an increment, so a replay is harmless.
    """
    now = now or _now()
    kind = event.get("type", "")
    data = (event.get("data") or {}).get("object") or {}

    user_id = _user_id_from_event(data)
    if user_id is None:
        log.info("webhook.no_user_ref", extra={"type": kind})
        return {"handled": False, "reason": "no user reference"}

    row = _get_or_create(db, user_id)

    if kind in ("checkout.session.completed", "customer.subscription.created",
                "customer.subscription.updated"):
        _apply_active(row, data, now)
    elif kind == "invoice.payment_failed":
        row.status = SubStatus.paid_past_due.value
    elif kind == "customer.subscription.deleted":
        row.status = SubStatus.paid_canceled.value
        row.cancel_at_period_end = False
    else:
        return {"handled": False, "reason": f"ignored event {kind}"}

    db.flush()
    return {"handled": True, "status": row.status}


def _apply_active(row: Subscription, data: dict, now: dt.datetime) -> None:
    row.status = SubStatus.paid_active.value
    row.stripe_subscription_id = (
        data.get("subscription") or data.get("id") or row.stripe_subscription_id
    )
    if data.get("customer"):
        row.stripe_customer_id = data["customer"]
    cancel_at_end = bool(data.get("cancel_at_period_end", False))
    row.cancel_at_period_end = cancel_at_end
    if cancel_at_end:
        row.status = SubStatus.paid_canceled.value
    period_end = data.get("current_period_end")
    if isinstance(period_end, (int, float)):
        row.current_period_end = dt.datetime.fromtimestamp(period_end, tz=dt.timezone.utc)
    interval = (data.get("metadata") or {}).get("interval")
    if interval in PRICES:
        row.price_interval = interval


def _user_id_from_event(data: dict) -> uuid.UUID | None:
    ref = (
        data.get("client_reference_id")
        or (data.get("metadata") or {}).get("user_id")
    )
    if not ref:
        return None
    try:
        return uuid.UUID(ref)
    except (ValueError, AttributeError):
        return None


# --- admin grants (beta / lifetime) --------------------------------------

def set_status(
    db: Session, *, user_id: uuid.UUID, status: str,
) -> dict:
    """Owner/admin grant of beta or lifetime access (spec §19: selected users
    get free lifetime subs). Not a payment path — a deliberate grant."""
    try:
        new = SubStatus(status)
    except ValueError as e:
        raise BillingError("Unknown status.", "invalid_status", 400) from e
    row = _get_or_create(db, user_id)
    row.status = new.value
    db.flush()
    return subscription_state(db, user_id=user_id)

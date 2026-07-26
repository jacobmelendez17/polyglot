"""Subscription state, checkout, billing portal, webhook, and admin grants.

The webhook is the one unauthenticated route (Stripe calls it), and it verifies
the signature through the provider before trusting anything. Everything else is
per-user or capability-gated.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from app.api.routes.subscription_schemas import (
    AdminSetStatusRequest,
    CheckoutOut,
    CheckoutRequest,
    EntitlementOut,
    PortalOut,
)
from app.auth.capabilities import Capability
from app.auth.deps import get_current_user, require
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.identity import User
from app.services import subscriptions as sub_svc
from app.services.billing_provider import build_billing_provider

router = APIRouter(prefix="/api/v1", tags=["subscriptions"])


def _http(err: sub_svc.BillingError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.get("/me/subscription", response_model=EntitlementOut)
def my_subscription(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return sub_svc.subscription_state(db, user_id=user.id)


@router.post("/me/subscription/checkout", response_model=CheckoutOut)
def checkout(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    try:
        url = sub_svc.start_checkout(
            db, user=user, interval=body.interval,
            provider=build_billing_provider(settings),
            frontend_url=getattr(settings, "frontend_url", "http://localhost:3000"),
        )
    except sub_svc.BillingError as e:
        raise _http(e) from e
    db.commit()
    return CheckoutOut(url=url)


@router.post("/me/subscription/portal", response_model=PortalOut)
def portal(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    try:
        url = sub_svc.billing_portal(
            db, user_id=user.id, provider=build_billing_provider(settings),
            frontend_url=getattr(settings, "frontend_url", "http://localhost:3000"),
        )
    except sub_svc.BillingError as e:
        raise _http(e) from e
    return PortalOut(url=url)


@router.post("/webhooks/stripe", status_code=200)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Stripe → us. Unauthenticated by nature; the signature is the auth.

    In the local/fake provider the body is trusted JSON, which is exactly what
    lets the dev flow post a synthetic 'payment succeeded' event.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    provider = build_billing_provider(settings)
    try:
        event = provider.verify_webhook(payload, signature)
    except Exception:  # pragma: no cover - signature failures
        raise HTTPException(status_code=400, detail={
            "error": {"code": "bad_signature", "message": "Invalid webhook signature."}})
    result = sub_svc.apply_webhook_event(db, event)
    db.commit()
    return result


@router.patch(
    "/admin/users/{user_id}/subscription",
    response_model=EntitlementOut,
    dependencies=[Depends(require(Capability.subscription_manage))],
)
def admin_set_status(
    body: AdminSetStatusRequest,
    user_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
):
    """Owner/admin grants beta or lifetime access (spec §19)."""
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, AttributeError) as e:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "User not found."}}) from e
    try:
        state = sub_svc.set_status(db, user_id=uid, status=body.status)
    except sub_svc.BillingError as e:
        raise _http(e) from e
    db.commit()
    return state

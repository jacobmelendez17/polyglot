"""Billing endpoints (spec §19). Complements the existing subscriptions router.

Reads require auth; the webhook is unauthenticated but provider-verified; the admin
grant is capability-gated. Distinct paths (`/me/entitlements`, `/billing/*`) so no
collision with the existing subscriptions router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.capabilities import Capability
from app.auth.deps import get_current_user, require
from app.db.session import get_db
from app.models.identity import User
from app.services import billing as svc
from app.services.payments import PaymentError, get_provider

router = APIRouter(prefix="/api/v1", tags=["billing"])


class EntitlementsOut(BaseModel):
    tier: str
    status: str
    entitled: bool
    free_max_level: int
    current_period_end: str | None = None
    canceled_at: str | None = None


class PlanOut(BaseModel):
    plan: str
    label: str
    amount: int
    currency: str
    interval: str


class CheckoutIn(BaseModel):
    plan: str = Field(pattern="^(monthly|annual)$")
    success_url: str = Field(default="/dashboard", max_length=500)
    cancel_url: str = Field(default="/pricing", max_length=500)


class UrlOut(BaseModel):
    url: str


class PortalIn(BaseModel):
    return_url: str = Field(default="/settings", max_length=500)


def _http(e: svc.BillingError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


@router.get("/me/entitlements", response_model=EntitlementsOut)
def entitlements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.get_entitlements(db, user=user)


@router.get("/billing/plans", response_model=list[PlanOut])
def list_plans(_: User = Depends(get_current_user)):
    return svc.plans()


@router.post("/billing/checkout", response_model=UrlOut)
def checkout(body: CheckoutIn, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    try:
        return svc.start_checkout(db, user=user, plan=body.plan,
                                  success_url=body.success_url, cancel_url=body.cancel_url)
    except svc.BillingError as e:
        raise _http(e) from e


@router.post("/billing/portal", response_model=UrlOut)
def portal(body: PortalIn, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    try:
        return svc.open_portal(db, user=user, return_url=body.return_url)
    except svc.BillingError as e:
        raise _http(e) from e


@router.post("/billing/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = get_provider().verify_and_parse_webhook(payload, signature)
    except PaymentError as e:
        raise HTTPException(status_code=e.status,
                           detail={"error": {"code": e.code, "message": e.message}}) from e
    result = svc.handle_webhook(db, event)
    db.commit()
    return result


@router.post("/admin/billing/{user_id}/grant-lifetime")
def grant_lifetime(user_id: str, db: Session = Depends(get_db),
                   actor: User = Depends(require(Capability.subscription_manage))):
    try:
        result = svc.grant_lifetime(db, actor=actor, user_id=user_id)
    except svc.BillingError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return result

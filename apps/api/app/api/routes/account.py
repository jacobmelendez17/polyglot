"""Password reset and email verification endpoints.

The two public routes here (`forgot-password`, `reset-password`) deliberately
give away nothing about which emails have accounts — same response either way
(see the service). They're rate-limited at the edge like the rest of /auth
(§25); the handlers stay focused on correctness.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.routes.account_schemas import (
    ForgotPasswordRequest,
    MessageOut,
    ResetPasswordRequest,
    VerificationStatusOut,
    VerifyEmailRequest,
    VerifyResultOut,
)
from app.auth.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.email.provider import build_provider
from app.models.identity import User
from app.services import account as account_svc

router = APIRouter(prefix="/api/v1/auth", tags=["account"])

# One generic line for both the found and not-found cases — the whole point.
_GENERIC_RESET = ("If an account exists for that address, a reset link is on its "
                  "way. Check your inbox.")


def _http(err: account_svc.AccountError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.post("/forgot-password", response_model=MessageOut)
def forgot_password(
    body: ForgotPasswordRequest, request: Request,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
):
    account_svc.request_password_reset(
        db, email=body.email, settings=settings, mailer=build_provider(settings)
    )
    db.commit()
    return MessageOut(message=_GENERIC_RESET)


@router.post("/reset-password", response_model=MessageOut)
def reset_password(
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    try:
        account_svc.confirm_password_reset(
            db, token=body.token, new_password=body.new_password
        )
    except account_svc.AccountError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return MessageOut(message="Your password has been reset. You can sign in now.")


@router.post("/send-verification", response_model=MessageOut)
def send_verification(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
):
    account_svc.request_email_verification(
        db, user=user, settings=settings, mailer=build_provider(settings)
    )
    db.commit()
    return MessageOut(message="Confirmation email sent. Check your inbox.")


@router.post("/verify-email", response_model=VerifyResultOut)
def verify_email(
    body: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    try:
        result = account_svc.confirm_email_verification(db, token=body.token)
    except account_svc.AccountError as e:
        db.rollback()
        raise _http(e) from e
    db.commit()
    return result


@router.get("/verification-status", response_model=VerificationStatusOut)
def verification_status(
    user: User = Depends(get_current_user),
):
    return account_svc.verification_status(user)

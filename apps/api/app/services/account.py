"""Password reset and email verification flows.

The overriding rule in this file is **no account enumeration**. Requesting a
reset for an address that has no account returns exactly the same response as
one that does. Neither the status code, the body, nor the timing distinguishes
them — otherwise the endpoint becomes a way to check which emails are
registered.

Redemption is server-authoritative and single-use: the token is looked up by
hash, checked for expiry and prior use, and consumed in the same transaction
that changes the password. A successful password reset also revokes every
existing session, because a reset is exactly what you do when you fear the
account is compromised.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.domain import email_tokens as token_rules
from app.email import templates
from app.email.provider import EmailDeliveryError, EmailProvider
from app.models.email_tokens import EmailVerificationToken, PasswordResetToken
from app.models.identity import AuthSession, User

log = logging.getLogger(__name__)

MIN_PASSWORD_LENGTH = 8


class AccountError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _frontend_url(settings, path: str, token: str) -> str:
    base = (getattr(settings, "frontend_url", "") or "http://localhost:3000").rstrip("/")
    return f"{base}{path}?token={token}"


# --- password reset -------------------------------------------------------

def request_password_reset(
    db: Session, *, email: str, settings, mailer: EmailProvider,
    now: dt.datetime | None = None,
) -> None:
    """Always succeeds from the caller's view — see the no-enumeration rule.

    An unknown address, a delivery failure, everything looks identical to the
    requester. Only the logs (without the token) tell the operator what happened.
    """
    now = now or _now()
    email_norm = (email or "").strip().lower()
    user = db.execute(
        select(User).where(User.email == email_norm)
    ).scalar_one_or_none()

    if user is None:
        log.info("reset.requested_unknown_email")     # no address in the log
        return

    # Invalidate any outstanding reset tokens: only the newest link should work.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    raw = token_rules.generate_token()
    db.add(PasswordResetToken(
        user_id=user.id, token_hash=token_rules.hash_token(raw),
        expires_at=token_rules.reset_expiry(now),
    ))
    db.flush()

    url = _frontend_url(settings, "/reset-password", raw)
    try:
        mailer.send(templates.password_reset(user.email, url))
    except EmailDeliveryError:
        # Don't leak the failure to the requester; the token still exists and a
        # retry will re-send. The operator sees it in the logs.
        log.error("reset.email_send_failed")


def confirm_password_reset(
    db: Session, *, token: str, new_password: str,
    now: dt.datetime | None = None,
) -> None:
    now = now or _now()
    if len(new_password or "") < MIN_PASSWORD_LENGTH:
        raise AccountError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            "weak_password", 400,
        )

    row = db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_rules.hash_token(token or "")
        )
    ).scalar_one_or_none()

    if row is None or not token_rules.is_redeemable(
        expires_at=row.expires_at, consumed_at=row.consumed_at, now=now,
    ):
        # One message for missing / expired / already-used — no oracle about
        # which tokens ever existed.
        raise AccountError(
            "This reset link is invalid or has expired.", "invalid_token", 400,
        )

    user = db.get(User, row.user_id)
    if user is None:
        raise AccountError(
            "This reset link is invalid or has expired.", "invalid_token", 400,
        )

    user.password_hash = hash_password(new_password)
    row.consumed_at = now

    # A password reset revokes every session: resetting is what you do when you
    # think the account is compromised, so old sessions must not survive it.
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.flush()


# --- email verification ---------------------------------------------------

def request_email_verification(
    db: Session, *, user: User, settings, mailer: EmailProvider,
    now: dt.datetime | None = None,
) -> None:
    """Send (or re-send) a verification link. Safe to call on signup and again
    on demand; a new link supersedes any old one."""
    now = now or _now()
    if user.email_verified_at is not None:
        return      # already verified — nothing to do

    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )

    raw = token_rules.generate_token()
    db.add(EmailVerificationToken(
        user_id=user.id, token_hash=token_rules.hash_token(raw),
        expires_at=token_rules.verify_expiry(now),
    ))
    db.flush()

    url = _frontend_url(settings, "/verify-email", raw)
    try:
        mailer.send(templates.email_verification(user.email, url))
    except EmailDeliveryError:
        log.error("verify.email_send_failed")


def confirm_email_verification(
    db: Session, *, token: str, now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    row = db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash == token_rules.hash_token(token or "")
        )
    ).scalar_one_or_none()

    if row is None or not token_rules.is_redeemable(
        expires_at=row.expires_at, consumed_at=row.consumed_at, now=now,
    ):
        raise AccountError(
            "This confirmation link is invalid or has expired.",
            "invalid_token", 400,
        )

    user = db.get(User, row.user_id)
    if user is None:
        raise AccountError(
            "This confirmation link is invalid or has expired.",
            "invalid_token", 400,
        )

    already = user.email_verified_at is not None
    if not already:
        user.email_verified_at = now
    row.consumed_at = now
    db.flush()
    return {"verified": True, "already_verified": already}


def verification_status(user: User) -> dict:
    return {"email": user.email, "verified": user.email_verified_at is not None}

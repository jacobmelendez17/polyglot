"""Auth service: bridges pure token/password logic to the database.

Handles account creation, credential verification, session issuance, refresh
rotation with reuse-detection, and logout. Every function takes an injected
`now` where time matters, so behavior is deterministic in tests.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_expiry,
)
from app.core.config import Settings
from app.models.enums import UserRole, UserStatus
from app.models.identity import AuthSession, Profile, User, UserSettings


class AuthError(Exception):
    """Generic auth failure. Message is safe to show; never leaks which field failed."""


@dataclass
class IssuedTokens:
    access_token: str
    refresh_token: str      # returned to client ONCE
    session_id: uuid.UUID
    user: User


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _password_column(user: User) -> str | None:
    # Password hash is stored on the user row via a dynamic attribute set in signup.
    return getattr(user, "password_hash", None)


def create_account(
    db: Session, *, email: str, password: str, settings: Settings,
    display_name: str | None = None,
    role: UserRole = UserRole.user, now: dt.datetime | None = None,
) -> User:
    email_norm = email.strip().lower()
    if not email_norm or "@" not in email_norm:
        raise AuthError("A valid email is required.")
    if len(password) < 8:
        raise AuthError("Password must be at least 8 characters.")
    existing = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if existing is not None:
        raise AuthError("An account with that email already exists.")

    user = User(id=uuid.uuid4(), email=email_norm, role=role, status=UserStatus.active)
    user.password_hash = hash_password(password)  # column added in migration
    db.add(user)
    db.flush()
    name = (display_name or "").strip() or email_norm.split("@")[0]
    db.add(Profile(user_id=user.id, display_name=name))
    db.add(UserSettings(user_id=user.id))
    db.flush()
    return user


def _issue_session(
    db: Session, *, user: User, settings: Settings, user_agent: str | None,
    ip_hash: str | None, now: dt.datetime, rotated_from: uuid.UUID | None = None,
) -> IssuedTokens:
    session_id = uuid.uuid4()
    refresh = generate_refresh_token()
    db.add(AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        user_agent=(user_agent or "")[:400],
        ip_hash=ip_hash,
        expires_at=refresh_expiry(now),
        rotated_from_session_id=rotated_from,
    ))
    db.flush()
    access = create_access_token(
        user_id=user.id, role=user.role.value, session_id=session_id,
        secret=settings.auth_secret, audience=settings.auth_audience,
        issuer=settings.auth_issuer, now=now,
    )
    return IssuedTokens(access_token=access, refresh_token=refresh,
                        session_id=session_id, user=user)


def login(
    db: Session, *, email: str, password: str, settings: Settings,
    user_agent: str | None = None, ip_hash: str | None = None,
    now: dt.datetime | None = None,
) -> IssuedTokens:
    now = now or _now()
    email_norm = email.strip().lower()
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    # Uniform failure regardless of whether the email exists (no user enumeration).
    if user is None or user.status != UserStatus.active:
        # Still run a hash to keep timing similar.
        verify_password(password, "pbkdf2_sha256$1$00$00")
        raise AuthError("Invalid email or password.")
    stored = _password_column(user)
    if not stored or not verify_password(password, stored):
        raise AuthError("Invalid email or password.")
    # Opportunistic rehash if our iteration count has increased.
    if needs_rehash(stored):
        user.password_hash = hash_password(password)
    user.last_seen_at = now
    return _issue_session(db, user=user, settings=settings,
                          user_agent=user_agent, ip_hash=ip_hash, now=now)


def refresh_session(
    db: Session, *, refresh_token: str, settings: Settings,
    user_agent: str | None = None, ip_hash: str | None = None,
    now: dt.datetime | None = None,
) -> IssuedTokens:
    """Rotate a refresh token. Reuse of an already-rotated/revoked token revokes
    the entire session chain (theft detection)."""
    now = now or _now()
    token_hash = hash_refresh_token(refresh_token)
    session = db.execute(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
    ).scalar_one_or_none()
    if session is None:
        raise AuthError("Invalid session.")

    if session.revoked_at is not None:
        # Reuse of a revoked token: revoke the whole chain descending from it.
        _revoke_chain(db, session.id, now)
        raise AuthError("Session reuse detected. Please sign in again.")
    if session.expires_at <= now:
        session.revoked_at = now
        raise AuthError("Session expired. Please sign in again.")

    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.active:
        raise AuthError("Account is not active.")

    # Rotate: revoke current, issue a fresh session pointing back to it.
    session.revoked_at = now
    return _issue_session(db, user=user, settings=settings, user_agent=user_agent,
                          ip_hash=ip_hash, now=now, rotated_from=session.id)


def logout(db: Session, *, refresh_token: str, now: dt.datetime | None = None) -> None:
    now = now or _now()
    token_hash = hash_refresh_token(refresh_token)
    session = db.execute(
        select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
    ).scalar_one_or_none()
    if session is not None and session.revoked_at is None:
        session.revoked_at = now


def logout_all(db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None) -> int:
    now = now or _now()
    sessions = db.execute(
        select(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
        )
    ).scalars().all()
    for s in sessions:
        s.revoked_at = now
    return len(sessions)


def _revoke_chain(db: Session, session_id: uuid.UUID, now: dt.datetime) -> None:
    """Revoke a session and every session rotated from it, transitively."""
    frontier = [session_id]
    seen: set[uuid.UUID] = set()
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        children = db.execute(
            select(AuthSession).where(AuthSession.rotated_from_session_id == current)
        ).scalars().all()
        for child in children:
            child.revoked_at = now
            frontier.append(child.id)
    # revoke the origin too
    origin = db.get(AuthSession, session_id)
    if origin is not None:
        origin.revoked_at = now

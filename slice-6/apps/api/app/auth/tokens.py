"""Short-lived access JWTs + opaque refresh tokens (PLANNING §4, §25).

Access token: HS256 JWT, 10-minute TTL, carries sub/role/sid/aud/iss/exp.
  (HS256 with a server secret for MVP; the plan allows moving to RS256/JWKS when
   Auth.js in Next.js becomes the issuer. verify_access_token is the single
   verification point either way.)
Refresh token: 256-bit opaque random string. Only its hash is stored server-side
  in auth_sessions. Rotation on every use; reuse of a rotated token is detectable.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import uuid
from dataclasses import dataclass

import jwt

ACCESS_TTL = dt.timedelta(minutes=10)
REFRESH_TTL = dt.timedelta(days=30)
_ALGO = "HS256"


@dataclass(frozen=True)
class AccessClaims:
    sub: uuid.UUID          # user id
    role: str
    sid: uuid.UUID          # session id
    exp: dt.datetime
    iat: dt.datetime


class TokenError(Exception):
    """Raised when an access token is missing/invalid/expired/wrong-audience."""


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def create_access_token(
    *, user_id: uuid.UUID, role: str, session_id: uuid.UUID, secret: str,
    audience: str, issuer: str, now: dt.datetime | None = None,
) -> str:
    issued = now or _now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": str(session_id),
        "aud": audience,
        "iss": issuer,
        "iat": int(issued.timestamp()),
        "exp": int((issued + ACCESS_TTL).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=_ALGO)


def verify_access_token(
    token: str, *, secret: str, audience: str, issuer: str,
) -> AccessClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[_ALGO], audience=audience, issuer=issuer,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            leeway=30,  # 30s clock-skew tolerance
        )
    except jwt.PyJWTError as exc:  # expired, bad sig, wrong aud/iss, etc.
        raise TokenError(str(exc)) from exc
    return AccessClaims(
        sub=uuid.UUID(payload["sub"]),
        role=payload["role"],
        sid=uuid.UUID(payload["sid"]),
        exp=dt.datetime.fromtimestamp(payload["exp"], tz=dt.timezone.utc),
        iat=dt.datetime.fromtimestamp(payload["iat"], tz=dt.timezone.utc),
    )


def generate_refresh_token() -> str:
    """Opaque, URL-safe, 256-bit. Returned to client ONCE; only its hash is stored."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """SHA-256 hex. Deterministic so we can look up a presented token by its hash."""
    return hashlib.sha256(token.encode()).hexdigest()


def refresh_expiry(now: dt.datetime | None = None) -> dt.datetime:
    return (now or _now()) + REFRESH_TTL

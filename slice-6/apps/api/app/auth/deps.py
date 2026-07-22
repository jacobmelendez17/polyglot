"""FastAPI dependencies for authentication and authorization.

- get_current_user: verifies the bearer access token and loads the user, checking
  that the token session is still active (not revoked/expired server-side).
- require(capability): returns a dependency that enforces a capability, 403 otherwise.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.capabilities import Capability, has_capability
from app.auth.tokens import TokenError, verify_access_token
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.enums import UserStatus
from app.models.identity import AuthSession, User

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"error": {"code": "unauthorized", "message": "Authentication required."}},
    headers={"WWW-Authenticate": "Bearer"},
)


def _bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _UNAUTH
    return token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    token = _bearer_token(request)
    try:
        claims = verify_access_token(
            token, secret=settings.auth_secret,
            audience=settings.auth_audience, issuer=settings.auth_issuer,
        )
    except TokenError:
        raise _UNAUTH from None

    # Server-side session must still be valid (supports logout / revocation even
    # while an access token is within its short TTL window).
    session = db.get(AuthSession, claims.sid)
    if session is None or session.revoked_at is not None:
        raise _UNAUTH

    user = db.get(User, claims.sub)
    if user is None or user.status != UserStatus.active:
        raise _UNAUTH
    return user


def require(capability: Capability) -> Callable[..., User]:
    """Dependency factory enforcing a capability (PLANNING §4)."""

    def _dep(user: User = Depends(get_current_user)) -> User:
        if not has_capability(user.role, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "forbidden",
                                  "message": "You do not have permission to do that."}},
            )
        return user

    return _dep

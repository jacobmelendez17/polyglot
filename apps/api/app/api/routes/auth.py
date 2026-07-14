"""Auth endpoints: signup, login, refresh, logout, and /me.

Consistent error shape: {\"error\": {\"code\", \"message\"}}. Rate limiting for these
routes is enforced at the edge (Cloudflare/Upstash per PLANNING §25); the handlers
stay focused on correctness.
"""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.routes.schemas import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    SignupRequest,
    TokenResponse,
)
from app.auth import service
from app.auth.capabilities import capabilities_for
from app.auth.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.identity import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _ip_hash(request: Request) -> str | None:
    client = request.client.host if request.client else None
    if not client:
        return None
    return hashlib.sha256(client.encode()).hexdigest()


def _auth_error(message: str, code: str = "auth_error", status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"error": {"code": code, "message": message}},
    )


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest, request: Request,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        service.create_account(db, email=body.email, password=body.password, settings=settings)
        tokens = service.login(
            db, email=body.email, password=body.password, settings=settings,
            user_agent=request.headers.get("user-agent"), ip_hash=_ip_hash(request),
        )
        db.commit()
    except service.AuthError as exc:
        db.rollback()
        raise _auth_error(str(exc)) from exc
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest, request: Request,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        tokens = service.login(
            db, email=body.email, password=body.password, settings=settings,
            user_agent=request.headers.get("user-agent"), ip_hash=_ip_hash(request),
        )
        db.commit()
    except service.AuthError as exc:
        db.rollback()
        raise _auth_error(str(exc), code="invalid_credentials", status_code=401) from exc
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest, request: Request,
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        tokens = service.refresh_session(
            db, refresh_token=body.refresh_token, settings=settings,
            user_agent=request.headers.get("user-agent"), ip_hash=_ip_hash(request),
        )
        db.commit()
    except service.AuthError as exc:
        db.commit()  # persist any revocation side-effects from reuse detection
        raise _auth_error(str(exc), code="invalid_session", status_code=401) from exc
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: LogoutRequest, db: Session = Depends(get_db)) -> None:
    service.logout(db, refresh_token=body.refresh_token)
    db.commit()


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    caps = sorted(c.value for c in capabilities_for(user.role))
    return MeResponse(id=str(user.id), email=user.email, role=user.role.value, capabilities=caps)

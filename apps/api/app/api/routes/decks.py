"""Decks — a browsable, read-only view of unlocked content.

All routes are per-user and scoped to unlocked levels. Nothing here writes.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.routes.account_schemas import (
    DECK_TYPE_PATTERN,
    DeckPageOut,
    DeckSummaryOut,
)
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import decks as deck_svc

router = APIRouter(prefix="/api/v1/me/decks", tags=["decks"])


@router.get("", response_model=list[DeckSummaryOut])
def list_decks(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return deck_svc.list_decks(db, user_id=user.id)


@router.get("/{deck_type}", response_model=DeckPageOut)
def deck_items(
    deck_type: str = Path(pattern=DECK_TYPE_PATTERN),
    limit: int = Query(default=50, ge=1, le=deck_svc.MAX_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return deck_svc.deck_items(
            db, user_id=user.id, deck_type=deck_type, limit=limit, offset=offset
        )
    except deck_svc.DeckError as e:
        raise HTTPException(
            status_code=e.status,
            detail={"error": {"code": e.code, "message": e.message}},
        ) from e


# ============================================================================
# slice 43 — deck catalog (unlock states) + learner-built decks.
# Appended to the existing decks router. Paths use two+ segments after /decks so
# they never collide with the single-segment GET /me/decks/{deck_type} route.
# ============================================================================
from pydantic import BaseModel, Field  # noqa: E402

from app.services import deck_catalog as _catalog  # noqa: E402


class _CustomDeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)


@router.get("/catalog/all")
def deck_catalog_all(
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Every deck with unlock state + progress, plus the user's custom decks."""
    return deck_catalog_list(db, user)


def deck_catalog_list(db: Session, user: User):
    return _catalog.list_all_decks(db, user)


@router.post("/catalog/custom", status_code=201)
def create_custom_deck(
    body: _CustomDeckCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = _catalog.create_custom_deck(db, user, name=body.name, description=body.description)
    except _catalog.DeckCatalogError as e:
        raise HTTPException(status_code=e.status,
                            detail={"error": {"code": e.code, "message": e.message}}) from e
    db.commit()
    return result


@router.delete("/catalog/custom/{deck_id}")
def delete_custom_deck(
    deck_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = _catalog.delete_custom_deck(db, user, deck_id)
    except _catalog.DeckCatalogError as e:
        raise HTTPException(status_code=e.status,
                            detail={"error": {"code": e.code, "message": e.message}}) from e
    db.commit()
    return result
# === end slice 43 ===========================================================

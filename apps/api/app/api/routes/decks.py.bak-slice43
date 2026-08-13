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

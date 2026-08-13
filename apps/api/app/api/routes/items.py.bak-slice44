"""Item detail, review history, user synonyms, and level progression.

Every route here requires an authenticated user and scopes reads to that user.
Item visibility is gated server-side on level unlock — the same rule the lesson
routes enforce — so a locked item is a 403 rather than a hidden link.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.api.routes.item_schemas import (
    ITEM_TYPE_PATTERN,
    AddSynonymOut,
    AddSynonymRequest,
    ItemDetailOut,
    LevelProgressOut,
    ReviewHistoryOut,
    UserSynonymOut,
)
from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import items as item_svc

router = APIRouter(prefix="/api/v1", tags=["items"])
log = logging.getLogger(__name__)


def _http(err: item_svc.ItemError) -> HTTPException:
    return HTTPException(
        status_code=err.status,
        detail={"error": {"code": err.code, "message": err.message}},
    )


@router.get("/items/{item_type}/{item_id}", response_model=ItemDetailOut)
def item_detail(
    item_type: str = Path(pattern=ITEM_TYPE_PATTERN),
    item_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return item_svc.get_item_detail(
            db, user_id=user.id, item_type=item_type, item_id=item_id
        )
    except item_svc.ItemError as e:
        raise _http(e) from e


@router.get("/items/{item_type}/{item_id}/history", response_model=ReviewHistoryOut)
def item_history(
    item_type: str = Path(pattern=ITEM_TYPE_PATTERN),
    item_id: str = Path(max_length=64),
    limit: int = Query(default=20, ge=1, le=item_svc.MAX_HISTORY_PAGE),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return item_svc.list_review_history(
            db, user_id=user.id, item_type=item_type, item_id=item_id,
            limit=limit, offset=offset,
        )
    except item_svc.ItemError as e:
        raise _http(e) from e


@router.get(
    "/items/{item_type}/{item_id}/synonyms", response_model=list[UserSynonymOut]
)
def list_synonyms(
    item_type: str = Path(pattern=ITEM_TYPE_PATTERN),
    item_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return item_svc.list_user_synonyms(
            db, user_id=user.id, item_type=item_type, item_id=item_id
        )
    except item_svc.ItemError as e:
        raise _http(e) from e


@router.post(
    "/items/{item_type}/{item_id}/synonyms",
    response_model=AddSynonymOut, status_code=201,
)
def add_synonym(
    body: AddSynonymRequest,
    item_type: str = Path(pattern=ITEM_TYPE_PATTERN),
    item_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        result = item_svc.add_user_synonym(
            db, user_id=user.id, item_type=item_type, item_id=item_id,
            synonym=body.synonym,
        )
    except item_svc.ItemError as e:
        raise _http(e) from e
    db.commit()
    # Content, not credentials: safe to log the id, never the text.
    log.info("user_synonym_added", extra={"item_type": item_type, "item_id": item_id})
    return result


@router.delete("/synonyms/{synonym_id}", status_code=204)
def delete_synonym(
    synonym_id: str = Path(max_length=64),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        item_svc.delete_user_synonym(db, user_id=user.id, synonym_id=synonym_id)
    except item_svc.ItemError as e:
        raise _http(e) from e
    db.commit()
    return None


@router.get("/levels/{position}/progress", response_model=LevelProgressOut)
def level_progress(
    position: int = Path(ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return item_svc.get_level_progress(db, user_id=user.id, position=position)
    except item_svc.ItemError as e:
        raise _http(e) from e

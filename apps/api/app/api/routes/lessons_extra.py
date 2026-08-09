"""Customize Lessons endpoint (§20, by request). Auth required, read-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import custom_lesson as svc

router = APIRouter(prefix="/api/v1/lessons", tags=["lessons"])


class SelectableItem(BaseModel):
    item_type: str
    item_id: str
    term: str
    translation: str
    part_of_speech: str


class SelectableLevel(BaseModel):
    level: int
    title: str
    items: list[SelectableItem]


class SelectableResponse(BaseModel):
    levels: list[SelectableLevel]


@router.get("/selectable", response_model=SelectableResponse)
def selectable(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return SelectableResponse(levels=svc.selectable_items(db, user.id))

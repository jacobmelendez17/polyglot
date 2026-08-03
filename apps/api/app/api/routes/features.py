"""Feature-unlock endpoint (spec §7). Auth required."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import features as svc

router = APIRouter(prefix="/api/v1", tags=["features"])


class FeatureState(BaseModel):
    feature: str
    unlock_level: int
    unlocked: bool
    levels_remaining: int


class FeaturesOut(BaseModel):
    completed_levels: int
    features: list[FeatureState]


@router.get("/features", response_model=FeaturesOut)
def list_features(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.list_features(db, user.id)

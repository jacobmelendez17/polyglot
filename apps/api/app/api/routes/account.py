"""Account endpoints (spec §16, §20): settings + profile. Auth required."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import account as svc

router = APIRouter(prefix="/api/v1/me", tags=["account"])


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = svc.get_settings(db, user.id)
    db.commit()
    return result


@router.patch("/settings")
def patch_settings(patch: dict, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    # Body is an open dict; the pure validator decides what's allowed, so unknown
    # keys are rejected with a clear per-field error rather than silently ignored.
    if not isinstance(patch, dict):
        raise HTTPException(status_code=422,
            detail={"error": {"code": "invalid_body", "message": "Expected an object."}})
    try:
        result = svc.update_settings(db, user.id, patch)
    except svc.SettingsError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail={
            "error": {"code": "invalid_settings", "message": "Some settings were invalid.",
                      "field_errors": e.field_errors}}) from e
    db.commit()
    return result


@router.get("/profile")
def get_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = svc.get_profile(db, user)
    db.commit()
    return result


@router.patch("/profile")
def patch_profile(body: ProfileUpdate, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    result = svc.update_profile(db, user, display_name=body.display_name,
                                bio=body.bio, timezone=body.timezone)
    db.commit()
    return result

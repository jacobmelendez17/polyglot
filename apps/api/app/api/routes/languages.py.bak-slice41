"""Language selection endpoints (spec §1, §16, §32). Auth required."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.session import get_db
from app.models.identity import User
from app.services import languages as svc

router = APIRouter(prefix="/api/v1", tags=["languages"])


class LanguageOut(BaseModel):
    code: str
    name: str
    native_name: str


class SetLanguageIn(BaseModel):
    code: str = Field(min_length=2, max_length=10)


def _http(e: svc.LanguageError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


@router.get("/languages", response_model=list[LanguageOut])
def list_languages(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return [svc.as_dict(l) for l in svc.list_enabled(db)]


@router.get("/me/language", response_model=LanguageOut)
def current_language(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lang = svc.get_active(db, user_id=user.id)
    if lang is None:
        raise HTTPException(status_code=409,
            detail={"error": {"code": "no_language", "message": "No languages available."}})
    return svc.as_dict(lang)


@router.put("/me/language", response_model=LanguageOut)
def set_language(body: SetLanguageIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    try:
        lang = svc.set_active(db, user_id=user.id, code=body.code)
    except svc.LanguageError as e:
        db.rollback(); raise _http(e) from e
    db.commit()
    return svc.as_dict(lang)

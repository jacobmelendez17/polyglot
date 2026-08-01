"""Reading resource endpoints (spec §7).

Reader routes require an authenticated user; admin routes are capability-gated
(content_edit / content_publish) and audit-logged in the service.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.capabilities import Capability, has_capability
from app.auth.deps import get_current_user, require
from app.db.session import get_db
from app.models.identity import User
from app.services import reading as svc

router = APIRouter(prefix="/api/v1", tags=["reading"])


def _is_editor(user: User) -> bool:
    return has_capability(user.role, Capability.content_edit)


def _http(e: svc.ReadingError) -> HTTPException:
    return HTTPException(status_code=e.status,
                        detail={"error": {"code": e.code, "message": e.message}})


# --- schemas ---------------------------------------------------------------

class TextListItem(BaseModel):
    id: str
    title: str
    author: str
    source_type: str
    level: int
    summary: str
    external_url: str


class TextOut(BaseModel):
    id: str
    title: str
    author: str
    source_type: str
    level: int
    body: str
    external_url: str
    summary: str
    status: str


class LookupOut(BaseModel):
    word: str
    found: bool
    term: str | None = None
    translation: str | None = None
    part_of_speech: str | None = None
    item_id: str | None = None


class AnnotationOut(BaseModel):
    id: str
    start: int
    end: int
    quote: str
    note: str


class AnnotationIn(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    note: str = Field(default="", max_length=2000)


class AdminTextIn(BaseModel):
    language_code: str = "es-MX"
    title: str = Field(min_length=1, max_length=300)
    source_type: str = Field(pattern="^(original|external)$")
    body: str = Field(default="", max_length=100000)
    external_url: str = Field(default="", max_length=600)
    author: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=2000)
    level: int = Field(default=1, ge=1, le=99)


class AdminUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    author: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=100000)
    external_url: str | None = Field(default=None, max_length=600)
    summary: str | None = Field(default=None, max_length=2000)
    level: int | None = Field(default=None, ge=1, le=99)


class StatusIn(BaseModel):
    status: str = Field(pattern="^(draft|in_review|published|archived)$")


# --- reader ----------------------------------------------------------------

@router.get("/reading", response_model=list[TextListItem])
def library(language: str = "es-MX", level: int | None = Query(default=None),
            db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return svc.list_texts(db, language_code=language, level=level)


@router.get("/reading/lookup", response_model=LookupOut)
def lookup(language: str = "es-MX", word: str = Query(max_length=80),
           db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return svc.lookup_word(db, language_code=language, word=word)


@router.get("/reading/{text_id}", response_model=TextOut)
def read(text_id: str = Path(max_length=64), db: Session = Depends(get_db),
         user: User = Depends(get_current_user)):
    try:
        return svc.get_text(db, text_id=text_id, is_editor=_is_editor(user))
    except svc.ReadingError as e:
        raise _http(e) from e


@router.get("/reading/{text_id}/annotations", response_model=list[AnnotationOut])
def annotations(text_id: str = Path(max_length=64), db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    return svc.list_annotations(db, user_id=user.id, text_id=text_id)


@router.post("/reading/{text_id}/annotations", response_model=AnnotationOut)
def add_annotation(body: AnnotationIn, text_id: str = Path(max_length=64),
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.add_annotation(db, user_id=user.id, text_id=text_id,
                                    start=body.start, end=body.end, note=body.note)
    except svc.ReadingError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


@router.delete("/reading/annotations/{annotation_id}")
def delete_annotation(annotation_id: str = Path(max_length=64),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = svc.delete_annotation(db, user_id=user.id, annotation_id=annotation_id)
    except svc.ReadingError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


# --- admin authoring -------------------------------------------------------

@router.get("/admin/reading")
def admin_list(language: str = "es-MX", db: Session = Depends(get_db),
               _: User = Depends(require(Capability.content_edit))):
    return svc.admin_list(db, language_code=language)


@router.post("/admin/reading")
def admin_create(body: AdminTextIn, db: Session = Depends(get_db),
                 actor: User = Depends(require(Capability.content_edit))):
    try:
        result = svc.create_text(
            db, actor_id=actor.id, language_code=body.language_code, title=body.title,
            source_type=body.source_type, body=body.body, external_url=body.external_url,
            author=body.author, summary=body.summary, level=body.level)
    except svc.ReadingError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


@router.patch("/admin/reading/{text_id}")
def admin_update(body: AdminUpdateIn, text_id: str = Path(max_length=64),
                 db: Session = Depends(get_db),
                 actor: User = Depends(require(Capability.content_edit))):
    try:
        result = svc.update_text(db, actor_id=actor.id, text_id=text_id,
                                 **body.model_dump(exclude_unset=True))
    except svc.ReadingError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result


@router.patch("/admin/reading/{text_id}/status")
def admin_status(body: StatusIn, text_id: str = Path(max_length=64),
                 db: Session = Depends(get_db),
                 actor: User = Depends(require(Capability.content_publish))):
    try:
        result = svc.set_status(db, actor_id=actor.id, text_id=text_id, status=body.status)
    except svc.ReadingError as e:
        db.rollback(); raise _http(e) from e
    db.commit(); return result

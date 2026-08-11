"""Admin routes: curriculum import, content management, users.

Every route is capability-gated (PLANNING §4) and every mutation writes an
admin_audit_log row in the same transaction (§22). Nothing here is reachable by
a normal user.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.schemas import (
    AdminUserOut,
    ContentItemOut,
    ContentListOut,
    ImportReportOut,
    ImportResult,
    RoleChange,
    StatusChange,
)
from app.auth.capabilities import Capability
from app.auth.deps import require
from app.db.base import ContentStatus
from app.db.session import get_db
from app.importer.import_service import import_grammar, import_vocabulary
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import UserRole
from app.models.identity import Profile, User
from app.models.platform import AdminAuditLog, ContentImport

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

MAX_IMPORT_BYTES = 5 * 1024 * 1024  # 5 MB cap on uploads


def _audit(db: Session, actor: User, action: str, table: str,
           target_id: uuid.UUID | None = None, before=None, after=None) -> None:
    db.add(AdminAuditLog(
        actor_id=actor.id, action=action, target_table=table,
        target_id=target_id, before=before or {}, after=after or {},
    ))


def _language(db: Session, code: str) -> Language:
    lang = db.execute(select(Language).where(Language.code == code)).scalar_one_or_none()
    if lang is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "unknown_language",
                              "message": f"Language '{code}' is not set up. Add it first."}},
        )
    return lang


def _spanish(db: Session) -> Language:
    return _language(db, "es-MX")


async def _read_csv(file: UploadFile) -> str:
    raw = await file.read()
    if len(raw) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"error": {"code": "file_too_large", "message": "CSV exceeds 5 MB."}},
        )
    try:
        return raw.decode("utf-8-sig")  # tolerate a BOM
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "bad_encoding", "message": "CSV must be UTF-8."}},
        ) from None


@router.post("/imports/vocabulary", response_model=ImportResult)
async def import_vocab(
    file: UploadFile,
    language: str = Query(default="es-MX", max_length=10),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_import)),
) -> ImportResult:
    text = await _read_csv(file)
    import_id = uuid.uuid4()
    lang = _language(db, language)
    created, updated, report = import_vocabulary(
        db, language_id=lang.id, csv_text=text, import_id=import_id,
    )
    db.add(ContentImport(
        id=import_id, filename=file.filename or "vocabulary.csv",
        kind="vocabulary", report=report.to_dict(), created_by=actor.id,
    ))
    _audit(db, actor, "import_vocabulary", "vocabulary_items",
           after={"created": created, "updated": updated})
    db.commit()
    return ImportResult(created=created, updated=updated,
                        report=ImportReportOut(**report.to_dict()))


@router.post("/imports/grammar", response_model=ImportResult)
async def import_gram(
    file: UploadFile,
    language: str = Query(default="es-MX", max_length=10),
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_import)),
) -> ImportResult:
    text = await _read_csv(file)
    import_id = uuid.uuid4()
    lang = _language(db, language)
    created, updated, report = import_grammar(
        db, language_id=lang.id, csv_text=text, import_id=import_id,
    )
    db.add(ContentImport(
        id=import_id, filename=file.filename or "grammar.csv",
        kind="grammar", report=report.to_dict(), created_by=actor.id,
    ))
    _audit(db, actor, "import_grammar", "grammar_points",
           after={"created": created, "updated": updated})
    db.commit()
    return ImportResult(created=created, updated=updated,
                        report=ImportReportOut(**report.to_dict()))


@router.get("/content/vocabulary", response_model=ContentListOut)
def list_vocab(
    level: int | None = None, status_filter: str | None = None,
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_edit)),
) -> ContentListOut:
    limit = max(1, min(limit, 200))
    q = select(VocabularyItem, Module.position).join(Module, VocabularyItem.module_id == Module.id)
    if level is not None:
        q = q.where(Module.position == level)
    if status_filter:
        q = q.where(VocabularyItem.status == ContentStatus(status_filter))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(
        q.order_by(Module.position, VocabularyItem.term).limit(limit).offset(offset)
    ).all()
    items = [
        ContentItemOut(
            id=str(v.id), term=v.term, translation=v.primary_translation,
            part_of_speech=v.part_of_speech, level=pos, status=v.status.value,
        )
        for v, pos in rows
    ]
    return ContentListOut(items=items, total=total)


@router.get("/content/grammar", response_model=ContentListOut)
def list_grammar(
    level: int | None = None, status_filter: str | None = None,
    limit: int = 50, offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_edit)),
) -> ContentListOut:
    limit = max(1, min(limit, 200))
    q = select(GrammarPoint, Module.position).join(Module, GrammarPoint.module_id == Module.id)
    if level is not None:
        q = q.where(Module.position == level)
    if status_filter:
        q = q.where(GrammarPoint.status == ContentStatus(status_filter))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(
        q.order_by(Module.position, GrammarPoint.title).limit(limit).offset(offset)
    ).all()
    items = [
        ContentItemOut(
            id=str(g.id), term=g.title, translation=g.translation,
            part_of_speech=g.part_of_speech, level=pos, status=g.status.value,
        )
        for g, pos in rows
    ]
    return ContentListOut(items=items, total=total)


def _set_status(db, actor, model, item_id: str, new_status: str, cap_needed: Capability):
    obj = db.get(model, uuid.UUID(item_id))
    if obj is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "Item not found."}},
        )
    before = obj.status.value
    obj.status = ContentStatus(new_status)
    _audit(db, actor, "set_status", model.__tablename__, target_id=obj.id,
           before={"status": before}, after={"status": new_status})
    db.commit()
    return {"id": item_id, "status": new_status}


@router.patch("/content/vocabulary/{item_id}/status")
def set_vocab_status(
    item_id: str, body: StatusChange,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_publish)),
):
    return _set_status(db, actor, VocabularyItem, item_id, body.status, Capability.content_publish)


@router.patch("/content/grammar/{item_id}/status")
def set_grammar_status(
    item_id: str, body: StatusChange,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_publish)),
):
    return _set_status(db, actor, GrammarPoint, item_id, body.status, Capability.content_publish)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.user_manage)),
) -> list[AdminUserOut]:
    rows = db.execute(
        select(User, Profile.display_name).outerjoin(Profile, Profile.user_id == User.id)
        .order_by(User.created_at)
    ).all()
    return [
        AdminUserOut(
            id=str(u.id), email=u.email, name=name or u.email.split("@")[0],
            role=u.role.value, status=u.status.value,
        )
        for u, name in rows
    ]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
def change_role(
    user_id: str, body: RoleChange,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.user_manage)),
) -> AdminUserOut:
    target = db.get(User, uuid.UUID(user_id))
    if target is None:
        raise HTTPException(
            status_code=404,
            detail={"error": {"code": "not_found", "message": "User not found."}},
        )
    # Only an owner may grant or revoke the owner role.
    if (body.role == "owner" or target.role == UserRole.owner) and actor.role != UserRole.owner:
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "forbidden",
                              "message": "Only an owner can manage the owner role."}},
        )
    before = target.role.value
    target.role = UserRole(body.role)
    _audit(db, actor, "change_role", "users", target_id=target.id,
           before={"role": before}, after={"role": body.role})
    db.commit()
    profile = db.get(Profile, target.id)
    return AdminUserOut(
        id=str(target.id), email=target.email,
        name=profile.display_name if profile else target.email.split("@")[0],
        role=target.role.value, status=target.status.value,
    )


# ============================================================================
# slice 39 — in-app curriculum editor (CRUD + move + soft delete/restore)
# Appended to the existing admin router. Every mutation is capability-gated and
# writes an admin_audit_log row (§22). Vocabulary carries a `batch` (1–4); grammar
# has no sub-batch. Soft delete sets deleted_at + archived; permanent delete is
# owner-only and lives in the archives view (not implemented here).
# ============================================================================
import datetime as _dt39

from pydantic import BaseModel, Field

from app.domain.content_edit import (
    EditError,
    normalize_article_gender,
    validate_batch,
    validate_level,
    validate_term,
)
from app.domain.normalize import normalize_term as _normalize_term39


def _now39() -> _dt39.datetime:
    return _dt39.datetime.now(tz=_dt39.timezone.utc)


def _uuid39(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}}) from None


def _edit_http(e: EditError) -> HTTPException:
    return HTTPException(status_code=422, detail={"error": {"code": e.code, "message": e.message}})


def _module_for_level39(db: Session, language_id: uuid.UUID, level: int) -> Module:
    """Get (or create) the Module at position=level for a language."""
    m = db.execute(
        select(Module).where(Module.language_id == language_id, Module.position == level)
    ).scalar_one_or_none()
    if m is None:
        m = Module(language_id=language_id, position=level, title=f"Level {level}",
                   status=ContentStatus.draft)
        db.add(m)
        db.flush()
    return m


def _level_of(db: Session, module_id: uuid.UUID) -> int:
    return db.execute(select(Module.position).where(Module.id == module_id)).scalar_one()


def _vocab_dict(db: Session, v: VocabularyItem) -> dict:
    return {
        "id": str(v.id), "kind": "vocabulary", "term": v.term,
        "translation": v.primary_translation, "part_of_speech": v.part_of_speech,
        "meaning": v.meaning, "level": _level_of(db, v.module_id),
        "batch": getattr(v, "batch", 1),
        "article": getattr(v.article, "value", v.article),
        "gender": getattr(v.grammatical_gender, "value", v.grammatical_gender),
        "status": v.status.value, "archived": v.deleted_at is not None,
    }


def _grammar_dict(db: Session, g: GrammarPoint) -> dict:
    return {
        "id": str(g.id), "kind": "grammar", "term": g.title,
        "translation": g.translation, "structure_pattern": g.structure_pattern,
        "part_of_speech": g.part_of_speech, "meaning": g.meaning,
        "level": _level_of(db, g.module_id),
        "status": g.status.value, "archived": g.deleted_at is not None,
    }


# --- request bodies ---------------------------------------------------------

class VocabCreate(BaseModel):
    term: str = Field(min_length=1, max_length=120)
    translation: str = Field(default="", max_length=200)
    level: int = Field(ge=1, le=200)
    batch: int = Field(default=1, ge=1, le=4)
    part_of_speech: str = Field(default="", max_length=40)
    meaning: str = Field(default="", max_length=4000)
    pronunciation: str = Field(default="", max_length=120)
    ipa: str = Field(default="", max_length=120)
    article: str = Field(default="none", max_length=8)
    gender: str = Field(default="none", max_length=12)
    synonyms: list[str] = Field(default_factory=list)
    variations: list[str] = Field(default_factory=list)
    castilian_variant: str = Field(default="", max_length=200)


class VocabUpdate(BaseModel):
    term: str | None = Field(default=None, max_length=120)
    translation: str | None = Field(default=None, max_length=200)
    part_of_speech: str | None = Field(default=None, max_length=40)
    meaning: str | None = Field(default=None, max_length=4000)
    pronunciation: str | None = Field(default=None, max_length=120)
    ipa: str | None = Field(default=None, max_length=120)
    article: str | None = Field(default=None, max_length=8)
    gender: str | None = Field(default=None, max_length=12)
    synonyms: list[str] | None = None
    variations: list[str] | None = None
    castilian_variant: str | None = Field(default=None, max_length=200)


class GrammarCreate(BaseModel):
    term: str = Field(min_length=1, max_length=200)  # the grammar title
    translation: str = Field(default="", max_length=200)
    structure_pattern: str = Field(default="", max_length=300)
    part_of_speech: str = Field(default="", max_length=40)
    meaning: str = Field(default="", max_length=4000)
    level: int = Field(ge=1, le=200)


class GrammarUpdate(BaseModel):
    term: str | None = Field(default=None, max_length=200)
    translation: str | None = Field(default=None, max_length=200)
    structure_pattern: str | None = Field(default=None, max_length=300)
    part_of_speech: str | None = Field(default=None, max_length=40)
    meaning: str | None = Field(default=None, max_length=4000)


class VocabMove(BaseModel):
    level: int = Field(ge=1, le=200)
    batch: int = Field(default=1, ge=1, le=4)


class GrammarMove(BaseModel):
    level: int = Field(ge=1, le=200)


# --- editor list (includes batch + archived; separate from the summary list) --

@router.get("/content/vocabulary/editor")
def editor_list_vocab(
    level: int | None = None, include_archived: bool = False,
    limit: int = 200, offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_edit)),
):
    limit = max(1, min(limit, 500))
    q = select(VocabularyItem, Module.position).join(Module, VocabularyItem.module_id == Module.id)
    if level is not None:
        q = q.where(Module.position == level)
    if not include_archived:
        q = q.where(VocabularyItem.deleted_at.is_(None))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(
        q.order_by(Module.position, VocabularyItem.term).limit(limit).offset(offset)
    ).all()
    return {"items": [_vocab_dict(db, v) for v, _pos in rows], "total": total}


@router.get("/content/grammar/editor")
def editor_list_grammar(
    level: int | None = None, include_archived: bool = False,
    limit: int = 200, offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require(Capability.content_edit)),
):
    limit = max(1, min(limit, 500))
    q = select(GrammarPoint, Module.position).join(Module, GrammarPoint.module_id == Module.id)
    if level is not None:
        q = q.where(Module.position == level)
    if not include_archived:
        q = q.where(GrammarPoint.deleted_at.is_(None))
    total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
    rows = db.execute(
        q.order_by(Module.position, GrammarPoint.title).limit(limit).offset(offset)
    ).all()
    return {"items": [_grammar_dict(db, g) for g, _pos in rows], "total": total}


# --- vocabulary CRUD --------------------------------------------------------

@router.post("/content/vocabulary", status_code=201)
def create_vocab_item(
    body: VocabCreate,
    language: str = "es-MX",
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    try:
        term = validate_term(body.term)
        validate_level(body.level)
        validate_batch(body.batch)
        article, gender = normalize_article_gender(body.part_of_speech, body.article, body.gender)
    except EditError as e:
        raise _edit_http(e)
    lang = _language(db, language)
    module = _module_for_level39(db, lang.id, body.level)
    v = VocabularyItem(
        language_id=lang.id, module_id=module.id, status=ContentStatus.draft,
        term=term, normalized_term=_normalize_term39(term),
        primary_translation=body.translation, part_of_speech=body.part_of_speech,
        meaning=body.meaning, pronunciation=body.pronunciation, ipa=body.ipa,
        synonyms=body.synonyms, variations=body.variations,
        castilian_variant=body.castilian_variant, batch=body.batch,
        article=article, grammatical_gender=gender,
    )
    db.add(v)
    db.flush()
    _audit(db, actor, "create", "vocabulary_items", v.id, after=_vocab_dict(db, v))
    db.commit()
    return _vocab_dict(db, v)


@router.patch("/content/vocabulary/{item_id}")
def update_vocab_item(
    body: VocabUpdate, item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    v = db.get(VocabularyItem, _uuid39(item_id))
    if v is None or v.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    before = _vocab_dict(db, v)
    try:
        if body.term is not None:
            v.term = validate_term(body.term)
            v.normalized_term = _normalize_term39(v.term)
        if body.translation is not None:
            v.primary_translation = body.translation
        if body.part_of_speech is not None:
            v.part_of_speech = body.part_of_speech
        if body.meaning is not None:
            v.meaning = body.meaning
        if body.pronunciation is not None:
            v.pronunciation = body.pronunciation
        if body.ipa is not None:
            v.ipa = body.ipa
        if body.synonyms is not None:
            v.synonyms = body.synonyms
        if body.variations is not None:
            v.variations = body.variations
        if body.castilian_variant is not None:
            v.castilian_variant = body.castilian_variant
        # Recompute article/gender against the (possibly new) part of speech.
        art_in = body.article if body.article is not None else getattr(v.article, "value", v.article)
        gen_in = body.gender if body.gender is not None else getattr(
            v.grammatical_gender, "value", v.grammatical_gender)
        article, gender = normalize_article_gender(v.part_of_speech, art_in, gen_in)
        v.article = article
        v.grammatical_gender = gender
    except EditError as e:
        raise _edit_http(e)
    db.flush()
    _audit(db, actor, "update", "vocabulary_items", v.id, before=before, after=_vocab_dict(db, v))
    db.commit()
    return _vocab_dict(db, v)


@router.post("/content/vocabulary/{item_id}/move")
def move_vocab_item(
    body: VocabMove, item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    v = db.get(VocabularyItem, _uuid39(item_id))
    if v is None or v.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    try:
        validate_level(body.level)
        validate_batch(body.batch)
    except EditError as e:
        raise _edit_http(e)
    before = _vocab_dict(db, v)
    module = _module_for_level39(db, v.language_id, body.level)
    v.module_id = module.id
    v.batch = body.batch
    db.flush()
    _audit(db, actor, "move", "vocabulary_items", v.id, before=before, after=_vocab_dict(db, v))
    db.commit()
    return _vocab_dict(db, v)


@router.delete("/content/vocabulary/{item_id}", status_code=200)
def soft_delete_vocab_item(
    item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    v = db.get(VocabularyItem, _uuid39(item_id))
    if v is None or v.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    before = _vocab_dict(db, v)
    v.deleted_at = _now39()
    v.status = ContentStatus.archived
    db.flush()
    _audit(db, actor, "soft_delete", "vocabulary_items", v.id, before=before)
    db.commit()
    return {"id": str(v.id), "archived": True}


@router.post("/content/vocabulary/{item_id}/restore")
def restore_vocab_item(
    item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    v = db.get(VocabularyItem, _uuid39(item_id))
    if v is None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    v.deleted_at = None
    v.status = ContentStatus.draft
    db.flush()
    _audit(db, actor, "restore", "vocabulary_items", v.id, after=_vocab_dict(db, v))
    db.commit()
    return _vocab_dict(db, v)


# --- grammar CRUD -----------------------------------------------------------

@router.post("/content/grammar", status_code=201)
def create_grammar_item(
    body: GrammarCreate,
    language: str = "es-MX",
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    try:
        title = validate_term(body.term)
        validate_level(body.level)
    except EditError as e:
        raise _edit_http(e)
    lang = _language(db, language)
    module = _module_for_level39(db, lang.id, body.level)
    g = GrammarPoint(
        language_id=lang.id, module_id=module.id, status=ContentStatus.draft,
        title=title, translation=body.translation,
        structure_pattern=body.structure_pattern, part_of_speech=body.part_of_speech,
        meaning=body.meaning,
    )
    db.add(g)
    db.flush()
    _audit(db, actor, "create", "grammar_points", g.id, after=_grammar_dict(db, g))
    db.commit()
    return _grammar_dict(db, g)


@router.patch("/content/grammar/{item_id}")
def update_grammar_item(
    body: GrammarUpdate, item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    g = db.get(GrammarPoint, _uuid39(item_id))
    if g is None or g.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    before = _grammar_dict(db, g)
    try:
        if body.term is not None:
            g.title = validate_term(body.term)
    except EditError as e:
        raise _edit_http(e)
    if body.translation is not None:
        g.translation = body.translation
    if body.structure_pattern is not None:
        g.structure_pattern = body.structure_pattern
    if body.part_of_speech is not None:
        g.part_of_speech = body.part_of_speech
    if body.meaning is not None:
        g.meaning = body.meaning
    db.flush()
    _audit(db, actor, "update", "grammar_points", g.id, before=before, after=_grammar_dict(db, g))
    db.commit()
    return _grammar_dict(db, g)


@router.post("/content/grammar/{item_id}/move")
def move_grammar_item(
    body: GrammarMove, item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_edit)),
):
    g = db.get(GrammarPoint, _uuid39(item_id))
    if g is None or g.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    try:
        validate_level(body.level)
    except EditError as e:
        raise _edit_http(e)
    before = _grammar_dict(db, g)
    module = _module_for_level39(db, g.language_id, body.level)
    g.module_id = module.id
    db.flush()
    _audit(db, actor, "move", "grammar_points", g.id, before=before, after=_grammar_dict(db, g))
    db.commit()
    return _grammar_dict(db, g)


@router.delete("/content/grammar/{item_id}", status_code=200)
def soft_delete_grammar_item(
    item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    g = db.get(GrammarPoint, _uuid39(item_id))
    if g is None or g.deleted_at is not None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    before = _grammar_dict(db, g)
    g.deleted_at = _now39()
    g.status = ContentStatus.archived
    db.flush()
    _audit(db, actor, "soft_delete", "grammar_points", g.id, before=before)
    db.commit()
    return {"id": str(g.id), "archived": True}


@router.post("/content/grammar/{item_id}/restore")
def restore_grammar_item(
    item_id: str,
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_archive)),
):
    g = db.get(GrammarPoint, _uuid39(item_id))
    if g is None:
        raise HTTPException(status_code=404, detail={
            "error": {"code": "not_found", "message": "Item not found."}})
    g.deleted_at = None
    g.status = ContentStatus.draft
    db.flush()
    _audit(db, actor, "restore", "grammar_points", g.id, after=_grammar_dict(db, g))
    db.commit()
    return _grammar_dict(db, g)
# === end slice 39 ===========================================================

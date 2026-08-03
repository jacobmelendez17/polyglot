"""Admin routes: curriculum import, content management, users.

Every route is capability-gated (PLANNING §4) and every mutation writes an
admin_audit_log row in the same transaction (§22). Nothing here is reachable by
a normal user.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
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


def _spanish(db: Session) -> Language:
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    if lang is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": {"code": "no_language", "message": "Spanish language not seeded."}},
        )
    return lang


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
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_import)),
) -> ImportResult:
    text = await _read_csv(file)
    import_id = uuid.uuid4()
    lang = _spanish(db)
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
    db: Session = Depends(get_db),
    actor: User = Depends(require(Capability.content_import)),
) -> ImportResult:
    text = await _read_csv(file)
    import_id = uuid.uuid4()
    lang = _spanish(db)
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

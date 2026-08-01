"""Reading resource service (spec §7).

Reader side: list published texts, open one (gated by the visibility rule), look up
a tapped word against the vocabulary table, and manage the learner's own private
annotations (highlight + note). Annotation offsets are validated against the
server's copy of the body and the quote is sliced server-side — the client never
declares what a highlight contains.

Admin side: create / update / set-status for texts, each writing an
admin_audit_log row in the same transaction (§22).
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import reading as rules
from app.models.curriculum import Language, VocabularyItem
from app.models.platform import AdminAuditLog
from app.models.reading import ReadingAnnotation, ReadingText

PUBLISHED = "published"
VALID_STATUS = ("draft", "in_review", "published", "archived")
VALID_SOURCE = ("original", "external")


class ReadingError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError):
        raise ReadingError("Not found.", "not_found", 404) from None


def _language(db: Session, code: str) -> Language | None:
    return db.execute(select(Language).where(Language.code == code)).scalar_one_or_none()


def _summary_of(text: ReadingText) -> str:
    return text.summary or rules.excerpt(text.body)


# --- reader ----------------------------------------------------------------

def list_texts(db: Session, *, language_code: str = "es-MX",
               level: int | None = None, limit: int = 50) -> list[dict]:
    lang = _language(db, language_code)
    if lang is None:
        return []
    q = select(ReadingText).where(
        ReadingText.language_id == lang.id,
        ReadingText.status == PUBLISHED,
        ReadingText.deleted_at.is_(None),
    )
    if level is not None:
        q = q.where(ReadingText.level == level)
    rows = db.execute(q.order_by(ReadingText.level, ReadingText.title).limit(limit)).scalars().all()
    return [{
        "id": str(t.id), "title": t.title, "author": t.author,
        "source_type": t.source_type, "level": t.level,
        "summary": _summary_of(t),
        "external_url": t.external_url if t.source_type == "external" else "",
    } for t in rows]


def get_text(db: Session, *, text_id: str, is_editor: bool = False) -> dict:
    text = db.get(ReadingText, _uuid(text_id))
    if text is None or not rules.can_view_text(
        status=text.status, deleted=text.deleted_at is not None, is_editor=is_editor,
    ):
        raise ReadingError("Not found.", "not_found", 404)
    return {
        "id": str(text.id), "title": text.title, "author": text.author,
        "source_type": text.source_type, "level": text.level,
        "body": text.body if text.source_type == "original" else "",
        "external_url": text.external_url, "summary": text.summary,
        "status": text.status,
    }


def lookup_word(db: Session, *, language_code: str, word: str) -> dict:
    normalized = rules.normalize_word(word)
    if not normalized:
        return {"word": word, "found": False}
    lang = _language(db, language_code)
    if lang is None:
        return {"word": word, "found": False}
    item = db.execute(
        select(VocabularyItem).where(
            VocabularyItem.language_id == lang.id,
            VocabularyItem.normalized_term == normalized,
            VocabularyItem.status == PUBLISHED,
            VocabularyItem.deleted_at.is_(None),
        ).limit(1)
    ).scalar_one_or_none()
    if item is None:
        return {"word": word, "found": False}
    return {
        "word": word, "found": True, "term": item.term,
        "translation": item.primary_translation,
        "part_of_speech": item.part_of_speech, "item_id": str(item.id),
    }


# --- annotations (private to the user) -------------------------------------

def list_annotations(db: Session, *, user_id: uuid.UUID, text_id: str) -> list[dict]:
    rows = db.execute(
        select(ReadingAnnotation).where(
            ReadingAnnotation.user_id == user_id,
            ReadingAnnotation.text_id == _uuid(text_id),
        ).order_by(ReadingAnnotation.start_offset)
    ).scalars().all()
    return [_annotation_dict(a) for a in rows]


def add_annotation(db: Session, *, user_id: uuid.UUID, text_id: str,
                   start: int, end: int, note: str) -> dict:
    text = db.get(ReadingText, _uuid(text_id))
    if text is None or text.status != PUBLISHED or text.deleted_at is not None:
        raise ReadingError("Not found.", "not_found", 404)
    if text.source_type != "original":
        raise ReadingError("External links can't be annotated.", "not_annotatable", 400)
    try:
        rules.validate_annotation(len(text.body or ""), start, end)
    except ValueError as e:
        raise ReadingError(str(e), "invalid_range", 422) from e
    quote = rules.extract_quote(text.body, start, end)
    ann = ReadingAnnotation(
        user_id=user_id, text_id=text.id, start_offset=start, end_offset=end,
        quote=quote, note=(note or "").strip()[:2000],
    )
    db.add(ann)
    db.flush()
    return _annotation_dict(ann)


def delete_annotation(db: Session, *, user_id: uuid.UUID, annotation_id: str) -> dict:
    ann = db.get(ReadingAnnotation, _uuid(annotation_id))
    if ann is None or ann.user_id != user_id:
        raise ReadingError("Not found.", "not_found", 404)
    db.delete(ann)
    db.flush()
    return {"id": str(annotation_id), "deleted": True}


def _annotation_dict(a: ReadingAnnotation) -> dict:
    return {"id": str(a.id), "start": a.start_offset, "end": a.end_offset,
            "quote": a.quote, "note": a.note}


# --- admin authoring (audit-logged) ----------------------------------------

def _audit(db: Session, actor_id: uuid.UUID, action: str,
           target_id: uuid.UUID | None, before=None, after=None) -> None:
    db.add(AdminAuditLog(
        actor_id=actor_id, action=action, target_table="reading_texts",
        target_id=target_id, before=before or {}, after=after or {},
    ))


def admin_list(db: Session, *, language_code: str = "es-MX", limit: int = 100) -> list[dict]:
    lang = _language(db, language_code)
    if lang is None:
        return []
    rows = db.execute(
        select(ReadingText).where(
            ReadingText.language_id == lang.id, ReadingText.deleted_at.is_(None),
        ).order_by(ReadingText.level, ReadingText.title).limit(limit)
    ).scalars().all()
    return [{
        "id": str(t.id), "title": t.title, "source_type": t.source_type,
        "level": t.level, "status": t.status,
    } for t in rows]


def create_text(db: Session, *, actor_id: uuid.UUID, language_code: str, title: str,
                source_type: str, body: str = "", external_url: str = "",
                author: str = "", summary: str = "", level: int = 1) -> dict:
    if source_type not in VALID_SOURCE:
        raise ReadingError("source_type must be 'original' or 'external'.", "invalid", 422)
    if source_type == "original" and not (body or "").strip():
        raise ReadingError("Original texts need a body.", "invalid", 422)
    if source_type == "external" and not (external_url or "").strip():
        raise ReadingError("External texts need a URL.", "invalid", 422)
    lang = _language(db, language_code)
    if lang is None:
        raise ReadingError("Language not found.", "no_language", 409)
    text = ReadingText(
        language_id=lang.id, title=(title or "").strip()[:300], author=author.strip()[:200],
        source_type=source_type, body=body or "", external_url=(external_url or "").strip()[:600],
        summary=(summary or "").strip(), level=int(level), status="draft",
    )
    db.add(text)
    db.flush()
    _audit(db, actor_id, "create_reading", text.id, after={"title": text.title})
    return {"id": str(text.id), "status": text.status}


def update_text(db: Session, *, actor_id: uuid.UUID, text_id: str, **fields) -> dict:
    text = db.get(ReadingText, _uuid(text_id))
    if text is None:
        raise ReadingError("Not found.", "not_found", 404)
    before = {"title": text.title, "level": text.level}
    for key in ("title", "author", "body", "external_url", "summary"):
        if key in fields and fields[key] is not None:
            setattr(text, key, fields[key])
    if fields.get("level") is not None:
        text.level = int(fields["level"])
    db.flush()
    _audit(db, actor_id, "update_reading", text.id, before=before,
           after={"title": text.title, "level": text.level})
    return {"id": str(text.id), "status": text.status}


def set_status(db: Session, *, actor_id: uuid.UUID, text_id: str, status: str) -> dict:
    if status not in VALID_STATUS:
        raise ReadingError("Invalid status.", "invalid", 422)
    text = db.get(ReadingText, _uuid(text_id))
    if text is None:
        raise ReadingError("Not found.", "not_found", 404)
    before = text.status
    text.status = status
    if status == "archived":
        text.deleted_at = _now()
    db.flush()
    _audit(db, actor_id, "set_reading_status", text.id,
           before={"status": before}, after={"status": status})
    return {"id": str(text.id), "status": status}

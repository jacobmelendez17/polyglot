"""Active-language service (spec §1, multilingual-ready schema).

The schema has always carried `language_id` on every piece of content; what was
missing was a runtime notion of *which* language a given learner is studying. This
service is that single source of truth. `get_active` resolves the learner's choice
(their profile's `active_language_code`) to a `Language` row, falling back safely
so a request never dies just because a preference is unset or points at a language
that's since been disabled. `set_active` only accepts a language that's actually
enabled. Everything that used to hardcode "es-MX" can now ask here instead.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.curriculum import Language
from app.models.identity import Profile

DEFAULT_CODE = "es-MX"


class LanguageError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message, self.code, self.status = message, code, status


def list_enabled(db: Session) -> list[Language]:
    return db.execute(
        select(Language).where(Language.enabled.is_(True)).order_by(Language.name)
    ).scalars().all()


def _by_code(db: Session, code: str, *, enabled_only: bool = True) -> Language | None:
    q = select(Language).where(Language.code == code)
    if enabled_only:
        q = q.where(Language.enabled.is_(True))
    return db.execute(q).scalar_one_or_none()


def get_active(db: Session, *, user_id: uuid.UUID) -> Language | None:
    """The learner's active language, resolved defensively.

    Preference → default (es-MX) → any enabled language. Returns None only when no
    language is enabled at all (a fresh, unseeded database).
    """
    profile = db.get(Profile, user_id)
    code = (profile.active_language_code if profile else None) or DEFAULT_CODE
    lang = _by_code(db, code)
    if lang is not None:
        return lang
    lang = _by_code(db, DEFAULT_CODE)
    if lang is not None:
        return lang
    return db.execute(
        select(Language).where(Language.enabled.is_(True)).order_by(Language.name).limit(1)
    ).scalar_one_or_none()


def set_active(db: Session, *, user_id: uuid.UUID, code: str) -> Language:
    """Point the learner at an enabled language. Rejects unknown/disabled codes."""
    lang = _by_code(db, code)
    if lang is None:
        raise LanguageError("That language isn't available.", "unknown_language", 422)
    profile = db.get(Profile, user_id)
    if profile is None:
        raise LanguageError("Profile not found.", "no_profile", 404)
    profile.active_language_code = lang.code
    db.flush()
    return lang


def as_dict(lang: Language) -> dict:
    return {"code": lang.code, "name": lang.name,
            "native_name": lang.native_name or lang.name}

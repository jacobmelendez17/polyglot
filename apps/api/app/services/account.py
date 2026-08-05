"""Account service (spec §16, §20): user settings + profile.

Settings and profile both get-or-create their row, validate input server-side, and
never let a client write server-controlled fields (xp, points, rank). Settings
validation (including the immersion gate) lives in the pure `domain.settings`.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.domain.settings import SettingsError, validate_settings_patch
from app.models.enums import CurriculumMode
from app.models.identity import Profile, User, UserSettings

# Fields serialized back to the client (everything editable, in a stable shape).
_SETTINGS_FIELDS = [
    "theme", "font_size", "color_theme", "lesson_batch_size", "review_order",
    "curriculum_mode", "back_to_back", "back_to_back_order", "show_srs_indicator",
    "leech_threshold", "review_batch_enabled", "review_batch_size",
    "reveal_full_answer", "allow_cheating", "allow_skipping", "undo_enabled",
    "accept_user_synonyms", "intermissions_enabled", "immersion_mode", "dialect",
    "audio_autoplay", "audio_voice", "audio_rate",
]


def _get_or_create_settings(db: Session, user_id: uuid.UUID) -> UserSettings:
    row = db.get(UserSettings, user_id)
    if row is None:
        row = UserSettings(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def _serialize_settings(row: UserSettings, *, immersion_unlocked: bool) -> dict:
    out: dict = {}
    for f in _SETTINGS_FIELDS:
        val = getattr(row, f)
        if f == "curriculum_mode" and val is not None:
            val = val.value if hasattr(val, "value") else val
        elif f in ("leech_threshold", "audio_rate") and val is not None:
            val = float(val)
        out[f] = val
    out["immersion_unlocked"] = immersion_unlocked  # so the UI can gate the toggle
    return out


def get_settings(db: Session, user_id: uuid.UUID) -> dict:
    row = _get_or_create_settings(db, user_id)
    profile = db.get(Profile, user_id)
    unlocked = bool(profile and profile.immersion_unlocked_at)
    return _serialize_settings(row, immersion_unlocked=unlocked)


def update_settings(db: Session, user_id: uuid.UUID, patch: dict) -> dict:
    profile = db.get(Profile, user_id)
    unlocked = bool(profile and profile.immersion_unlocked_at)
    clean = validate_settings_patch(patch, immersion_unlocked=unlocked)  # raises SettingsError
    row = _get_or_create_settings(db, user_id)
    for key, value in clean.items():
        if key == "curriculum_mode":
            value = CurriculumMode(value)
        setattr(row, key, value)
    db.flush()
    return _serialize_settings(row, immersion_unlocked=unlocked)


# --- profile ---------------------------------------------------------------

def get_profile(db: Session, user: User) -> dict:
    p = db.get(Profile, user.id)
    if p is None:
        p = Profile(user_id=user.id, display_name=user.email.split("@")[0])
        db.add(p)
        db.flush()
    return {
        "display_name": p.display_name or "",
        "bio": p.bio or "",
        "timezone": p.timezone or "UTC",
        "email": user.email,
        "role": user.role.value,
        # read-only stats (server-controlled)
        "xp_total": int(p.xp_total or 0),
        "points_balance": int(p.points_balance or 0),
        "rank_level": int(getattr(p, "rank_level", 1) or 1),
        "streak_current": int(p.streak_current or 0),
        "streak_best": int(p.streak_best or 0),
        "immersion_unlocked": bool(p.immersion_unlocked_at),
    }


def update_profile(db: Session, user: User, *, display_name: str | None = None,
                   bio: str | None = None, timezone: str | None = None) -> dict:
    p = db.get(Profile, user.id)
    if p is None:
        p = Profile(user_id=user.id)
        db.add(p)
        db.flush()
    if display_name is not None:
        p.display_name = display_name.strip()[:120]
    if bio is not None:
        p.bio = bio.strip()[:500]
    if timezone is not None:
        p.timezone = timezone.strip()[:64]
    db.flush()
    return get_profile(db, user)


__all__ = ["get_settings", "update_settings", "get_profile", "update_profile", "SettingsError"]

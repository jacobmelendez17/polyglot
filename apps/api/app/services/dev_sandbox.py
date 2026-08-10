"""Admin dev sandbox (troubleshooting practices and reviews).

Everything here is gated on the `dev_panel` capability and does nothing for a
normal account. It exists so an admin can exercise the real review and practice
engines without living through real SRS intervals or grinding a curriculum up
from zero.

Three tools:

  * **time scale** — multiply SRS intervals so a week becomes 30 seconds
    (domain/dev_mode.py). Stored on the admin's settings; read per request.
  * **unlock everything** — seed the admin's progress so every published item is
    learned, which makes every practice type immediately available (practice
    draws only from learned items).
  * **make reviews due now** — pull every scheduled review's next_review_at back
    to now, so you don't have to wait even the scaled interval to see the queue.

None of this touches another user. It's scoped to the caller's own rows.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.domain import dev_mode as dev_rules
from app.models.curriculum import GrammarPoint, Language, Module, VocabularyItem
from app.models.enums import ItemType
from app.models.identity import Profile, UserSettings
from app.models.progress import UserItemProgress


class DevError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _settings(db: Session, user_id: uuid.UUID) -> UserSettings:
    row = db.get(UserSettings, user_id)
    if row is None:
        row = UserSettings(user_id=user_id)
        db.add(row)
        db.flush()
    return row


def dev_state(db: Session, *, user_id: uuid.UUID) -> dict:
    s = _settings(db, user_id)
    scale = dev_rules.clamp_scale(getattr(s, "dev_srs_scale", 1.0))
    return {
        "dev_mode": bool(getattr(s, "dev_mode", False)),
        "srs_scale": scale,
        "srs_scale_description": dev_rules.describe_scale(scale),
        "presets": dev_rules.SCALE_PRESETS,
    }


def set_dev_mode(
    db: Session, *, user_id: uuid.UUID, enabled: bool,
    scale: str | float | None = None,
) -> dict:
    s = _settings(db, user_id)
    s.dev_mode = bool(enabled)
    if scale is not None:
        s.dev_srs_scale = dev_rules.resolve_scale(scale)
    elif enabled and dev_rules.clamp_scale(s.dev_srs_scale) >= 1.0:
        # Turning dev mode on with no scale yet? Default to the fast preset so it
        # actually does something visible.
        s.dev_srs_scale = dev_rules.SCALE_PRESETS["fast"]
    db.flush()
    return dev_state(db, user_id=user_id)


def active_scale(db: Session, *, user_id: uuid.UUID) -> float:
    """The SRS multiplier to apply for this user right now.

    1.0 (no scaling) unless dev mode is on. This is the one value the reviews
    service reads, so dev mode changes nothing else about the code path.
    """
    s = db.get(UserSettings, user_id)
    if s is None or not getattr(s, "dev_mode", False):
        return 1.0
    return dev_rules.clamp_scale(getattr(s, "dev_srs_scale", 1.0))


# --- sandbox actions ------------------------------------------------------

def _spanish(db: Session) -> Language | None:
    return db.execute(
        select(Language).where(Language.code == "es-MX")
    ).scalar_one_or_none()


def unlock_all(
    db: Session, *, user_id: uuid.UUID, up_to_level: int | None = None,
    now: dt.datetime | None = None,
) -> dict:
    """Mark every published item learned, so every practice type has material.

    Idempotent: an item that's already unlocked is left where it is (we don't
    reset a stage you were testing). Optionally bounded to a level.
    """
    now = now or _now()
    lang = _spanish(db)
    if lang is None:
        raise DevError("No language seeded.", "no_language", 400)

    module_q = select(Module).where(Module.language_id == lang.id)
    if up_to_level is not None:
        module_q = module_q.where(Module.position <= up_to_level)
    module_ids = [m.id for m in db.execute(module_q).scalars().all()]
    if not module_ids:
        return {"unlocked": 0}

    created = 0
    for item_type, model in (("vocabulary", VocabularyItem), ("grammar", GrammarPoint)):
        rows = db.execute(
            select(model.id).where(
                model.module_id.in_(module_ids),
                model.status == ContentStatus.published,
                model.deleted_at.is_(None),
            )
        ).scalars().all()
        existing = {
            p.item_id for p in db.execute(
                select(UserItemProgress).where(
                    UserItemProgress.user_id == user_id,
                    UserItemProgress.item_type == ItemType(item_type),
                )
            ).scalars().all()
        }
        for item_id in rows:
            if item_id in existing:
                continue
            db.add(UserItemProgress(
                user_id=user_id, item_type=ItemType(item_type), item_id=item_id,
                srs_stage=1, next_review_at=now, lesson_completed_at=now,
            ))
            created += 1
    db.flush()
    return {"unlocked": created}


def make_reviews_due(
    db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None,
) -> dict:
    """Pull every scheduled review back to now, so the queue is full immediately."""
    now = now or _now()
    result = db.execute(
        update(UserItemProgress)
        .where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.next_review_at.isnot(None),
            UserItemProgress.next_review_at > now,
        )
        .values(next_review_at=now)
    )
    db.flush()
    return {"made_due": int(result.rowcount or 0)}


def replay_onboarding(db: Session, *, user_id: uuid.UUID) -> dict:
    """Clear the onboarding stamp only — narrower than `reset_progress`.

    Unlike a full progress reset, this touches nothing else: SRS progress, XP,
    streaks, active language, and curriculum_mode all stay exactly as they are.
    It exists so you can re-see the slides (and, now that language/curriculum
    picking sit right after them, those two screens as well) without also
    wiping a sandbox account you've already set up for testing something else.
    """
    profile = db.get(Profile, user_id)
    if profile is not None:
        profile.onboarding_completed_at = None
    db.flush()
    return {"replayed": profile is not None}


def set_stage(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str, stage: int,
    now: dt.datetime | None = None,
) -> dict:
    """Force one item to a specific SRS stage, for testing a stage transition
    without climbing there."""
    now = now or _now()
    if stage < 1 or stage > 9:
        raise DevError("Stage must be 1..9.", "invalid_stage", 400)
    try:
        pk = uuid.UUID(item_id)
    except (ValueError, AttributeError) as e:
        raise DevError("Bad item id.", "invalid_item", 400) from e

    row = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.item_type == ItemType(item_type),
            UserItemProgress.item_id == pk,
        )
    ).scalar_one_or_none()
    if row is None:
        raise DevError("Item not unlocked for this user.", "not_unlocked", 404)
    row.srs_stage = stage
    row.next_review_at = now
    db.flush()
    return {"item_id": item_id, "srs_stage": stage}

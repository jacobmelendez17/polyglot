"""Reset-a-user's-progress, for the admin dev sandbox (your request).

This wipes the caller's *learning* progress so you can watch a fresh account
from scratch — and, crucially, clears the onboarding stamp so the intro slides
show again on your next sign-in. It's scoped to the caller only and gated on the
`dev_panel` capability by the route.

What it clears: SRS item progress, review sessions/answers/history, practice
sessions, the XP ledger, and intermission view records; and it zeroes the
profile's XP/points/rank/current-streak and nulls `onboarding_completed_at`.

What it deliberately keeps: journal entries (your writing), forum posts, feedback
tickets, subscription, settings, and widget layout — none of that is "learning
progress", and losing your journal to a progress reset would be a nasty surprise.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.identity import Profile

log = logging.getLogger(__name__)


def _delete_user_rows(db: Session, model_path: str, class_name: str,
                      user_id: uuid.UUID) -> int:
    """Delete a user's rows from one table, tolerating a model that may not
    exist in a given build. Returns the row count deleted (best effort)."""
    try:
        module = __import__(model_path, fromlist=[class_name])
        model = getattr(module, class_name)
    except (ImportError, AttributeError):
        return 0
    try:
        result = db.execute(delete(model).where(model.user_id == user_id))
        return int(result.rowcount or 0)
    except Exception:  # pragma: no cover - a table without user_id, etc.
        log.info("reset.skip_table", extra={"model": class_name})
        return 0


# (module_path, ClassName) for every table that holds learning progress.
_PROGRESS_MODELS = [
    ("app.models.progress", "ReviewAnswer"),
    ("app.models.progress", "ReviewSession"),
    ("app.models.progress", "SrsReview"),
    ("app.models.progress", "PracticeSession"),
    ("app.models.progress", "XpEvent"),
    ("app.models.progress", "UserItemProgress"),
    ("app.models.platform", "UserIntermissionView"),
]


def reset_progress(
    db: Session, *, user_id: uuid.UUID, now: dt.datetime | None = None,
) -> dict:
    now = now or dt.datetime.now(tz=dt.timezone.utc)
    deleted: dict[str, int] = {}

    for module_path, class_name in _PROGRESS_MODELS:
        deleted[class_name] = _delete_user_rows(db, module_path, class_name, user_id)

    # Zero the profile's progress counters and clear the onboarding stamp.
    profile = db.get(Profile, user_id)
    if profile is not None:
        profile.xp_total = 0
        profile.points_balance = 0
        profile.rank_level = 1
        profile.streak_current = 0
        # onboarding shows again on next sign-in
        profile.onboarding_completed_at = None

    db.flush()
    return {
        "reset": True,
        "onboarding_will_show_on_next_sign_in": True,
        "deleted": deleted,
    }

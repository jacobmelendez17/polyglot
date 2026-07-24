"""Dashboard layout persistence and guided-tour state.

The layout rules live in `domain/widgets.py`; this module only reads and writes.
Every read goes through `normalize`, so a row written by an older client — or by
hand — still produces a dashboard we can render.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import widgets as widget_rules
from app.models.platform import UserWidgetLayout
from app.models.tours import UserTourState

# Tours have to be declared here rather than accepted from the client, so a
# crafted key can't fill the table with junk rows.
KNOWN_TOURS: frozenset[str] = frozenset({"dashboard"})

MAX_TOUR_STEPS = 20


class DashboardError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.isoformat()


# --- layout ---------------------------------------------------------------

def get_layout(db: Session, *, user_id: uuid.UUID) -> widget_rules.Layout:
    row = db.get(UserWidgetLayout, user_id)
    if row is None or not row.layout:
        return widget_rules.default_layout()
    return widget_rules.normalize(row.layout)


def save_layout(
    db: Session, *, user_id: uuid.UUID, raw: object,
) -> widget_rules.Layout:
    """Normalize first, then store. What comes back from a PUT is what was
    written, not what was sent — so the client's next render matches the server."""
    layout = widget_rules.normalize(raw)
    row = db.get(UserWidgetLayout, user_id)
    if row is None:
        row = UserWidgetLayout(user_id=user_id, layout=layout.to_dict())
        db.add(row)
    else:
        row.layout = layout.to_dict()
    db.flush()
    return layout


def reset_layout(db: Session, *, user_id: uuid.UUID) -> widget_rules.Layout:
    layout = widget_rules.default_layout()
    row = db.get(UserWidgetLayout, user_id)
    if row is None:
        db.add(UserWidgetLayout(user_id=user_id, layout=layout.to_dict()))
    else:
        row.layout = layout.to_dict()
    db.flush()
    return layout


def dashboard_view(db: Session, *, user_id: uuid.UUID) -> dict:
    layout = get_layout(db, user_id=user_id)
    return {
        "layout": layout.to_dict(),
        "catalog": widget_rules.catalog_dicts(),
        "grid_columns": widget_rules.GRID_COLUMNS,
        "max_widgets": widget_rules.MAX_WIDGETS,
    }


# --- tours ----------------------------------------------------------------

def _tour_row(
    db: Session, *, user_id: uuid.UUID, tour_key: str, create: bool = False,
) -> UserTourState | None:
    if tour_key not in KNOWN_TOURS:
        raise DashboardError("Unknown tour.", "not_found", 404)
    row = db.execute(
        select(UserTourState).where(
            UserTourState.user_id == user_id,
            UserTourState.tour_key == tour_key,
        )
    ).scalar_one_or_none()
    if row is None and create:
        row = UserTourState(user_id=user_id, tour_key=tour_key, step_index=0,
                            skipped=False)
        db.add(row)
        db.flush()
    return row


def tour_state(db: Session, *, user_id: uuid.UUID, tour_key: str) -> dict:
    row = _tour_row(db, user_id=user_id, tour_key=tour_key)
    if row is None:
        return {"tour_key": tour_key, "step_index": 0, "completed": False,
                "skipped": False, "completed_at": None}
    return {
        "tour_key": tour_key,
        "step_index": int(row.step_index or 0),
        "completed": row.completed_at is not None,
        "skipped": bool(row.skipped),
        "completed_at": _iso(row.completed_at),
    }


def record_step(
    db: Session, *, user_id: uuid.UUID, tour_key: str, step_index: int,
) -> dict:
    """Remember where the learner is, so a refresh resumes rather than restarts.

    The step only moves forward: an out-of-order request from a stale tab can't
    drag someone back to step one.
    """
    if step_index < 0 or step_index > MAX_TOUR_STEPS:
        raise DashboardError("Step out of range.", "invalid", 400)
    row = _tour_row(db, user_id=user_id, tour_key=tour_key, create=True)
    assert row is not None
    row.step_index = max(int(row.step_index or 0), step_index)
    db.flush()
    return tour_state(db, user_id=user_id, tour_key=tour_key)


def complete_tour(
    db: Session, *, user_id: uuid.UUID, tour_key: str, skipped: bool = False,
    now: dt.datetime | None = None,
) -> dict:
    now = now or _now()
    row = _tour_row(db, user_id=user_id, tour_key=tour_key, create=True)
    assert row is not None
    if row.completed_at is None:
        row.completed_at = now
        row.skipped = bool(skipped)
    db.flush()
    return tour_state(db, user_id=user_id, tour_key=tour_key)


def restart_tour(db: Session, *, user_id: uuid.UUID, tour_key: str) -> dict:
    """Explicit replay. The tour never auto-restarts once finished; this only
    runs when the learner asks for it from the dashboard."""
    row = _tour_row(db, user_id=user_id, tour_key=tour_key, create=True)
    assert row is not None
    row.completed_at = None
    row.skipped = False
    row.step_index = 0
    db.flush()
    return tour_state(db, user_id=user_id, tour_key=tour_key)

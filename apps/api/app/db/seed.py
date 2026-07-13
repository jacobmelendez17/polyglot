"""Seed data for local/dev/test — CLEARLY MARKED demo data (Definition of Done).

Creates:
  - the owner/admin user + profile + settings (from env, no hardcoded prod secrets)
  - the two starter languages (Spanish es-MX, Tagalog tl) with stage names
  - the dashboard widget catalog (default + optional) per PLANNING §15

This does NOT import the CSV curriculum; that runs through the importer
(admin-triggered) so the report is captured. Run: python -m app.db.seed
"""
from __future__ import annotations

import os
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.curriculum import Language
from app.models.enums import UserRole
from app.models.identity import Profile, User, UserSettings
from app.models.platform import DashboardWidget

# Practice-stage names per language (PLANNING §10: \"Stage Uno\" .. \"Stage Cinco\").
SPANISH_STAGES = ["Uno", "Dos", "Tres", "Cuatro", "Cinco"]
TAGALOG_STAGES = ["Isa", "Dalawa", "Tatlo", "Apat", "Lima"]

WIDGETS: list[tuple[str, str, bool]] = [
    ("progression", "Progression Card", True),
    ("journey", "Journey Card", True),
    ("line_chart", "Line Chart", True),
    ("forecast", "Forecast", True),
    ("lesson", "Lesson Card", True),
    ("reviews", "Reviews Card", True),
    ("streak", "Streak Card", True),
    ("weak_items", "Weak Item Practice", True),
    ("intermission", "Intermission Card", True),
    ("practice_pins", "Practice Link Pins", False),
    ("heat_map", "Heat Map", False),
    ("total_days", "Total Days Studied", False),
    ("leech", "Leech Practice Card", False),
    ("skill_balance", "Skill Balance Card", False),
]


def seed(db: Session) -> None:
    _seed_languages(db)
    _seed_widgets(db)
    _seed_owner(db)
    db.commit()


def _seed_languages(db: Session) -> None:
    wanted = [
        ("es-MX", "Spanish (Latin American)", "Español", SPANISH_STAGES),
        ("tl", "Tagalog", "Tagalog", TAGALOG_STAGES),
    ]
    for code, name, native, stages in wanted:
        exists = db.execute(select(Language).where(Language.code == code)).scalar_one_or_none()
        if exists is None:
            db.add(Language(code=code, name=name, native_name=native, stage_names=stages))


def _seed_widgets(db: Session) -> None:
    for key, title, is_default in WIDGETS:
        exists = db.execute(
            select(DashboardWidget).where(DashboardWidget.key == key)
        ).scalar_one_or_none()
        if exists is None:
            db.add(DashboardWidget(key=key, title=title, is_default=is_default))


def _seed_owner(db: Session) -> None:
    email = os.environ.get("SEED_OWNER_EMAIL", "jacobmelen17@gmail.com")
    exists = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if exists is not None:
        return
    user = User(id=uuid.uuid4(), email=email, role=UserRole.owner)
    db.add(user)
    db.flush()
    db.add(Profile(user_id=user.id, display_name="Owner"))
    db.add(UserSettings(user_id=user.id))


if __name__ == "__main__":  # pragma: no cover
    with SessionLocal() as session:
        seed(session)
        print("Seed complete.")

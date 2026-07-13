"""Users, sessions, profile, settings."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Enum, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, TimestampMixin, fk, pk
from app.models.enums import (
    CurriculumMode,
    UserRole,
    UserStatus,
)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    auth_provider_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    email_verified_at: Mapped[datetime | None]
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.user)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.active
    )
    last_seen_at: Mapped[datetime | None]


class AuthSession(Base, TimestampMixin):
    """Server-side refresh sessions (rotation + reuse-detection revocation)."""

    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    rotated_from_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    xp_total: Mapped[int] = mapped_column(BigInteger, default=0)
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    rank_level: Mapped[int] = mapped_column(Integer, default=1)
    streak_current: Mapped[int] = mapped_column(Integer, default=0)
    streak_best: Mapped[int] = mapped_column(Integer, default=0)
    streak_type: Mapped[str] = mapped_column(String(30), default="any")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Mexico_City")
    onboarding_completed_at: Mapped[datetime | None]
    immersion_unlocked_at: Mapped[datetime | None]


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"
    user_id: Mapped[uuid.UUID] = fk("users.id", primary_key=True)
    theme: Mapped[str] = mapped_column(String(10), default="system")
    font_size: Mapped[str] = mapped_column(String(10), default="md")
    color_theme: Mapped[str] = mapped_column(String(30), default="terraza")
    lesson_batch_size: Mapped[int] = mapped_column(Integer, default=5)
    review_order: Mapped[str] = mapped_column(String(20), default="random")
    curriculum_mode: Mapped[CurriculumMode] = mapped_column(
        Enum(CurriculumMode, name="curriculum_mode"), default=CurriculumMode.default_dispersed
    )
    back_to_back: Mapped[bool] = mapped_column(Boolean, default=True)
    back_to_back_order: Mapped[str] = mapped_column(String(10), default="es_first")
    show_srs_indicator: Mapped[bool] = mapped_column(Boolean, default=True)
    leech_threshold: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0)
    review_batch_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    review_batch_size: Mapped[int] = mapped_column(Integer, default=20)
    reveal_full_answer: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_cheating: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_skipping: Mapped[bool] = mapped_column(Boolean, default=False)
    undo_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    accept_user_synonyms: Mapped[bool] = mapped_column(Boolean, default=False)
    intermissions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    immersion_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    dialect: Mapped[str] = mapped_column(String(20), default="latam_mx")

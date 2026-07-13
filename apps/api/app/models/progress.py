"""SRS progress, practice stages, sessions, answers, XP/points ledgers, journals.

user_item_progress is the SOURCE OF TRUTH for SRS stage, next review date,
unlocked/fluent/perfect status, mistake count, and leech score (PLANNING §23).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, TimestampMixin, fk, pk
from app.models.enums import ItemType, LeechState, PracticeCategory


class UserModuleState(Base, TimestampMixin):
    """Curriculum mode is locked when a user starts a level (PLANNING §5)."""

    __tablename__ = "user_module_state"
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_user_module"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = fk("modules.id", nullable=False, index=True)
    curriculum_mode_locked: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime | None]
    unlocked_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]


class UserItemProgress(Base, TimestampMixin):
    __tablename__ = "user_item_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_id", name="uq_user_item"),
        # Hot path: build the due-review queue.
        Index("ix_uip_due", "user_id", "next_review_at"),
    )
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    srs_stage: Mapped[int] = mapped_column(SmallInteger, default=1)   # 1..9
    next_review_at: Mapped[datetime | None]
    unlocked_at: Mapped[datetime | None]
    lesson_completed_at: Mapped[datetime | None]
    fluent_at: Mapped[datetime | None]
    perfect_at: Mapped[datetime | None]
    # Intra-review pair state: SRS applies only after both prompts answered.
    meaning_passed_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    reading_passed_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    total_incorrect: Mapped[int] = mapped_column(Integer, default=0)
    recent_results: Mapped[list] = mapped_column(JSON, default=list)  # ring buffer, last 10
    leech_score: Mapped[float] = mapped_column(Numeric(5, 3), default=0)
    leech_state: Mapped[LeechState] = mapped_column(
        Enum(LeechState, name="leech_state"), default=LeechState.none
    )


class UserItemPracticeStage(Base, TimestampMixin):
    """Uno..Cinco progress per item per practice category (PLANNING §10)."""

    __tablename__ = "user_item_practice_stages"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "item_type", "item_id", "category", name="uq_user_item_practice"
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    category: Mapped[PracticeCategory] = mapped_column(
        Enum(PracticeCategory, name="practice_category")
    )
    stage: Mapped[int] = mapped_column(SmallInteger, default=0)   # 0..5
    stage_reached_at: Mapped[datetime | None]   # next stage available at +24h


class ReviewSession(Base, TimestampMixin):
    __tablename__ = "review_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="review")  # review|lesson_quiz|leech|weak
    state: Mapped[str] = mapped_column(String(12), default="active")  # active|completed|abandoned
    queue_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)  # resume after refresh
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]


class ReviewAnswer(Base, TimestampMixin):
    """Every submitted answer, with full override provenance (PLANNING §9, §23)."""

    __tablename__ = "review_answers"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_review_answer_idem"),)
    id: Mapped[uuid.UUID] = pk()
    session_id: Mapped[uuid.UUID] = fk("review_sessions.id", nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    prompt_direction: Mapped[str] = mapped_column(String(10))  # es_to_en | en_to_es
    prompt_kind: Mapped[str] = mapped_column(String(10))       # meaning | reading | cloze
    submitted_answer: Mapped[str] = mapped_column(Text, default="")
    normalized_answer: Mapped[str] = mapped_column(Text, default="")
    original_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    final_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    typo_forgiven: Mapped[bool] = mapped_column(Boolean, default=False)
    synonym_matched: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_flags: Mapped[list] = mapped_column(JSON, default=list)
    undo_used: Mapped[bool] = mapped_column(Boolean, default=False)
    undo_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    srs_stage_before: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    srs_stage_after: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pair_incomplete: Mapped[bool] = mapped_column(Boolean, default=False)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    answered_at: Mapped[datetime | None]


class SrsReview(Base, TimestampMixin):
    """One row per completed item-pair SRS transaction (audit of stage moves)."""

    __tablename__ = "srs_reviews"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    session_id: Mapped[uuid.UUID | None] = fk("review_sessions.id", nullable=True)
    stage_before: Mapped[int] = mapped_column(SmallInteger)
    stage_after: Mapped[int] = mapped_column(SmallInteger)
    wrong_answer_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    promoted: Mapped[bool] = mapped_column(Boolean, default=False)
    penalty_factor: Mapped[int] = mapped_column(SmallInteger, default=1)
    occurred_at: Mapped[datetime | None]


class PracticeSession(Base, TimestampMixin):
    __tablename__ = "practice_sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    practice_type: Mapped[str] = mapped_column(String(30))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(12), default="active")
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]


class JournalPrompt(Base, TimestampMixin):
    __tablename__ = "journal_prompts"
    __table_args__ = (UniqueConstraint("active_on", name="uq_prompt_active_on"),)
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="")
    text_target: Mapped[str] = mapped_column(Text, default="")
    active_on: Mapped[datetime | None]   # daily queue rotation


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    prompt_id: Mapped[uuid.UUID | None] = fk("journal_prompts.id", nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    body_draft: Mapped[str] = mapped_column(Text, default="")   # autosave, never lost
    archived_at: Mapped[datetime | None]
    visibility: Mapped[str] = mapped_column(String(12), default="private")


class XpEvent(Base, TimestampMixin):
    """Append-only XP ledger. Idempotency key prevents farming (PLANNING §12)."""

    __tablename__ = "xp_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_xp_idem"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_table: Mapped[str] = mapped_column(String(40), default="")
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)


class PointsEvent(Base, TimestampMixin):
    __tablename__ = "points_events"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_points_idem"),)
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_table: Mapped[str] = mapped_column(String(40), default="")
    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    idempotency_key: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)


class UserSynonym(Base, TimestampMixin):
    """User-added synonyms, counted correct only when the setting is enabled (§8)."""

    __tablename__ = "user_synonyms"
    __table_args__ = (
        UniqueConstraint("user_id", "item_type", "item_id", "normalized", name="uq_user_syn"),
    )
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    synonym: Mapped[str] = mapped_column(String(200))
    normalized: Mapped[str] = mapped_column(String(200))

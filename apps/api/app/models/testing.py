"""Testing-map models (spec §7).

`TestQuestion` is the question bank: a prompt (optional audio + a caption), a stem,
four options, and the correct index — which is PRIVATE and never serialized to a
learner. `map` is one of cefr/app/life; `app_level` gates app-map questions to what
the learner has reached; `band` groups cefr bands (A1..C2) or life scenarios.

`TestAttempt` is one run through a map: it stores the answered questions as a JSON
snapshot (so the results screen and XP idempotency don't need a second table) plus
the running score.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, TimestampMixin, fk, pk


class TestQuestion(Base, TimestampMixin):
    __tablename__ = "test_questions"
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    map: Mapped[str] = mapped_column(String(8), index=True)      # cefr | app | life
    band: Mapped[str] = mapped_column(String(40), default="")    # cefr band or life scenario
    app_level: Mapped[int] = mapped_column(Integer, default=1)   # app-map gating
    caption: Mapped[str] = mapped_column(Text, default="")       # shown with the audio
    stem: Mapped[str] = mapped_column(Text, default="")          # the question
    options: Mapped[list] = mapped_column(JSON, default=list)    # [{text, image_asset_id?}]
    correct_index: Mapped[int] = mapped_column(Integer, default=0)  # PRIVATE
    explanation: Mapped[str] = mapped_column(Text, default="")
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    deleted_at: Mapped[datetime | None]


class TestAttempt(Base, TimestampMixin):
    __tablename__ = "test_attempts"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    map: Mapped[str] = mapped_column(String(8))
    band: Mapped[str] = mapped_column(String(40), default="")
    state: Mapped[str] = mapped_column(String(12), default="active")  # active|completed
    question_ids: Mapped[list] = mapped_column(JSON, default=list)   # ordered snapshot
    answers: Mapped[list] = mapped_column(JSON, default=list)        # [{question_id, chosen, correct}]
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None]

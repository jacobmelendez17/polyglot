"""Reading resource models (spec §7).

`ReadingText` is a piece of reading material: an original text authored on the site
(with a `body`) or a curated external link (with an `external_url`). Status is a
plain string on the draft→published→archived path; `deleted_at` is the soft-delete
marker. `ReadingAnnotation` is a learner's private highlight-plus-note on a text —
character offsets into the body, with the quote extracted server-side.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, fk, pk


class ReadingText(Base, TimestampMixin):
    __tablename__ = "reading_texts"
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    author: Mapped[str] = mapped_column(String(200), default="")
    source_type: Mapped[str] = mapped_column(String(12), default="original")  # original|external
    body: Mapped[str] = mapped_column(Text, default="")                        # original texts
    external_url: Mapped[str] = mapped_column(String(600), default="")         # external links
    summary: Mapped[str] = mapped_column(Text, default="")
    level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    deleted_at: Mapped[datetime | None]


class ReadingAnnotation(Base, TimestampMixin):
    __tablename__ = "reading_annotations"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, index=True)
    text_id: Mapped[uuid.UUID] = fk("reading_texts.id", nullable=False, index=True)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text, default="")   # extracted server-side
    note: Mapped[str] = mapped_column(Text, default="")

"""Languages, modules(levels), lessons, vocab, grammar, sentences, audio, verbs."""
from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Enum,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import GUID, Base, ContentMixin, TimestampMixin, fk, pk
from app.models.enums import Article, Gender, ItemType, LessonKind


class Language(Base, TimestampMixin):
    __tablename__ = "languages"
    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)   # es-MX, tl, es-ES
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    native_name: Mapped[str] = mapped_column(String(60), default="")
    # practice-stage names per language, e.g. ["Uno","Dos","Tres","Cuatro","Cinco"]
    stage_names: Mapped[list] = mapped_column(JSON, default=list)


class Module(Base, ContentMixin):
    """Called a \"level\" in the UI (PLANNING: module == level)."""

    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("language_id", "position", name="uq_module_pos"),)
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")


class Lesson(Base, ContentMixin):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_lesson_pos"),)
    id: Mapped[uuid.UUID] = pk()
    module_id: Mapped[uuid.UUID] = fk("modules.id", nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)   # 1..5
    kind: Mapped[LessonKind] = mapped_column(Enum(LessonKind, name="lesson_kind"))
    theme_title: Mapped[str] = mapped_column(String(120), default="")


class LessonItem(Base, TimestampMixin):
    """Ordered placement of an item into a lesson, per curriculum mode."""

    __tablename__ = "lesson_items"
    __table_args__ = (
        UniqueConstraint("lesson_id", "curriculum_mode", "position", name="uq_lessonitem_pos"),
    )
    id: Mapped[uuid.UUID] = pk()
    lesson_id: Mapped[uuid.UUID] = fk("lessons.id", nullable=False, index=True)
    curriculum_mode: Mapped[str] = mapped_column(String(30), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type"))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)


class AudioAsset(Base, ContentMixin):
    __tablename__ = "audio_assets"
    id: Mapped[uuid.UUID] = pk()
    # {content_type}_{content_id}_{locale}_{voice_id}_{version}.{ext}
    storage_path: Mapped[str] = mapped_column(String(400), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(40))
    content_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    locale: Mapped[str] = mapped_column(String(10))
    voice_id: Mapped[str] = mapped_column(String(40), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[int | None]
    source: Mapped[str] = mapped_column(String(10), default="tts")   # tts | human


class VocabularyItem(Base, ContentMixin):
    __tablename__ = "vocabulary_items"
    __table_args__ = (
        # Enforce: only nouns may carry an article (PLANNING §6 important rule).
        CheckConstraint(
            "article = 'none' OR part_of_speech = 'noun'",
            name="ck_article_only_for_nouns",
        ),
    )
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = fk("modules.id", nullable=False, index=True)
    term: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    primary_translation: Mapped[str] = mapped_column(String(200), default="")
    part_of_speech: Mapped[str] = mapped_column(String(40), default="")
    difficulty_rank: Mapped[int] = mapped_column(Integer, default=0)
    pronunciation: Mapped[str] = mapped_column(String(120), default="")
    ipa: Mapped[str] = mapped_column(String(120), default="")
    meaning: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[list] = mapped_column(JSON, default=list)          # phrase-use groups
    grammatical_gender: Mapped[Gender] = mapped_column(
        Enum(Gender, name="gram_gender"), default=Gender.none
    )
    article: Mapped[Article] = mapped_column(Enum(Article, name="article"), default=Article.none)
    accepted_answers: Mapped[list] = mapped_column(JSON, default=list)   # PRIVATE
    rejected_answers: Mapped[list] = mapped_column(JSON, default=list)   # PRIVATE
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    variations: Mapped[list] = mapped_column(JSON, default=list)
    castilian_variant: Mapped[str] = mapped_column(String(200), default="")
    latam_variant: Mapped[str] = mapped_column(String(200), default="")
    audio_asset_id: Mapped[uuid.UUID | None] = fk("audio_assets.id", nullable=True)
    source_import_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class GrammarPoint(Base, ContentMixin):
    __tablename__ = "grammar_points"
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    module_id: Mapped[uuid.UUID] = fk("modules.id", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    translation: Mapped[str] = mapped_column(String(200), default="")
    structure_pattern: Mapped[str] = mapped_column(String(300), default="")
    part_of_speech: Mapped[str] = mapped_column(String(40), default="")
    meaning: Mapped[str] = mapped_column(Text, default="")
    explanation_rich: Mapped[str] = mapped_column(Text, default="")
    accepted_answers: Mapped[list] = mapped_column(JSON, default=list)
    rejected_answers: Mapped[list] = mapped_column(JSON, default=list)
    synonyms: Mapped[list] = mapped_column(JSON, default=list)
    unlocks: Mapped[dict] = mapped_column(JSON, default=dict)   # e.g. verb-conjugation gating
    audio_asset_id: Mapped[uuid.UUID | None] = fk("audio_assets.id", nullable=True)
    source_import_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class Sentence(Base, ContentMixin):
    """Admin-written only (never scraped). Reusable across items."""

    __tablename__ = "sentences"
    id: Mapped[uuid.UUID] = pk()
    language_id: Mapped[uuid.UUID] = fk("languages.id", nullable=False, index=True)
    text_es: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[str] = mapped_column(String(12), default="phrase")  # phrase|sentence|complex
    audio_asset_id: Mapped[uuid.UUID | None] = fk("audio_assets.id", nullable=True)


class SentenceLink(Base, TimestampMixin):
    __tablename__ = "sentence_links"
    id: Mapped[uuid.UUID] = pk()
    sentence_id: Mapped[uuid.UUID] = fk("sentences.id", nullable=False, index=True)
    item_type: Mapped[ItemType] = mapped_column(Enum(ItemType, name="item_type", create_type=False))
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="example")
    cloze_answer: Mapped[str | None] = mapped_column(String(200), nullable=True)


class VerbMeta(Base, TimestampMixin):
    __tablename__ = "verbs_meta"
    vocabulary_item_id: Mapped[uuid.UUID] = fk("vocabulary_items.id", primary_key=True)
    conjugation_class: Mapped[str] = mapped_column(String(10))   # ar|er|ir|irregular
    is_regular: Mapped[bool] = mapped_column(Boolean, default=True)
    conjugations: Mapped[dict] = mapped_column(JSON, default=dict)  # {tense: {person: form}}

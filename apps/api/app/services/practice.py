"""Practice service: build practice sessions, grade practice answers.

Practice draws from items the user has already learned (has a UserItemProgress
row). It awards XP and advances the practice-stage (Uno..Cinco) but does NOT
touch the SRS stage — practice is extra drilling, not scheduled review.
"""
from __future__ import annotations

import datetime as dt
import random
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import srs
from app.domain.answer_check import CheckMode, check_answer, expected_from_item
from app.domain.audio import StoredAsset, resolve_audio
from app.domain.practice import (
    PracticeCandidate,
    PracticeMode,
    advance_practice_stage,
    available_conjugation_cells,
    is_perfect,
    is_perfect_across,
    make_cloze,
    make_conjugation,
    select_practice_pool,
)
from app.domain.xp import XpKind, xp_for
from app.models.curriculum import (
    AudioAsset,
    Sentence,
    SentenceLink,
    VerbMeta,
    VocabularyItem,
)
from app.models.enums import ItemType, PracticeCategory
from app.models.identity import UserSettings
from app.models.progress import (
    PracticeSession,
    UserItemPracticeStage,
    UserItemProgress,
    XpEvent,
)


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


class PracticeError(Exception):
    """User-safe practice failure."""


@dataclass
class PracticePrompt:
    item_type: str
    item_id: str
    mode: str
    shown: str          # the sentence-with-blank, or the conjugation ask
    translation: str
    # conjugation extras
    tense: str | None = None
    person: str | None = None
    # how the client should produce sound for this prompt (None = silent)
    audio: dict | None = None


@dataclass
class PracticeGrade:
    correct: bool
    expected: str
    warnings: list[str]
    xp_awarded: int
    practice_stage: int | None = None
    perfect: bool = False
    # True only the moment ALL shipped practice categories reach Cinco AND the
    # item's SRS side is Fluent — distinct from `perfect`, which just means
    # THIS category is maxed (and stays true on every later correct answer).
    perfect_overall: bool = False


def _candidates(db: Session, user_id: uuid.UUID) -> list[PracticeCandidate]:
    rows = db.execute(
        select(UserItemProgress).where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.lesson_completed_at.is_not(None),
        )
    ).scalars().all()
    out: list[PracticeCandidate] = []
    for p in rows:
        is_verb = False
        has_example = False
        if p.item_type is ItemType.vocabulary:
            v = db.get(VocabularyItem, p.item_id)
            if v is not None:
                is_verb = (v.part_of_speech or "").lower() in ("verb", "verbo")
                has_example = bool(
                    db.execute(
                        select(SentenceLink.id).where(
                            SentenceLink.item_type == ItemType.vocabulary,
                            SentenceLink.item_id == v.id,
                        ).limit(1)
                    ).scalar_one_or_none()
                )
        out.append(PracticeCandidate(
            item_type=p.item_type.value, item_id=str(p.item_id),
            srs_stage=p.srs_stage, leech_score=float(p.leech_score or 0),
            total_incorrect=p.total_incorrect or 0,
            has_example=has_example, is_verb=is_verb,
        ))
    return out


def _audio_for(db: Session, text: str, *, content_id, content_type: str = "vocabulary") -> dict:
    """Stored recording if one exists for this item, else browser speech."""
    asset_row = db.execute(
        select(AudioAsset).where(
            AudioAsset.content_type == content_type,
            AudioAsset.content_id == content_id,
        ).limit(1)
    ).scalar_one_or_none()
    asset = None
    if asset_row is not None:
        asset = StoredAsset(
            storage_path=asset_row.storage_path, locale=asset_row.locale,
            voice_id=asset_row.voice_id, source=asset_row.source,
        )
    return resolve_audio(text, asset=asset).to_dict()


def build_practice(
    db: Session, user_id: uuid.UUID, *, mode: str, limit: int = 10, seed: int = 0,
) -> list[PracticePrompt]:
    try:
        pmode = PracticeMode(mode)
    except ValueError:
        raise PracticeError("unknown practice mode") from None

    pool = select_practice_pool(_candidates(db, user_id), pmode, limit=limit, seed=seed)
    rng = random.Random(seed)
    prompts: list[PracticePrompt] = []

    for c in pool:
        if pmode is PracticeMode.conjugation:
            vm = db.get(VerbMeta, uuid.UUID(c.item_id))
            v = db.get(VocabularyItem, uuid.UUID(c.item_id))
            if vm is None or v is None:
                continue
            cells = available_conjugation_cells(vm.conjugations)
            if not cells:
                continue
            tense, person = rng.choice(cells)
            cj = make_conjugation(v.term, vm.conjugations, tense=tense, person=person)
            if cj is None:
                continue
            prompts.append(PracticePrompt(
                item_type=c.item_type, item_id=c.item_id, mode=mode,
                shown=f"{cj.infinitive} — {tense}, {person}",
                translation=v.primary_translation, tense=tense, person=person,
            ))
        elif pmode is PracticeMode.listening:
            v = db.get(VocabularyItem, uuid.UUID(c.item_id))
            if v is None:
                continue
            # The word itself is never shown — that's the whole point.
            prompts.append(PracticePrompt(
                item_type=c.item_type, item_id=c.item_id, mode=mode,
                shown="", translation=v.primary_translation,
                audio=_audio_for(db, v.term, content_id=v.id),
            ))
        else:
            # fill_blank and weak_items both use a cloze when an example exists,
            # otherwise fall back to a plain translation prompt.
            v = (db.get(VocabularyItem, uuid.UUID(c.item_id))
                 if c.item_type == "vocabulary" else None)
            link = None
            sentence = None
            if v is not None:
                link = db.execute(
                    select(SentenceLink).where(
                        SentenceLink.item_type == ItemType.vocabulary,
                        SentenceLink.item_id == v.id,
                    ).limit(1)
                ).scalar_one_or_none()
                if link is not None:
                    sentence = db.get(Sentence, link.sentence_id)
            if v is not None and sentence is not None:
                # Prefer the curated cloze answer if the editor supplied one.
                target = link.cloze_answer or v.term
                cz = make_cloze(sentence.text_es, target, v.primary_translation)
                if cz is not None:
                    prompts.append(PracticePrompt(
                        item_type=c.item_type, item_id=c.item_id, mode=mode,
                        shown=cz.sentence_with_blank, translation=cz.translation,
                    ))
                    continue
            # fallback: translate the word
            if v is not None:
                prompts.append(PracticePrompt(
                    item_type=c.item_type, item_id=c.item_id, mode=mode,
                    shown=v.primary_translation, translation=v.term,
                ))
    return prompts


def start_practice(
    db: Session, user_id: uuid.UUID, *, mode: str, seed: int = 0,
    now: dt.datetime | None = None,
) -> tuple[PracticeSession, list[PracticePrompt]]:
    now = now or _now()
    prompts = build_practice(db, user_id, mode=mode, seed=seed)
    session = PracticeSession(
        user_id=user_id, practice_type=mode, state="active",
        detail={"count": len(prompts)}, started_at=now,
    )
    db.add(session)
    db.flush()
    return session, prompts


def _practice_category(mode: str) -> PracticeCategory:
    # Listening reps count toward the listening category; fill_blank / conjugation
    # / weak_items all live under the "sentences" family for the practice-stage
    # system (there's no dedicated mode for "speaking" yet — PLANNING R-13).
    if mode == PracticeMode.listening.value:
        return PracticeCategory.listening
    return PracticeCategory.sentences


def _derive_expected(db: Session, *, item_type: str, item_id: str, mode: str,
                     tense: str | None, person: str | None) -> str:
    """The server owns the correct answer — never the client. Recompute it from
    the item so a crafted request can't declare its own 'expected' value."""
    if item_type != "vocabulary":
        return ""
    v = db.get(VocabularyItem, uuid.UUID(item_id))
    if v is None:
        return ""
    if mode == "conjugation" and tense and person:
        vm = db.get(VerbMeta, uuid.UUID(item_id))
        cj = make_conjugation(v.term, vm.conjugations if vm else {},
                              tense=tense, person=person)
        return cj.answer if cj else v.term
    if mode == "listening":
        return v.term          # type what you heard, in Spanish
    if mode == "fill_blank":
        link = db.execute(
            select(SentenceLink).where(
                SentenceLink.item_type == ItemType.vocabulary,
                SentenceLink.item_id == v.id,
            ).limit(1)
        ).scalar_one_or_none()
        if link is not None and link.cloze_answer:
            return link.cloze_answer
        return v.term
    # weak_items fallback: translating the word
    return v.term


def grade_practice(
    db: Session, *, user_id: uuid.UUID, item_type: str, item_id: str,
    mode: str, submitted: str,
    tense: str | None = None, person: str | None = None,
    idempotency_key: uuid.UUID, now: dt.datetime | None = None,
) -> PracticeGrade:
    now = now or _now()

    expected_answer = _derive_expected(
        db, item_type=item_type, item_id=item_id, mode=mode, tense=tense, person=person,
    )

    prior = db.execute(
        select(XpEvent).where(XpEvent.idempotency_key == idempotency_key)
    ).scalar_one_or_none()
    if prior is not None:
        return PracticeGrade(correct=True, expected=expected_answer, warnings=[],
                             xp_awarded=0)   # already recorded

    settings = db.get(UserSettings, user_id)
    allow_cheating = bool(settings.allow_cheating) if settings else False
    expected = expected_from_item(primary=expected_answer)
    result = check_answer(submitted, expected, mode=CheckMode.practice,
                          allow_cheating=allow_cheating)

    # Advance practice stage (Uno..Cinco) for this item+category.
    category = _practice_category(mode)
    ps = db.execute(
        select(UserItemPracticeStage).where(
            UserItemPracticeStage.user_id == user_id,
            UserItemPracticeStage.item_type == ItemType(item_type),
            UserItemPracticeStage.item_id == uuid.UUID(item_id),
            UserItemPracticeStage.category == category,
        )
    ).scalar_one_or_none()
    if ps is None:
        ps = UserItemPracticeStage(
            user_id=user_id, item_type=ItemType(item_type),
            item_id=uuid.UUID(item_id), category=category, stage=0,
        )
        db.add(ps)
        db.flush()
    new_stage = advance_practice_stage(
        ps.stage, correct=result.correct,
        stage_reached_at=ps.stage_reached_at, now=now,
    )
    if new_stage != ps.stage:
        ps.stage = new_stage
        ps.stage_reached_at = now

    # XP only on a correct answer.
    amount = 0
    if result.correct:
        amount = xp_for(XpKind.test_correct)   # practice reuses the test-correct value
        db.add(XpEvent(
            user_id=user_id, amount=amount, kind="practice",
            source_table="practice_sessions", idempotency_key=idempotency_key,
        ))
    db.flush()

    # Overall "Perfect" status (PLANNING §10): every shipped practice category
    # at Cinco AND the item's SRS side Fluent. Checked here — the moment any
    # category's stage moves — rather than only from the review side, since
    # practice is what actually advances these stages.
    perfect_overall = False
    if result.correct:
        cat_rows = db.execute(
            select(UserItemPracticeStage).where(
                UserItemPracticeStage.user_id == user_id,
                UserItemPracticeStage.item_type == ItemType(item_type),
                UserItemPracticeStage.item_id == uuid.UUID(item_id),
            )
        ).scalars().all()
        stage_by_category = {r.category.value: r.stage for r in cat_rows}
        progress = db.execute(
            select(UserItemProgress).where(
                UserItemProgress.user_id == user_id,
                UserItemProgress.item_type == ItemType(item_type),
                UserItemProgress.item_id == uuid.UUID(item_id),
            )
        ).scalar_one_or_none()
        if (progress is not None and progress.perfect_at is None
                and srs.is_fluent(progress.srs_stage)
                and is_perfect_across(stage_by_category)):
            progress.perfect_at = now
            perfect_overall = True
    db.flush()

    return PracticeGrade(
        correct=result.correct, expected=expected_answer,
        warnings=result.warning_values, xp_awarded=amount,
        practice_stage=ps.stage, perfect=is_perfect(ps.stage),
        perfect_overall=perfect_overall,
    )


def complete_practice(db: Session, *, user_id: uuid.UUID, session_id: uuid.UUID,
                      now: dt.datetime | None = None) -> dict:
    now = now or _now()
    session = db.get(PracticeSession, session_id)
    if session is None or session.user_id != user_id:
        raise PracticeError("session not found")
    session.state = "completed"
    session.completed_at = now
    db.flush()
    return {"state": "completed"}

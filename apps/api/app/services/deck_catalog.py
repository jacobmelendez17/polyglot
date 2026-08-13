"""Deck catalog service (slice 43): unlock states + learner-built decks.

Builds the full deck list — always-on decks (with their live counts), the
threshold-gated decks with unlock progress, and the user's custom decks — and
handles custom-deck create/delete. Unlock thresholds and the catalog live in the
pure `domain.deck_unlock`; this layer only supplies the Familiar+ counts and
persistence.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.domain import deck_unlock
from app.models.curriculum import Language, VerbMeta, VocabularyItem
from app.models.enums import ItemType
from app.models.identity import User
from app.models.platform import CustomDeck
from app.models.progress import UserItemProgress
from app.services import decks as decks_svc

FAMILIAR_STAGE = deck_unlock.FAMILIAR_STAGE
MAX_NAME = 80
MAX_DESC = 500


class DeckCatalogError(Exception):
    def __init__(self, message: str, code: str = "error", status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def _now() -> dt.datetime:
    return dt.datetime.now(tz=dt.timezone.utc)


def _spanish(db: Session) -> Language | None:
    return db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()


def familiar_counts(db: Session, user_id: uuid.UUID, language_id: uuid.UUID) -> dict[str, int]:
    """Count the user's Familiar+ vocabulary by category (part of speech + verb
    regularity). Grammar isn't category-split here — the always-on grammar deck
    already covers it."""
    rows = db.execute(
        select(VocabularyItem.part_of_speech, VerbMeta.is_regular)
        .join(
            UserItemProgress,
            and_(
                UserItemProgress.item_id == VocabularyItem.id,
                UserItemProgress.item_type == ItemType.vocabulary,
            ),
        )
        .outerjoin(VerbMeta, VerbMeta.vocabulary_item_id == VocabularyItem.id)
        .where(
            UserItemProgress.user_id == user_id,
            UserItemProgress.srs_stage >= FAMILIAR_STAGE,
            VocabularyItem.language_id == language_id,
            VocabularyItem.deleted_at.is_(None),
        )
    ).all()

    counts: dict[str, int] = {}
    for pos, is_regular in rows:
        p = (pos or "").strip().lower()
        if p:
            counts[f"pos:{p}"] = counts.get(f"pos:{p}", 0) + 1
        if p == "verb" and is_regular is not None:
            key = "regularity:regular" if is_regular else "regularity:irregular"
            counts[key] = counts.get(key, 0) + 1
    return counts


def _custom_dict(c: CustomDeck) -> dict:
    refs = c.item_refs or []
    return {
        "id": f"custom:{c.id}", "title": c.name, "description": c.description or "",
        "glyph": "✎", "category": "", "threshold": 0, "have": len(refs), "need": 0,
        "unlocked": True, "custom": True, "count": len(refs),
    }


def list_all_decks(db: Session, user: User) -> list[dict]:
    """Always-on + threshold-gated + custom decks, with unlock state/progress."""
    lang = _spanish(db)
    counts = familiar_counts(db, user.id, lang.id) if lang else {}
    states = deck_unlock.evaluate(counts)

    # Live counts for the always-on decks come from the existing decks service.
    base = {d["type"]: d for d in decks_svc.list_decks(db, user_id=user.id)}

    out: list[dict] = []
    for st in states:
        entry = {
            "id": st.id, "title": st.title, "description": st.description, "glyph": st.glyph,
            "category": st.category, "threshold": st.threshold, "have": st.have,
            "need": st.need, "unlocked": st.unlocked, "custom": False,
        }
        if st.id in base:
            entry["count"] = base[st.id]["count"]
        out.append(entry)

    customs = db.execute(
        select(CustomDeck)
        .where(CustomDeck.user_id == user.id, CustomDeck.deleted_at.is_(None))
        .order_by(CustomDeck.created_at)
    ).scalars().all()
    out.extend(_custom_dict(c) for c in customs)
    return out


def create_custom_deck(db: Session, user: User, *, name: str, description: str = "") -> dict:
    clean = (name or "").strip()
    if not clean:
        raise DeckCatalogError("Give your deck a name.", "empty_name", 422)
    if len(clean) > MAX_NAME:
        raise DeckCatalogError(f"Name must be ≤ {MAX_NAME} characters.", "name_too_long", 422)
    deck = CustomDeck(
        user_id=user.id, name=clean, description=(description or "").strip()[:MAX_DESC],
        item_refs=[],
    )
    db.add(deck)
    db.flush()
    return _custom_dict(deck)


def _parse_custom_id(deck_id: str) -> uuid.UUID:
    raw = deck_id[len("custom:"):] if deck_id.startswith("custom:") else deck_id
    try:
        return uuid.UUID(raw)
    except (ValueError, AttributeError, TypeError):
        raise DeckCatalogError("Deck not found.", "not_found", 404) from None


def delete_custom_deck(db: Session, user: User, deck_id: str) -> dict:
    cid = _parse_custom_id(deck_id)
    deck = db.get(CustomDeck, cid)
    if deck is None or deck.user_id != user.id or deck.deleted_at is not None:
        raise DeckCatalogError("Deck not found.", "not_found", 404)
    deck.deleted_at = _now()
    db.flush()
    return {"id": f"custom:{deck.id}", "deleted": True}

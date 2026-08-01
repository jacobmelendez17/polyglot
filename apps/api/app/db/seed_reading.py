"""DEMO SEED — reading resource (spec §7).

Original, hand-written micro-texts so the reading library isn't empty in local
development. This is clearly-marked demo content, not production curriculum; the
strings below are original (per §6, nothing scraped from the web). Idempotent:
re-running skips texts whose titles already exist.

Run standalone:  python -m app.db.seed_reading
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.curriculum import Language
from app.models.reading import ReadingText

# --- DEMO DATA (original, hand-written; safe to delete) --------------------

_ORIGINAL = [
    {
        "title": "El gato y la luna",
        "author": "Polyglot (demo)",
        "level": 1,
        "summary": "Un gato mira la luna. Texto muy corto para empezar.",
        "body": (
            "El gato mira la luna.\n"
            "La luna es grande y blanca.\n"
            "El gato quiere la luna, pero la luna está muy lejos.\n"
            "El gato duerme y sueña con la luna."
        ),
    },
    {
        "title": "Un día en el mercado",
        "author": "Polyglot (demo)",
        "level": 2,
        "summary": "Ana va al mercado y compra frutas. Un texto sencillo para practicar.",
        "body": (
            "Ana va al mercado por la mañana.\n"
            "Compra manzanas, plátanos y un poco de pan.\n"
            "El vendedor es amable y le da una naranja gratis.\n"
            "Ana camina a casa contenta con su bolsa llena."
        ),
    },
]

_EXTERNAL = [
    {
        "title": "Cuentos cortos (enlace externo)",
        "author": "",
        "level": 3,
        "summary": "Ejemplo de recurso externo. Reemplázalo con enlaces reales desde el panel de administración.",
        "external_url": "https://example.com/cuentos",
    },
]


def seed_reading(db: Session) -> int:
    """Insert demo reading texts if missing. Returns the number created."""
    lang = db.execute(
        select(Language).where(Language.code == "es-MX")
    ).scalar_one_or_none()
    if lang is None:
        return 0

    existing = set(db.execute(select(ReadingText.title)).scalars().all())
    created = 0

    for t in _ORIGINAL:
        if t["title"] in existing:
            continue
        db.add(ReadingText(
            language_id=lang.id, title=t["title"], author=t["author"],
            source_type="original", body=t["body"], summary=t["summary"],
            level=t["level"], status="published",
        ))
        created += 1

    for t in _EXTERNAL:
        if t["title"] in existing:
            continue
        db.add(ReadingText(
            language_id=lang.id, title=t["title"], author=t["author"],
            source_type="external", external_url=t["external_url"],
            summary=t["summary"], level=t["level"], status="published",
        ))
        created += 1

    db.commit()
    return created


if __name__ == "__main__":  # pragma: no cover
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        n = seed_reading(session)
        print(f"seeded {n} demo reading text(s)")

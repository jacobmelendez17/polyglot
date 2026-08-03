"""DEMO SEED — testing maps (spec §7).

A few original, hand-written questions across the three maps so testing is
demoable in local dev. Clearly-marked demo content, not production. Idempotent:
skips questions whose stems already exist. Run: python -m app.db.seed_tests
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.curriculum import Language
from app.models.testing import TestQuestion

# (map, band, app_level, caption, stem, options, correct_index, explanation)
_QUESTIONS = [
    ("cefr", "A1", 1, "Hola, me llamo Ana.",
     "¿Cómo se llama ella?", ["Ana", "Juan", "Sofía", "Luis"], 0,
     "She says 'me llamo Ana' — 'my name is Ana'."),
    ("cefr", "A1", 1, "El gato está debajo de la mesa.",
     "¿Dónde está el gato?", ["Sobre la mesa", "Debajo de la mesa",
      "En la silla", "Fuera"], 1,
     "'debajo de' means 'under'."),
    ("app", "", 1, "Necesito ___ para beber.",
     "Choose the word that fits.", ["tubig", "agua", "pan", "libro"], 1,
     "'agua' = water; you drink water."),
    ("app", "", 1, "El plural de 'gato' es…",
     "Pick the correct plural.", ["gatos", "gata", "gatas", "gato"], 0,
     "Regular plural adds -s."),
    ("life", "restaurant", 1, "El mesero pregunta: «¿Qué desea tomar?»",
     "How do you order water?", ["Un café, por favor", "Agua, por favor",
      "La cuenta, por favor", "Nada, gracias"], 1,
     "'Agua, por favor' orders water."),
    ("life", "directions", 1, "Alguien pregunta cómo llegar al baño.",
     "Which reply gives a direction?", ["Está a la derecha", "Me llamo Ana",
      "Tengo hambre", "Es azul"], 0,
     "'a la derecha' = to the right."),
]


def seed_tests(db: Session) -> int:
    lang = db.execute(select(Language).where(Language.code == "es-MX")).scalar_one_or_none()
    if lang is None:
        return 0
    existing = set(db.execute(select(TestQuestion.stem)).scalars().all())
    created = 0
    for (m, band, level, caption, stem, options, correct, explanation) in _QUESTIONS:
        if stem in existing:
            continue
        db.add(TestQuestion(
            language_id=lang.id, map=m, band=band, app_level=level, caption=caption,
            stem=stem, options=[{"text": o} for o in options], correct_index=correct,
            explanation=explanation, status="published",
        ))
        created += 1
    db.commit()
    return created


if __name__ == "__main__":  # pragma: no cover
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        print(f"seeded {seed_tests(session)} demo test question(s)")

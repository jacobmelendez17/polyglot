"""SEED / DEMO DATA — the forum categories (spec §18).

The five categories the spec names: Grammar Help, Vocabulary, Speaking Practice,
Bug Reports, Feature Requests. Idempotent, matched on slug.

    docker compose exec api python -m app.db.seed_forums
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.forum import ForumCategory

# (slug, title, description, position, locked)
CATEGORIES: list[tuple[str, str, str, int, bool]] = [
    ("grammar-help", "Grammar Help",
     "Stuck on ser vs estar, the subjunctive, or where an accent goes? Ask here.",
     1, False),
    ("vocabulary", "Vocabulary",
     "Words, phrases, false friends, and the little differences that trip everyone up.",
     2, False),
    ("speaking-practice", "Speaking Practice",
     "Find a partner, share a recording, or ask how something is really said.",
     3, False),
    ("bug-reports", "Bug Reports",
     "Something broken or behaving oddly? Tell us what happened and how to repeat it.",
     4, False),
    ("feature-requests", "Feature Requests",
     "Ideas for what polyglot should do next. The most-wanted ones shape the roadmap.",
     5, False),
]


def seed_forums(db: Session) -> int:
    added = 0
    for slug, title, description, position, locked in CATEGORIES:
        exists = db.execute(
            select(ForumCategory).where(ForumCategory.slug == slug)
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(ForumCategory(
            slug=slug, title=title, description=description,
            position=position, locked=locked,
        ))
        added += 1
    db.commit()
    return added


if __name__ == "__main__":  # pragma: no cover
    with SessionLocal() as session:
        count = seed_forums(session)
        print(f"Forum categories seeded: {count} added ({len(CATEGORIES)} defined).")

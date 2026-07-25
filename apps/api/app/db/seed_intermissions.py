"""SEED / DEMO DATA — hand-written intermissions for the early levels.

All copy here is original, written for this app. Nothing is lifted from the web:
this is a paid product, and borrowed explanations are both a licensing problem
and a quality one (§6).

Idempotent — run it as often as you like:

    docker compose exec api python -m app.db.seed_intermissions
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import ContentStatus
from app.db.session import SessionLocal
from app.models.platform import Intermission

# (title, body, trigger)
#
# `trigger.category` is a display hint only — it tints the popup and groups the
# archive page. `order` breaks ties when two fire at once.
INTERMISSIONS: list[tuple[str, str, dict]] = [
    (
        "Why Spanish nouns have a gender",
        "Every Spanish noun is either masculine or feminine, and the article in "
        "front of it has to agree: **el libro**, **la mesa**. This isn't about "
        "the thing itself — a table isn't feminine in any meaningful sense. It's "
        "a grammatical category, the same way English marks plurals.\n\n"
        "The practical upshot: learn the article as part of the word. Not "
        "*mesa*, but *la mesa*. It costs nothing extra now and saves you "
        "re-learning several hundred words later.",
        {"kind": "level_start", "level": 1, "category": "rule", "order": 1},
    ),
    (
        "The five vowels never move",
        "Spanish vowels are steady in a way English ones aren't. **A** is always "
        "*ah*, **e** is always *eh*, **i** is *ee*, **o** is *oh*, **u** is *oo*. "
        "They don't drift depending on the letters around them.\n\n"
        "English speakers tend to soften unstressed vowels into a vague *uh* — "
        "the way the second syllable of *banana* collapses. Spanish doesn't do "
        "that. Give every vowel its full value and you will sound dramatically "
        "more comprehensible, even with a small vocabulary.",
        {"kind": "level_start", "level": 1, "category": "pronunciation", "order": 2},
    ),
    (
        "Mexico's ustedes",
        "You may have seen **vosotros** in a textbook. In Mexico — and across "
        "Latin America — it isn't used. The plural 'you' is **ustedes**, whether "
        "you're talking to your closest friends or a room of strangers.\n\n"
        "This app teaches Mexican Spanish, so **ustedes** is what you'll drill. "
        "You'll still recognise *vosotros* if you read Spanish literature or "
        "travel to Spain; you just won't need to produce it.",
        {"kind": "level_start", "level": 1, "category": "regional", "order": 3},
    ),
    (
        "Getting reviews wrong is the point",
        "It is tempting to treat a wrong answer as a failure. It isn't — it's the "
        "system finding the edge of what you know, which is the only place "
        "learning happens.\n\n"
        "An item you get wrong comes back sooner. An item you get right waits "
        "longer. If you were getting everything right, the intervals would be too "
        "short and you'd be wasting your time reviewing things you already know.",
        {"kind": "items_learned", "count": 10, "category": "tip", "order": 1},
    ),
    (
        "Ser and estar: permanent isn't quite right",
        "The usual shorthand is that **ser** is permanent and **estar** is "
        "temporary. It gets you surprisingly far and then quietly fails.\n\n"
        "A better frame: **ser** describes what something *is* — identity, "
        "origin, the category it belongs to. **estar** describes what state it's "
        "*in* — where it is, how it's doing, how it strikes you right now. "
        "*Es aburrido* means he is a boring person. *Está aburrido* means he is "
        "bored at the moment. Neither is more permanent; they're answering "
        "different questions.",
        {"kind": "items_learned", "count": 25, "category": "rule", "order": 2},
    ),
    (
        "Two ways to say 'you'",
        "**Tú** is informal, **usted** is formal. Mexican Spanish leans on this "
        "distinction more than most learners expect.\n\n"
        "The rough rule: **usted** for anyone older than you, anyone serving you "
        "in a professional capacity, and anyone you've just met in a formal "
        "setting. **tú** for friends, peers, and children. When you're unsure, "
        "start with **usted** — being slightly too formal is a smaller mistake "
        "than being too familiar, and people will often invite you to switch.",
        {"kind": "level_start", "level": 2, "category": "culture", "order": 1},
    ),
    (
        "The rolled r, and when it matters",
        "Spanish has two r sounds. A single **r** between vowels is a quick tap — "
        "close to the *dd* in the American English *ladder*. A double **rr**, or "
        "an **r** starting a word, is the trilled one.\n\n"
        "The difference carries meaning: **pero** (but) and **perro** (dog) are "
        "different words. If the trill won't come yet, don't stall on it — the "
        "tap is the more common sound, and the trill tends to arrive on its own "
        "after a few months of use.",
        {"kind": "items_learned", "count": 40, "category": "pronunciation", "order": 3},
    ),
    (
        "Why the intervals stretch out",
        "You have items reaching the Familiar stages now, which means you won't "
        "see them for a week, then two.\n\n"
        "That gap is doing the work. Recalling something just as it starts to "
        "fade strengthens the memory far more than reviewing it while it's still "
        "fresh. A long interval isn't the system neglecting an item — it's a "
        "prediction that you'll still have it, and a test of whether that "
        "prediction was right.",
        {"kind": "srs_stage", "stage": 5, "category": "tip", "order": 1},
    ),
    (
        "Diminutives are everywhere",
        "Mexican Spanish uses **-ito** and **-ita** constantly, and not only to "
        "mean 'small'. *Ahorita* is the famous one: literally 'right now-ish', "
        "in practice anywhere from this second to never.\n\n"
        "More often the ending softens a sentence or adds warmth. *Un momentito* "
        "isn't a shorter moment than *un momento* — it's a politer one. You don't "
        "need to produce these yet, but you'll hear them in almost every "
        "conversation.",
        {"kind": "level_start", "level": 3, "category": "culture", "order": 1},
    ),
    (
        "Questions turn upside down",
        "Spanish opens a question with **¿** and closes it with **?**. Same for "
        "exclamations: **¡** and **!**.\n\n"
        "It looks fussy until you read a long sentence aloud. The opening mark "
        "tells you a question is coming *before* you start, so you can pitch it "
        "correctly from the first word. English makes you guess and correct "
        "mid-sentence. This app accepts your answers without the opening marks, "
        "but you'll see them in every sentence we show you.",
        {"kind": "level_start", "level": 1, "category": "rule", "order": 4},
    ),
]


def seed_intermissions(db: Session, *, publish: bool = True) -> int:
    """Insert any intermission that isn't already there, matched on title."""
    added = 0
    for title, body, trigger in INTERMISSIONS:
        exists = db.execute(
            select(Intermission).where(Intermission.title == title)
        ).scalar_one_or_none()
        if exists is not None:
            continue
        db.add(Intermission(
            title=title, body_rich=body, trigger=trigger,
            status=ContentStatus.published if publish else ContentStatus.draft,
        ))
        added += 1
    db.commit()
    return added


if __name__ == "__main__":  # pragma: no cover
    with SessionLocal() as session:
        count = seed_intermissions(session)
        print(f"Intermissions seeded: {count} added "
              f"({len(INTERMISSIONS)} defined).")

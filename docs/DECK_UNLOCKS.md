# Deck unlocks — catalog & suggestions

A deck unlocks when enough items in a **category** reach **Familiar** (SRS stage ≥ 5).
Everything is data-driven from one place: the catalog in
`apps/api/app/domain/deck_unlock.py` (`BUILTIN_DECKS`). Add a `DeckDef(id, title,
description, glyph, category, threshold)` and the service counts + evaluates it —
no other code changes needed for pos/regularity-based decks.

Category keys the counter already produces:
- `""` — always unlocked (not gated)
- `pos:<part_of_speech>` — Familiar+ vocab of that part of speech (`pos:verb`, `pos:noun`, …)
- `regularity:regular` / `regularity:irregular` — Familiar+ verbs by regularity

## Shipping now (in the catalog)

| Deck | Category | Threshold |
|---|---|---|
| vocabulary | — | always |
| grammar | — | always |
| intermissions | — | always |
| verbs | `pos:verb` | 20 |
| irregular verbs | `regularity:irregular` | 5 |
| regular verbs | `regularity:regular` | 15 |
| nouns | `pos:noun` | 30 |
| adjectives | `pos:adjective` | 15 |
| adverbs | `pos:adverb` | 10 |

## Suggested additions (pick what you like)

**Part-of-speech decks** (already supported — just add a row):
- pronouns (`pos:pronoun`, ~10) · prepositions (`pos:preposition`, ~10) ·
  conjunctions (`pos:conjunction`, ~8) · interjections (`pos:interjection`, ~6) ·
  numbers (`pos:numeral`, ~10) · phrases (`pos:phrase`, ~15)

**Verb-class decks** (needs a small counter tweak to key off `VerbMeta.conjugation_class`):
- -ar verbs · -er verbs · -ir verbs (e.g. 10 each) — great for conjugation drilling.

**Theme / tag decks** (needs the counter to also tally `tag:<name>` from item tags):
- animals · food & kitchen · family · travel · body · colors · time & dates …
  Unlock at, say, 10–15 familiar words carrying that tag. This is the richest set
  and maps directly to your CSV `Tags` column.

**Level-milestone decks** (needs a `level:<n>` category from the item's module):
- "level 1 mastery", "level 5 mastery" — unlock when every item in a level is Familiar+.

**Progress-flavored decks** (needs their own signals, not category counts):
- **leeches** — items above your leech threshold (you already compute leech state).
- **perfect** — items that reached "perfect" status (all practice categories done).
- **almost fluent** — items at Advanced heading to Fluent.
- **due today** — everything due for review now (a live filter, not a threshold).

**Difficulty-tier decks** (from `difficulty_rank`):
- "the tricky 50" — your highest-difficulty familiar items.

## How to add one

1. Add a `DeckDef(...)` to `BUILTIN_DECKS`.
2. If it uses a new category kind (tag / level / verb-class), extend
   `familiar_counts()` in `services/deck_catalog.py` to emit that key.
3. Add a case to the catalog-items resolver when deck browsing lands (next slice).
4. Tune the threshold — they're named constants, easy to change.

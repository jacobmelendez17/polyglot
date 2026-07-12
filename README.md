# lengua ✦

A cozy, SRS-powered path to real Spanish fluency (Latin American / Mexican dialect first,
Tagalog next). Learn vocabulary and grammar through leveled lessons, keep them through
spaced-repetition reviews, and grow reading, writing, listening, and speaking skills
through practice that unlocks as you progress.

## Why it exists

Most apps either gamify without retention or drill without joy. Lengua pairs a serious
SRS engine (nine stages, Beginner 1 → Fluent) with a warm, journal-like interface —
the "Terraza" design language — so daily study feels like a ritual, not a chore.

## What is in the app

- **Levels** — 10 levels, each with 48 vocabulary words + 12 grammar points across
  5 lessons, with selectable curriculum modes (dispersed, grammar batch, or mixed).
- **Reviews** — paired Spanish→English / English→Spanish prompts; both must be right
  to advance an item. Forgiving, configurable answer checking with undo.
- **Practice** — sentence structure, verb conjugation, listening, reading/writing,
  journals, and CEFR-style testing, each with its own Uno→Cinco progress stages.
- **Progress** — XP, ranks, streaks, forecast, heat map, leech detection, and a
  side-scrolling journey map through Latin America.

## How to use it (local dev)

```bash
cp .env.example .env
docker compose up          # web http://localhost:3000 · api http://localhost:8000/healthz
```

Backend tests: `cd apps/api && pip install ".[dev]" && pytest`
Frontend checks: `cd apps/web && npm install && npm run lint && npm run typecheck`

## Repository layout

```
apps/web        Next.js (Cloudflare Pages) — UI, Auth.js, BFF proxy
apps/api        FastAPI (Fly.io) — SRS engine, answer checking, content, admin
packages/design-tokens   Terraza palette + type tokens (single source of truth)
docs/           PLANNING.md — architecture, schema, SRS spec, phases
```

## Status

Phase 1, slice 1a (scaffold, CI, health checks) — see `docs/PLANNING.md` for the full
phased roadmap, definition of done, and open decisions.

#!/usr/bin/env bash
set -e

echo "→ Waiting for database, then running migrations…"
alembic upgrade head

echo "→ Seeding baseline data (languages, widgets, owner)…"
python -m app.db.seed || echo "  (seed skipped or already present)"

echo "→ Starting API on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

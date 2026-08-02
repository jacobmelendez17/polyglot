"""Liveness + readiness probes (spec §27).

`/health/live` is a cheap "the process is up" check for orchestrators. `/health/ready`
additionally pings the database (SELECT 1) and reports whether Sentry is active, so a
load balancer only sends traffic once dependencies are actually reachable — a failed
DB ping returns 503, not 200.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)):
    import os
    checks = {"database": False}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001 - readiness must never raise
        checks["database"] = False

    ok = all(checks.values())
    body = {
        "status": "ready" if ok else "degraded",
        "checks": checks,
        "sentry": bool(os.getenv("SENTRY_DSN")),
    }
    return JSONResponse(status_code=200 if ok else 503, content=body)

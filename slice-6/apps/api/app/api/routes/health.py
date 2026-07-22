"""Liveness/readiness. Exposes no version or config detail (security checklist)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

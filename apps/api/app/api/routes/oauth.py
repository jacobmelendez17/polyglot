"""Social sign-in wiring (§20, by request).

Google / Discord / GitHub buttons need provider credentials (a client id/secret per
provider) that only exist in the deployment's environment. This router reports which
providers are configured so the UI can light up the right buttons, and exposes a
`/start` endpoint that will kick off the OAuth redirect once a provider adapter is
wired. Nothing here fabricates a login — an unconfigured provider is reported as such.

To enable a provider, set its client id/secret env vars (e.g. OAUTH_GOOGLE_CLIENT_ID
/ OAUTH_GOOGLE_CLIENT_SECRET) and register an adapter that performs the authorize
redirect + callback token exchange. See PLANNING (slice 30) for the full plan.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/auth/oauth", tags=["auth"])

PROVIDERS = ("google", "discord", "github")


def _configured(provider: str) -> bool:
    prefix = f"OAUTH_{provider.upper()}_"
    return bool(os.getenv(prefix + "CLIENT_ID") and os.getenv(prefix + "CLIENT_SECRET"))


class ProvidersResponse(BaseModel):
    providers: dict[str, bool]


@router.get("/providers", response_model=ProvidersResponse)
def list_providers() -> ProvidersResponse:
    """Which social providers are configured in this environment (all false until set)."""
    return ProvidersResponse(providers={p: _configured(p) for p in PROVIDERS})


@router.get("/{provider}/start")
def start(provider: str):
    """Begin the OAuth redirect for a provider. 404 for unknown providers; 501 until
    the provider's adapter (authorize redirect + callback) is wired."""
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404,
            detail={"error": {"code": "unknown_provider", "message": "Unknown provider."}})
    if not _configured(provider):
        raise HTTPException(status_code=503, detail={"error": {
            "code": "oauth_not_configured",
            "message": f"{provider} sign-in isn't set up yet.",
        }})
    # Configured but no adapter registered yet — implemented in the OAuth slice.
    raise HTTPException(status_code=501, detail={"error": {
        "code": "oauth_not_implemented",
        "message": f"{provider} sign-in is configured but not wired yet.",
    }})

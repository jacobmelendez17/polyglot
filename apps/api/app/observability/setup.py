"""One call wires all production-hardening concerns into the app (spec §25–§27).

`create_app()` calls `install_observability(app)`; everything here is additive and
safe to run with no extra configuration (Sentry stays off without a DSN, rate
limiting uses the in-memory backend, logging goes to stdout). Middleware is added
outermost-first: security headers wrap everything, then request-id logging, then the
rate limiter closest to the routes.
"""
from __future__ import annotations

from fastapi import FastAPI

from app.observability.health import router as health_router
from app.observability.logging import RequestContextMiddleware, configure_logging
from app.observability.ratelimit import RateLimitMiddleware
from app.observability.security import SecurityHeadersMiddleware
from app.observability.sentry import init_sentry


def install_observability(app: FastAPI) -> None:
    configure_logging()
    init_sentry()
    # add_middleware wraps last-added outermost, so add inner→outer:
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(health_router)

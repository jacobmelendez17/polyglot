"""Request-scoped logging (spec §27).

Assigns every request a stable id (honouring an inbound `X-Request-ID` from
Cloudflare or a load balancer, else generating one), echoes it on the response, and
logs one structured line per request with method, path, status, and duration. It
deliberately logs *only* that metadata — never bodies, tokens, or query strings —
so nothing sensitive lands in the logs (§25).
"""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("polyglot.request")


def configure_logging(level: str | None = None) -> None:
    import os
    lvl = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'))
        root.addHandler(handler)
    root.setLevel(getattr(logging, lvl, logging.INFO))


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception(
                "request_failed id=%s method=%s path=%s duration_ms=%.1f",
                request_id, request.method, request.url.path, duration_ms)
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id, request.method, request.url.path, response.status_code, duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response

"""Rate limiting (spec §25): a provider seam plus a per-client middleware.

The pure decision lives in `domain.ratelimit`; this module stores the timestamps
behind that decision. `InMemoryLimiter` is the default (fine for one process — beta/
single-node); `RedisLimiter` is the seam for Upstash Redis when you scale to several
workers (guarded import, so the app runs without the redis package). `get_limiter`
selects by `RATE_LIMIT_BACKEND` (default "memory").

`RateLimitMiddleware` applies a coarse per-IP limit across the whole API as a safety
net — enough to blunt abuse of auth, review submission, and form posts without
touching every router. Health checks are exempt so probes are never throttled. The
same limiter can be reused as a tighter per-route dependency later.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.domain.ratelimit import evaluate


class Limiter:
    """Backend interface: record a hit for `key` and return whether it's allowed."""

    def hit(self, key: str, *, limit: int, window: float,
            now: float | None = None) -> tuple[bool, float]:
        raise NotImplementedError


class InMemoryLimiter(Limiter):
    def __init__(self) -> None:
        self._store: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key, *, limit, window, now=None):
        now = time.time() if now is None else now
        with self._lock:
            d = evaluate(list(self._store[key]), now, limit=limit, window=window)
            self._store[key] = deque(d.kept)
            return d.allowed, d.retry_after


class RedisLimiter(Limiter):  # pragma: no cover - exercised only when redis is configured
    """Seam for Upstash/Redis. Not wired for the MVP; needs the redis package and
    a REDIS_URL. Kept import-guarded so its absence never breaks startup."""

    def __init__(self, url: str) -> None:
        try:
            import redis  # type: ignore
        except ImportError as e:  # noqa: BLE001
            raise RuntimeError("RATE_LIMIT_BACKEND=redis needs the `redis` package.") from e
        self._redis = redis.Redis.from_url(url)

    def hit(self, key, *, limit, window, now=None):
        now = time.time() if now is None else now
        member = f"{now}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - window)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, int(window) + 1)
        _, _, count, _ = pipe.execute()
        if count <= limit:
            return True, 0.0
        self._redis.zrem(key, member)
        return False, window


_limiter: Limiter | None = None


def get_limiter() -> Limiter:
    global _limiter
    if _limiter is not None:
        return _limiter
    backend = (os.getenv("RATE_LIMIT_BACKEND") or "memory").strip().lower()
    if backend == "redis" and os.getenv("REDIS_URL"):
        _limiter = RedisLimiter(os.environ["REDIS_URL"])
    else:
        _limiter = InMemoryLimiter()
    return _limiter


def reset_limiter() -> None:
    """Test hook — drop the process-wide limiter so each test starts clean."""
    global _limiter
    _limiter = None


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, limit: int | None = None, window: float | None = None,
                 exempt_prefixes: tuple[str, ...] = ("/health",)) -> None:
        super().__init__(app)
        self.limit = limit if limit is not None else int(os.getenv("RATE_LIMIT_MAX", "120"))
        self.window = window if window is not None else float(os.getenv("RATE_LIMIT_WINDOW", "60"))
        self.exempt_prefixes = exempt_prefixes

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.exempt_prefixes):
            return await call_next(request)
        allowed, retry = get_limiter().hit(
            f"ip:{_client_ip(request)}", limit=self.limit, window=self.window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "rate_limited",
                                   "message": "Too many requests — slow down a moment."}},
                headers={"Retry-After": str(int(retry) + 1)},
            )
        return await call_next(request)

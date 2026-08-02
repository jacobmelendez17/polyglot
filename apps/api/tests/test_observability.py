"""Observability wiring: request id, security headers, rate limiting, readiness."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.logging import RequestContextMiddleware
from app.observability.ratelimit import (
    InMemoryLimiter,
    RateLimitMiddleware,
    get_limiter,
    reset_limiter,
)
from app.observability.security import SecurityHeadersMiddleware


@pytest.fixture(autouse=True)
def _clean_limiter():
    reset_limiter()
    yield
    reset_limiter()


def _app(*, limit=1000):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit=limit, window=60)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    return app


def test_default_limiter_is_in_memory():
    assert isinstance(get_limiter(), InMemoryLimiter)


def test_request_id_is_generated_and_echoed():
    client = TestClient(_app())
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID")  # generated


def test_inbound_request_id_is_honoured():
    client = TestClient(_app())
    r = client.get("/ping", headers={"X-Request-ID": "abc123"})
    assert r.headers["X-Request-ID"] == "abc123"


def test_security_headers_present():
    r = TestClient(_app()).get("/ping")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in r.headers and "Permissions-Policy" in r.headers


def test_hsts_only_over_https():
    client = TestClient(_app())
    assert "Strict-Transport-Security" not in client.get("/ping").headers
    fwd = client.get("/ping", headers={"X-Forwarded-Proto": "https"})
    assert "Strict-Transport-Security" in fwd.headers


def test_rate_limit_blocks_after_the_cap():
    client = TestClient(_app(limit=3))
    for _ in range(3):
        assert client.get("/ping").status_code == 200
    blocked = client.get("/ping")
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_health_is_exempt_from_rate_limiting():
    client = TestClient(_app(limit=1))
    client.get("/ping")  # consume the only slot
    assert client.get("/ping").status_code == 429
    # health probes still pass no matter what
    for _ in range(5):
        assert client.get("/health/live").status_code == 200


def test_forwarded_ip_separates_clients():
    client = TestClient(_app(limit=1))
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # a different client IP has its own budget
    assert client.get("/ping", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
    # the first client is now over its cap
    assert client.get("/ping", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429

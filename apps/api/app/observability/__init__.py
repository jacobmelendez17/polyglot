"""Production-hardening wiring (spec §25, §26, §27): rate limiting, request-id
logging, security headers, an optional Sentry init, and a readiness check — all
installed with a single `install_observability(app)` call from `create_app`."""

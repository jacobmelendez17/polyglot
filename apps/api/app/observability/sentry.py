"""Optional error tracking (spec §27).

Sentry is initialised only when `SENTRY_DSN` is set *and* the `sentry_sdk` package
is installed. Both the import and the DSN check are guarded, so the app runs fine
with neither — error tracking is an add-on, never a startup dependency. Returns
True when Sentry was actually initialised (handy for tests and health output).
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger("polyglot.sentry")


def init_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False
    try:
        import sentry_sdk  # type: ignore
    except ImportError:  # pragma: no cover - depends on optional dependency
        logger.warning("SENTRY_DSN set but sentry_sdk isn't installed; skipping.")
        return False
    sentry_sdk.init(  # pragma: no cover - requires the real SDK + DSN
        dsn=dsn,
        environment=os.getenv("APP_ENV", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,  # never ship user PII to the tracker (§25)
    )
    return True

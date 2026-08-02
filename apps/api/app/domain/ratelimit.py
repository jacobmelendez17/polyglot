"""Rate limiting — the pure decision (spec §25).

`evaluate` is a sliding-window log: given the timestamps of a client's recent hits
and the current time, it decides whether one more is allowed, prunes anything older
than the window, and — when blocked — says how long until the window frees up. It
holds no state and does no I/O, so the limit/window behaviour is fully unit-testable
and identical no matter which backend (in-memory or Redis) stores the timestamps.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RateDecision:
    allowed: bool
    remaining: int           # requests still allowed in the current window
    retry_after: float       # seconds until the next request would be allowed (0 if allowed now)
    kept: list[float]        # pruned timestamps to persist (includes `now` when allowed)


def evaluate(recent: list[float], now: float, *, limit: int, window: float) -> RateDecision:
    """Decide whether a hit at `now` is allowed given prior hit timestamps.

    `recent` are epoch-seconds of earlier hits (any order). `limit` hits are allowed
    per rolling `window` seconds.
    """
    if limit <= 0:
        return RateDecision(False, 0, window, [])
    cutoff = now - window
    active = sorted(t for t in recent if t > cutoff)
    if len(active) < limit:
        return RateDecision(True, limit - len(active) - 1, 0.0, active + [now])
    # Blocked: the earliest active hit must age out of the window first.
    retry = (active[0] + window) - now
    return RateDecision(False, 0, max(retry, 0.0), active)

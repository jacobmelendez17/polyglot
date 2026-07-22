"""Leech detection (PLANNING §13) — pure functions.

    leech_score = recent_incorrect_weighted / recent_review_count

Only the most recent 10 reviews of an item count, and older mistakes decay
(linear weighting, newest heaviest). A pair answered wrong contributes 1.0;
each *extra* wrong answer in that pair adds 0.5, so a persistently-missed item
can exceed 1.0 and reach the Critical threshold (resolves PLANNING R-05).
"""
from __future__ import annotations

from enum import Enum

WINDOW = 10          # most recent N reviews matter
EXTRA_WRONG_WEIGHT = 0.5

WATCH_THRESHOLD = 0.8
DEFAULT_LEECH_THRESHOLD = 1.0   # user-configurable in settings
CRITICAL_THRESHOLD = 1.5


class LeechState(str, Enum):
    none = "none"
    watch = "watch"
    leech = "leech"
    critical = "critical"


def push_result(recent: list[int], wrong_answer_count: int) -> list[int]:
    """Append a review outcome to the ring buffer, keeping the last WINDOW.
    Stores the raw wrong-answer count per review."""
    out = [*recent, max(0, int(wrong_answer_count))]
    return out[-WINDOW:]


def _weights(n: int) -> list[float]:
    """Newest-heaviest linear decay: for n=10 -> [0.1 .. 1.0] oldest→newest."""
    if n <= 0:
        return []
    return [(i + 1) / n for i in range(n)]


def _wrong_weight(wrong_answer_count: int) -> float:
    if wrong_answer_count <= 0:
        return 0.0
    return 1.0 + EXTRA_WRONG_WEIGHT * (wrong_answer_count - 1)


def leech_score(recent: list[int]) -> float:
    """Weighted recent-incorrect rate. 0.0 when there is no history."""
    if not recent:
        return 0.0
    window = recent[-WINDOW:]
    w = _weights(len(window))
    numerator = sum(wt * _wrong_weight(r) for wt, r in zip(w, window, strict=False))
    denominator = sum(w)
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


def leech_state(score: float, *, threshold: float = DEFAULT_LEECH_THRESHOLD) -> LeechState:
    if score >= CRITICAL_THRESHOLD:
        return LeechState.critical
    if score >= threshold:
        return LeechState.leech
    if score >= WATCH_THRESHOLD:
        return LeechState.watch
    return LeechState.none


def is_leech(state: LeechState) -> bool:
    """Leech and Critical items get the shortened SRS interval."""
    return state in (LeechState.leech, LeechState.critical)

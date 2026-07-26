"""Dev-mode time scaling for SRS testing (admin sandbox).

The problem this solves: an SRS is, by design, slow. To watch an item climb from
Beginner 1 to Fluent you'd normally wait four hours, then eight, then a day, a
week, two weeks — months in total. That's correct for a learner and useless for
troubleshooting.

Dev mode multiplies every SRS interval by a small fraction so the whole ladder
plays out in minutes. A scale of 1/20160 turns one week (10080 minutes) into
exactly 30 seconds, which is the "30 seconds instead of a week" from the request.

This is deliberately just a multiplier on the existing intervals — not a second
scheduling path. The real logic stays the one code path, so the sandbox tests
the same engine a learner uses, only faster. Scale 1.0 (the default, and the
only value a non-admin can ever have) is a complete no-op.
"""
from __future__ import annotations

# One week is 10080 minutes. To make Familiar 1's one-week interval land at 30
# seconds, scale by 30 / 10080. Applied uniformly, every other interval shrinks
# in proportion: Beginner 1's 4h → ~0.7s, Advanced's 4mo → ~51s.
#
# Presented as a named preset so the guide and the API agree on one number.
WEEK_MINUTES = 7 * 24 * 60

# Preset scales, keyed by the name the API and the docs use.
SCALE_PRESETS: dict[str, float] = {
    "off": 1.0,
    # "fast": the headline preset — Familiar 1 (1 week) resolves in ~30 seconds.
    "fast": 30.0 / (WEEK_MINUTES * 60),
    # "instant": everything is due almost immediately (~1 second at Beginner 1),
    # for when you just want the item back now.
    "instant": 1.0 / (WEEK_MINUTES * 60),
}

DEFAULT_SCALE = 1.0
# Never let a scale be zero or negative — that would make next_review_at
# nonsensical (an item due before it was reviewed).
MIN_SCALE = 1e-9
MAX_SCALE = 1.0     # dev mode only ever speeds things up, never slows them down


def clamp_scale(scale: float | None) -> float:
    """A safe multiplier. Out-of-range or missing values fall back to no scaling."""
    if scale is None:
        return DEFAULT_SCALE
    try:
        value = float(scale)
    except (TypeError, ValueError):
        return DEFAULT_SCALE
    if value != value:      # NaN
        return DEFAULT_SCALE
    return max(MIN_SCALE, min(value, MAX_SCALE))


def resolve_scale(name_or_value: str | float | None) -> float:
    """Accept either a preset name ('fast') or a raw multiplier (0.001)."""
    if isinstance(name_or_value, str):
        key = name_or_value.strip().lower()
        if key in SCALE_PRESETS:
            return SCALE_PRESETS[key]
        try:
            return clamp_scale(float(key))
        except ValueError:
            return DEFAULT_SCALE
    return clamp_scale(name_or_value)


def describe_scale(scale: float) -> str:
    """Human-readable summary, for the dev panel."""
    if scale >= 1.0:
        return "off — real intervals (1 week = 1 week)"
    week_seconds = WEEK_MINUTES * 60 * scale
    if week_seconds < 90:
        return f"fast — 1 week ≈ {week_seconds:.0f}s"
    return f"scaled — 1 week ≈ {week_seconds / 60:.1f} min"

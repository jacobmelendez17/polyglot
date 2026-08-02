"""Entitlements — the pure paywall rule (spec §19).

Who can reach what. Level 1 is free for everyone; beyond level 1 needs an
entitlement. This is a pure, deterministic function of the learner's role and
subscription (tier + status) — no I/O, no Stripe — so the paywall boundary is
unit-testable and identical everywhere it's checked.

Access is granted to: staff roles (they run the place), beta testers (the free
perk, §19), a lifetime subscription that hasn't been revoked, and an active/trialing
paid subscription. During the beta the default tier is `free_beta`, which counts as
active access — so today nobody hits the wall; the wall is in place for when paid
tiers switch on and users land on the plain `free` tier.
"""
from __future__ import annotations

FREE_MAX_LEVEL = 1

STAFF_ROLES = frozenset({"moderator", "content_editor", "admin", "owner"})
BETA_ROLE = "beta_tester"

# Tiers that carry access while their status is active. Note `free` is absent — a
# plain free account only gets level 1.
ENTITLED_TIERS = frozenset({"free_beta", "lifetime", "monthly", "annual"})
ACTIVE_STATUSES = frozenset({"active", "trialing"})


def is_entitled(*, role: str, tier: str, status: str) -> bool:
    """True if this learner has full (paid-equivalent) access."""
    if role in STAFF_ROLES or role == BETA_ROLE:
        return True
    if tier == "lifetime" and status != "canceled":
        return True  # lifetime never expires
    return tier in ENTITLED_TIERS and status in ACTIVE_STATUSES


def can_access_level(level: int, *, entitled: bool) -> bool:
    return level <= FREE_MAX_LEVEL or entitled


def gate_reason(level: int, *, entitled: bool) -> str | None:
    """None when allowed; otherwise a short machine code for the client."""
    return None if can_access_level(level, entitled=entitled) else "paywall"

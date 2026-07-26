"""Subscription entitlements — pure functions (spec §19).

What a learner is allowed to reach depends on their subscription status, and
that decision has to be made the same way everywhere: on the server before a
gated route runs, and in the UI so a locked thing looks locked. Both read from
this module.

Statuses (spec §19):

    free        — signed up, not paying. Level 1 only.
    beta        — beta tester. Full access, contributes feedback. Time-boxed by
                  a beta program, but treated as full-access while active.
    lifetime    — granted free lifetime access for contributing. Full access.
    paid_active — a current Stripe subscription. Full access.
    paid_past_due — payment failed, inside the grace window. Still full access,
                  because dunning hasn't given up yet (§19 failed-payment).
    paid_canceled — canceled; access continues until the paid period ends, then
                  falls back to free.

The gate itself is deliberately simple: **level 1 is free for everyone; a few
practice types are free but capped to level-1 content; everything else needs an
active entitlement.** One rule, stated once.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import Enum

FREE_LEVEL = 1

# Practice types a free user can touch — but only on level-1 content (§19).
FREE_PRACTICE_MODES = frozenset({"fill_blank", "listening", "reading"})


class SubStatus(str, Enum):
    free = "free"
    beta = "beta"
    lifetime = "lifetime"
    paid_active = "paid_active"
    paid_past_due = "paid_past_due"
    paid_canceled = "paid_canceled"


# Statuses that grant full access right now. past_due is included: the grace
# window is exactly the time we keep access on while retrying payment.
_FULL_ACCESS = frozenset({
    SubStatus.beta, SubStatus.lifetime,
    SubStatus.paid_active, SubStatus.paid_past_due,
})


@dataclass(frozen=True)
class Entitlement:
    status: SubStatus
    full_access: bool
    max_free_level: int
    # For a canceled sub, access continues until this moment, then drops to free.
    access_until: dt.datetime | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "full_access": self.full_access,
            "max_free_level": self.max_free_level,
            "access_until": self.access_until.isoformat() if self.access_until else None,
        }


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)


def resolve_entitlement(
    status: SubStatus | str,
    *,
    current_period_end: dt.datetime | None = None,
    now: dt.datetime,
) -> Entitlement:
    """Turn a stored subscription status into what the user may reach right now.

    A canceled subscription still grants access until its period end; after
    that, the same row resolves to free without needing a write. That means a
    lapsed cancel doesn't depend on a cron job to downgrade it — the entitlement
    is recomputed from the clock every request.
    """
    status = SubStatus(status)
    now = _aware(now)
    period_end = _aware(current_period_end)

    if status == SubStatus.paid_canceled:
        still_paid = period_end is not None and now < period_end
        if still_paid:
            return Entitlement(status, True, FREE_LEVEL, access_until=period_end)
        return Entitlement(SubStatus.free, False, FREE_LEVEL)

    full = status in _FULL_ACCESS
    return Entitlement(status, full, FREE_LEVEL, access_until=period_end if full else None)


# --- the gate ------------------------------------------------------------

def can_access_level(entitlement: Entitlement, level: int) -> bool:
    """Level 1 is free for everyone; the rest needs full access."""
    if level <= entitlement.max_free_level:
        return True
    return entitlement.full_access


def can_access_practice(entitlement: Entitlement, mode: str, level: int) -> bool:
    """A free user gets the free practice modes, but only on level-1 content.

    Anything past level 1, or any mode outside the free set, needs full access.
    """
    if entitlement.full_access:
        return True
    if mode in FREE_PRACTICE_MODES and level <= entitlement.max_free_level:
        return True
    return False


def gate_reason(entitlement: Entitlement, level: int) -> str | None:
    """None if allowed, else a short human reason for the paywall."""
    if can_access_level(entitlement, level):
        return None
    return (
        "Level 1 is free. A subscription unlocks every level, all practice "
        "types, and the full curriculum."
    )

"""Entitlement resolution and dev-mode scaling — pure functions."""
import datetime as dt

import pytest

from app.domain.dev_mode import (
    DEFAULT_SCALE,
    MAX_SCALE,
    SCALE_PRESETS,
    WEEK_MINUTES,
    clamp_scale,
    describe_scale,
    resolve_scale,
)
from app.domain.entitlements import (
    FREE_LEVEL,
    Entitlement,
    SubStatus,
    can_access_level,
    can_access_practice,
    gate_reason,
    resolve_entitlement,
)

NOW = dt.datetime(2026, 7, 25, 12, 0, tzinfo=dt.timezone.utc)


# --- entitlement resolution ----------------------------------------------

def test_free_gets_level_one_only():
    e = resolve_entitlement(SubStatus.free, now=NOW)
    assert not e.full_access
    assert can_access_level(e, 1)
    assert not can_access_level(e, 2)


@pytest.mark.parametrize("status", [
    SubStatus.beta, SubStatus.lifetime, SubStatus.paid_active,
])
def test_full_access_statuses_reach_every_level(status):
    e = resolve_entitlement(status, now=NOW)
    assert e.full_access
    assert can_access_level(e, 1)
    assert can_access_level(e, 99)


def test_past_due_keeps_access_during_the_grace_window():
    """Payment failed but dunning hasn't given up — access stays on (§19)."""
    e = resolve_entitlement(SubStatus.paid_past_due, now=NOW)
    assert e.full_access
    assert can_access_level(e, 5)


def test_canceled_keeps_access_until_period_end():
    end = NOW + dt.timedelta(days=10)
    e = resolve_entitlement(SubStatus.paid_canceled, current_period_end=end, now=NOW)
    assert e.full_access
    assert e.access_until == end


def test_canceled_lapses_to_free_after_period_end():
    """No cron needed: the entitlement recomputes from the clock every request."""
    end = NOW - dt.timedelta(seconds=1)
    e = resolve_entitlement(SubStatus.paid_canceled, current_period_end=end, now=NOW)
    assert not e.full_access
    assert e.status == SubStatus.free
    assert not can_access_level(e, 2)


def test_canceled_with_no_period_end_is_free():
    e = resolve_entitlement(SubStatus.paid_canceled, current_period_end=None, now=NOW)
    assert not e.full_access


def test_naive_period_end_is_treated_as_utc():
    end = (NOW + dt.timedelta(days=1)).replace(tzinfo=None)
    e = resolve_entitlement(SubStatus.paid_canceled, current_period_end=end, now=NOW)
    assert e.full_access


# --- the practice gate ---------------------------------------------------

def test_free_user_gets_free_practice_on_level_one_only():
    e = resolve_entitlement(SubStatus.free, now=NOW)
    assert can_access_practice(e, "fill_blank", level=1)
    assert can_access_practice(e, "listening", level=1)
    # ...but not past level 1
    assert not can_access_practice(e, "fill_blank", level=2)
    # ...and not a non-free mode even at level 1
    assert not can_access_practice(e, "conjugation", level=1)


def test_full_access_reaches_every_practice():
    e = resolve_entitlement(SubStatus.paid_active, now=NOW)
    assert can_access_practice(e, "conjugation", level=8)
    assert can_access_practice(e, "speaking", level=5)


def test_gate_reason_is_none_when_allowed():
    e = resolve_entitlement(SubStatus.free, now=NOW)
    assert gate_reason(e, 1) is None
    assert gate_reason(e, 2) is not None


def test_free_level_constant_is_one():
    assert FREE_LEVEL == 1


# --- dev-mode scaling ----------------------------------------------------

def test_default_scale_is_a_noop():
    assert DEFAULT_SCALE == 1.0
    assert clamp_scale(None) == 1.0
    assert clamp_scale(1.0) == 1.0


def test_fast_preset_turns_one_week_into_thirty_seconds():
    scale = SCALE_PRESETS["fast"]
    week_seconds = WEEK_MINUTES * 60 * scale
    assert round(week_seconds) == 30


def test_scale_never_exceeds_one_or_drops_to_zero():
    """Dev mode only ever speeds up, and never makes an item due before review."""
    assert clamp_scale(5.0) == MAX_SCALE
    assert clamp_scale(-1.0) > 0
    assert clamp_scale(0.0) > 0


def test_nan_and_garbage_fall_back_to_no_scaling():
    assert clamp_scale(float("nan")) == 1.0
    assert clamp_scale("not a number") == 1.0


def test_resolve_scale_accepts_preset_names_and_raw_values():
    assert resolve_scale("off") == 1.0
    assert resolve_scale("fast") == SCALE_PRESETS["fast"]
    assert resolve_scale("0.5") == 0.5
    assert resolve_scale(0.25) == 0.25
    assert resolve_scale("nonsense") == 1.0


def test_describe_scale_reads_sensibly():
    assert "off" in describe_scale(1.0)
    assert "30s" in describe_scale(SCALE_PRESETS["fast"]) or "s" in describe_scale(SCALE_PRESETS["fast"])

"""Entitlements — the pure paywall rule."""
import pytest

from app.domain.entitlements import (
    FREE_MAX_LEVEL,
    can_access_level,
    gate_reason,
    is_entitled,
)


@pytest.mark.parametrize("role", ["moderator", "content_editor", "admin", "owner"])
def test_staff_always_entitled(role):
    assert is_entitled(role=role, tier="free", status="canceled") is True


def test_beta_tester_is_a_free_perk():
    assert is_entitled(role="beta_tester", tier="free", status="canceled") is True


def test_plain_free_user_is_not_entitled():
    assert is_entitled(role="user", tier="free", status="active") is False


def test_beta_default_is_entitled_during_beta():
    assert is_entitled(role="user", tier="free_beta", status="active") is True


def test_paid_active_or_trialing_is_entitled():
    assert is_entitled(role="user", tier="monthly", status="active") is True
    assert is_entitled(role="user", tier="annual", status="trialing") is True


def test_paid_past_due_or_canceled_is_not_entitled():
    assert is_entitled(role="user", tier="monthly", status="past_due") is False
    assert is_entitled(role="user", tier="annual", status="canceled") is False


def test_lifetime_ignores_payment_status_until_revoked():
    assert is_entitled(role="user", tier="lifetime", status="active") is True
    assert is_entitled(role="user", tier="lifetime", status="past_due") is True
    assert is_entitled(role="user", tier="lifetime", status="canceled") is False


def test_level_one_is_free_for_everyone():
    assert FREE_MAX_LEVEL == 1
    assert can_access_level(1, entitled=False) is True


def test_beyond_level_one_needs_entitlement():
    assert can_access_level(2, entitled=False) is False
    assert can_access_level(2, entitled=True) is True
    assert can_access_level(9, entitled=False) is False


def test_gate_reason():
    assert gate_reason(1, entitled=False) is None
    assert gate_reason(3, entitled=False) == "paywall"
    assert gate_reason(3, entitled=True) is None

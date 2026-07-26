"""Email tokens and the email provider abstraction — pure/near-pure tests."""
import datetime as dt

import pytest

from app.domain.email_tokens import (
    RESET_TTL,
    VERIFY_TTL,
    generate_token,
    hash_token,
    is_expired,
    is_redeemable,
    reset_expiry,
    tokens_match,
    verify_expiry,
)
from app.email.provider import (
    ConsoleEmailProvider,
    MemoryEmailProvider,
    OutgoingEmail,
    SmtpEmailProvider,
    build_provider,
)

NOW = dt.datetime(2026, 7, 24, 12, 0, tzinfo=dt.timezone.utc)


# --- tokens ---------------------------------------------------------------

def test_tokens_are_unique_and_long():
    a, b = generate_token(), generate_token()
    assert a != b
    assert len(a) > 30              # ~43 chars for 32 url-safe bytes


def test_only_the_hash_is_stored_and_it_verifies():
    raw = generate_token()
    stored = hash_token(raw)
    assert stored != raw            # never store the raw token
    assert tokens_match(raw, stored)
    assert not tokens_match(raw + "x", stored)
    assert not tokens_match("anything", "")


def test_hash_is_stable():
    raw = generate_token()
    assert hash_token(raw) == hash_token(raw)


def test_reset_and_verify_ttls_differ():
    assert reset_expiry(NOW) == NOW + RESET_TTL
    assert verify_expiry(NOW) == NOW + VERIFY_TTL
    assert RESET_TTL < VERIFY_TTL


def test_expiry_boundary_is_inclusive():
    assert not is_expired(NOW + dt.timedelta(seconds=1), NOW)
    assert is_expired(NOW, NOW)                      # exactly at expiry = expired
    assert is_expired(NOW - dt.timedelta(seconds=1), NOW)


def test_missing_expiry_counts_as_expired():
    assert is_expired(None, NOW) is True


def test_naive_expiry_is_treated_as_utc():
    naive = (NOW + dt.timedelta(minutes=30)).replace(tzinfo=None)
    assert not is_expired(naive, NOW)


def test_redeemable_only_when_fresh_and_unused():
    good = reset_expiry(NOW)
    assert is_redeemable(expires_at=good, consumed_at=None, now=NOW)
    # already consumed
    assert not is_redeemable(expires_at=good, consumed_at=NOW, now=NOW)
    # expired
    assert not is_redeemable(
        expires_at=NOW - dt.timedelta(minutes=1), consumed_at=None, now=NOW,
    )


# --- provider selection ---------------------------------------------------

class _Cfg:
    def __init__(self, **kw):
        self.email_backend = kw.get("email_backend", "")
        self.smtp_host = kw.get("smtp_host", "")
        self.smtp_port = kw.get("smtp_port", 1025)
        self.smtp_username = kw.get("smtp_username", "")
        self.smtp_password = kw.get("smtp_password", "")
        self.smtp_use_tls = kw.get("smtp_use_tls", False)
        self.email_from = kw.get("email_from", "")


def test_no_config_falls_back_to_console():
    assert isinstance(build_provider(_Cfg()), ConsoleEmailProvider)


def test_memory_backend_is_selectable_for_tests():
    assert isinstance(build_provider(_Cfg(email_backend="memory")), MemoryEmailProvider)


def test_an_smtp_host_selects_smtp():
    provider = build_provider(_Cfg(smtp_host="localhost", smtp_port=1025))
    assert isinstance(provider, SmtpEmailProvider)
    assert provider.host == "localhost"


def test_explicit_console_beats_a_configured_host():
    provider = build_provider(_Cfg(email_backend="console", smtp_host="localhost"))
    assert isinstance(provider, ConsoleEmailProvider)


def test_memory_provider_captures_messages():
    provider = MemoryEmailProvider()
    provider.send(OutgoingEmail(to="a@b.com", subject="hi", text="body"))
    assert len(provider.sent) == 1
    assert provider.sent[0].to == "a@b.com"

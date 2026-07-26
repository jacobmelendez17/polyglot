"""One-time email tokens — pure functions (password reset, email verification).

The security shape here matters more than the mechanics:

  * **Only a hash is stored.** The raw token goes in the email and nowhere else.
    A database leak exposes hashes, which are useless for redeeming a token —
    the same reason we hash refresh tokens.
  * **Single use.** A token is marked consumed the moment it's redeemed; a
    second attempt fails even inside the validity window.
  * **Short-lived.** Reset tokens last one hour, verification links a day. Long
    enough to be usable, short enough that a leaked inbox from last week is not
    a standing key to the account.
  * **Constant-time comparison** on the hash, so redemption time can't be used
    to guess a token byte by byte.

No database, no clock of its own — `now` is always injected — so every property
above is a deterministic unit test.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets

# 256 bits of entropy, URL-safe. Long enough that guessing is hopeless and the
# expiry window never becomes the weak point.
TOKEN_BYTES = 32

RESET_TTL = dt.timedelta(hours=1)
VERIFY_TTL = dt.timedelta(days=1)


def generate_token() -> str:
    """A fresh URL-safe token. Returned once, shown to no one but the recipient."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """SHA-256 of the raw token. This is what the database stores."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_match(raw_token: str, stored_hash: str) -> bool:
    """Constant-time check that a presented token matches a stored hash."""
    return hmac.compare_digest(hash_token(raw_token), stored_hash or "")


def reset_expiry(now: dt.datetime) -> dt.datetime:
    return now + RESET_TTL


def verify_expiry(now: dt.datetime) -> dt.datetime:
    return now + VERIFY_TTL


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def is_expired(expires_at: dt.datetime | None, now: dt.datetime) -> bool:
    exp = _aware(expires_at)
    if exp is None:
        return True
    current = _aware(now)
    assert current is not None
    return current >= exp


def is_redeemable(
    *, expires_at: dt.datetime | None, consumed_at: dt.datetime | None,
    now: dt.datetime,
) -> bool:
    """A token can be spent only if it exists, hasn't expired, and is unused."""
    return consumed_at is None and not is_expired(expires_at, now)

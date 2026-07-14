"""Password hashing using PBKDF2-HMAC-SHA256 from the standard library.

Chosen for zero external dependencies and determinism in tests. The format is
self-describing (algorithm$iterations$salt$hash) so we can raise the iteration
count later without breaking existing hashes. A provider swap to argon2/bcrypt
is a drop-in replacement of hash_password/verify_password.
"""
from __future__ import annotations

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 240_000
_SALT_BYTES = 16


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = encoded.split("$")
    except (ValueError, AttributeError):
        return False
    if algo != _ALGO:
        return False
    expected = bytes.fromhex(hash_hex)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
    # constant-time comparison to avoid timing leaks
    return hmac.compare_digest(expected, actual)


def needs_rehash(encoded: str, *, iterations: int = _ITERATIONS) -> bool:
    """True if a stored hash used fewer iterations than we now require."""
    try:
        _, iters, _, _ = encoded.split("$")
    except (ValueError, AttributeError):
        return True
    return int(iters) < iterations

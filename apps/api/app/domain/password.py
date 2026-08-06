"""Password policy — pure rules (§25, by request).

A password must be at least 8 characters and include an uppercase letter, a lowercase
letter, a number, and a special character. `check_password` reports each rule's
pass/fail (for a UI checklist); `validate_password` raises with a human message
listing what's missing. No I/O — fully unit-testable and shared by the signup route.
"""
from __future__ import annotations

MIN_LENGTH = 8
# Explicit set (excludes whitespace) so "a space" doesn't silently satisfy the rule.
SPECIAL_CHARS = set("!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~")

# key -> (human label, predicate)
RULES: list[tuple[str, str, object]] = [
    ("length", f"at least {MIN_LENGTH} characters", lambda p: len(p) >= MIN_LENGTH),
    ("uppercase", "an uppercase letter", lambda p: any(c.isupper() for c in p)),
    ("lowercase", "a lowercase letter", lambda p: any(c.islower() for c in p)),
    ("digit", "a number", lambda p: any(c.isdigit() for c in p)),
    ("special", "a special character", lambda p: any(c in SPECIAL_CHARS for c in p)),
]


class PasswordError(Exception):
    """Raised when a password fails the policy. Message is safe to show the user."""

    def __init__(self, failed: list[str]) -> None:
        self.failed = failed
        super().__init__("Your password needs " + ", ".join(failed) + ".")


def check_password(password: str) -> dict[str, bool]:
    """Per-rule pass/fail, keyed by rule name (for a live requirements checklist)."""
    return {key: bool(pred(password)) for key, _label, pred in RULES}


def validate_password(password: str) -> None:
    """Raise PasswordError if any rule fails, listing the missing requirements."""
    failed = [label for key, label, pred in RULES if not pred(password)]
    if failed:
        raise PasswordError(failed)

"""Immersion mode — the unlock rule (spec §16).

Immersion turns the app's own chrome Spanish: nav, buttons, widget labels. It
deliberately does NOT translate instructions, item meanings, or anything a user
wrote — those stay in whatever language they were, because an explanation you
cannot read is not immersion, it is a locked door.

It unlocks at level 10, which in this app means curriculum level, not XP rank.
"""
from __future__ import annotations

IMMERSION_UNLOCK_LEVEL = 10

# Strings that stay in English even with immersion on: these are the categories,
# not individual keys, so the rule is stated once and the dictionary follows it.
NEVER_TRANSLATED = (
    "item meanings and translations",
    "lesson and practice instructions",
    "user-written content (journals, forum posts, synonyms)",
    "error messages that describe what went wrong",
)


def immersion_unlocked(levels_completed: int) -> bool:
    """A level counts as completed once it has been fully unlocked past."""
    return int(levels_completed or 0) >= IMMERSION_UNLOCK_LEVEL


def levels_remaining(levels_completed: int) -> int:
    return max(0, IMMERSION_UNLOCK_LEVEL - int(levels_completed or 0))


def can_enable(levels_completed: int, requested: bool) -> bool:
    """Turning immersion ON requires the unlock; turning it OFF never does.

    The asymmetry matters: if the unlock rule ever changed, someone who already
    had it on should still be able to switch it back off.
    """
    return (not requested) or immersion_unlocked(levels_completed)

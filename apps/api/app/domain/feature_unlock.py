"""Feature-unlock schedule — pure rules (spec §7).

Practice features open up as a learner completes levels. This module holds the
schedule (feature → the level at which it unlocks) and the pure functions over it.
No I/O, so "which features are open at N completed levels" is fully unit-testable and
stable.

FILLER SCHEDULE — the spec says a CSV will define the real unlock levels ("the CSV
will outline when these features or sub-features become unlocked"). These are
reasonable placeholders, easy to change: edit the dict, and the API/UI follow.
Reviews and reading are available from the very start; immersion mirrors the §16
"after level 10" rule.
"""
from __future__ import annotations

# feature key -> level at which it unlocks (1 = available immediately)
FEATURE_UNLOCK: dict[str, int] = {
    "reviews": 1,
    "reading": 1,
    "listening": 2,
    "writing": 2,          # daily writing prompt / journal
    "testing_app": 2,      # app map tests what you've covered
    "sentence_structure": 3,
    "speaking": 3,
    "testing_life": 3,
    "testing_cefr": 4,
    "verb_conjugation": 5,  # after tense grammar is well underway (§7)
    "immersion": 10,        # §16: immersion unlocks after level 10
}

# Stable display order for the roadmap (unlock level, then key).
_ORDER = sorted(FEATURE_UNLOCK, key=lambda f: (FEATURE_UNLOCK[f], f))


def is_feature(feature: str) -> bool:
    return feature in FEATURE_UNLOCK


def unlock_level(feature: str) -> int:
    """The level a feature unlocks at. Unknown features are treated as locked
    forever (a large sentinel) rather than silently available."""
    return FEATURE_UNLOCK.get(feature, 10**6)


def is_unlocked(feature: str, *, completed_levels: int) -> bool:
    return completed_levels >= unlock_level(feature)


def unlocked_features(completed_levels: int) -> set[str]:
    return {f for f in FEATURE_UNLOCK if completed_levels >= FEATURE_UNLOCK[f]}


def feature_states(completed_levels: int) -> list[dict]:
    """Every feature with its unlock level and current state, in roadmap order."""
    return [
        {
            "feature": f,
            "unlock_level": FEATURE_UNLOCK[f],
            "unlocked": completed_levels >= FEATURE_UNLOCK[f],
            "levels_remaining": max(0, FEATURE_UNLOCK[f] - completed_levels),
        }
        for f in _ORDER
    ]

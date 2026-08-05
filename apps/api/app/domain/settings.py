"""Settings validation — pure rules (spec §16).

Every settings write goes through `validate_settings_patch`: it accepts only known
fields, checks each against its allowed values/range, and enforces the one real
business rule — immersion mode can't be turned on until it's unlocked (§16: "after
finishing level 10"). It returns a cleaned patch (correct types) or raises with a
per-field error map, so the route can hand the client exactly what was wrong. No
I/O, fully unit-testable.
"""
from __future__ import annotations

# Enumerated fields → their allowed values.
ENUM_FIELDS: dict[str, set[str]] = {
    "theme": {"light", "dark", "system"},
    "font_size": {"sm", "md", "lg", "xl"},
    "review_order": {"newest_first", "stage_order", "random"},
    "back_to_back_order": {"es_first", "en_first"},
    "curriculum_mode": {"default_dispersed", "grammar_batch", "fully_dispersed"},
    "dialect": {"latam_mx", "castilian"},
}

BOOL_FIELDS: set[str] = {
    "back_to_back", "show_srs_indicator", "review_batch_enabled", "reveal_full_answer",
    "allow_cheating", "allow_skipping", "undo_enabled", "accept_user_synonyms",
    "intermissions_enabled", "immersion_mode", "audio_autoplay",
}

# integer fields → (min, max)
INT_FIELDS: dict[str, tuple[int, int]] = {
    "lesson_batch_size": (1, 50),
    "review_batch_size": (1, 100),
}

# float fields → (min, max)
FLOAT_FIELDS: dict[str, tuple[float, float]] = {
    "leech_threshold": (0.1, 5.0),
    "audio_rate": (0.5, 2.0),
}

# free-ish strings → max length
STR_FIELDS: dict[str, int] = {
    "color_theme": 30,
    "audio_voice": 60,
}

ALL_FIELDS = (set(ENUM_FIELDS) | BOOL_FIELDS | set(INT_FIELDS)
              | set(FLOAT_FIELDS) | set(STR_FIELDS))


class SettingsError(Exception):
    def __init__(self, field_errors: dict[str, str]) -> None:
        super().__init__("Invalid settings.")
        self.field_errors = field_errors


def validate_settings_patch(patch: dict, *, immersion_unlocked: bool) -> dict:
    """Return a cleaned patch, or raise SettingsError with per-field messages."""
    clean: dict = {}
    errors: dict[str, str] = {}

    for key, value in patch.items():
        if value is None:
            continue  # unset fields in a partial update are simply skipped
        if key not in ALL_FIELDS:
            errors[key] = "Unknown setting."
            continue
        if key in ENUM_FIELDS:
            if value not in ENUM_FIELDS[key]:
                errors[key] = f"Must be one of: {', '.join(sorted(ENUM_FIELDS[key]))}."
            else:
                clean[key] = value
        elif key in BOOL_FIELDS:
            if not isinstance(value, bool):
                errors[key] = "Must be true or false."
            else:
                clean[key] = value
        elif key in INT_FIELDS:
            lo, hi = INT_FIELDS[key]
            if isinstance(value, bool) or not isinstance(value, int):
                errors[key] = "Must be a whole number."
            elif not (lo <= value <= hi):
                errors[key] = f"Must be between {lo} and {hi}."
            else:
                clean[key] = value
        elif key in FLOAT_FIELDS:
            lo, hi = FLOAT_FIELDS[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors[key] = "Must be a number."
            elif not (lo <= float(value) <= hi):
                errors[key] = f"Must be between {lo} and {hi}."
            else:
                clean[key] = float(value)
        else:  # STR_FIELDS
            if not isinstance(value, str):
                errors[key] = "Must be text."
            elif len(value) > STR_FIELDS[key]:
                errors[key] = f"Must be at most {STR_FIELDS[key]} characters."
            else:
                clean[key] = value

    # The one business rule: immersion mode gates on being unlocked (§16).
    if clean.get("immersion_mode") is True and not immersion_unlocked:
        errors["immersion_mode"] = "Immersion mode unlocks after you finish level 10."
        clean.pop("immersion_mode", None)

    if errors:
        raise SettingsError(errors)
    return clean

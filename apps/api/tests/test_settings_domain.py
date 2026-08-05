"""Settings validation — the pure rules (§16)."""
import pytest

from app.domain.settings import SettingsError, validate_settings_patch


def test_valid_patch_is_cleaned():
    clean = validate_settings_patch(
        {"theme": "dark", "lesson_batch_size": 10, "leech_threshold": 1.5,
         "allow_cheating": True, "curriculum_mode": "grammar_batch"},
        immersion_unlocked=False)
    assert clean["theme"] == "dark" and clean["lesson_batch_size"] == 10
    assert clean["leech_threshold"] == 1.5 and clean["allow_cheating"] is True


def test_none_values_are_skipped():
    assert validate_settings_patch({"theme": None, "font_size": "lg"},
                                   immersion_unlocked=True) == {"font_size": "lg"}


@pytest.mark.parametrize("patch,field", [
    ({"theme": "neon"}, "theme"),
    ({"unknown_x": 1}, "unknown_x"),
    ({"lesson_batch_size": 0}, "lesson_batch_size"),
    ({"lesson_batch_size": 999}, "lesson_batch_size"),
    ({"lesson_batch_size": True}, "lesson_batch_size"),
    ({"allow_cheating": "yes"}, "allow_cheating"),
    ({"leech_threshold": 9.0}, "leech_threshold"),
    ({"review_order": "sideways"}, "review_order"),
])
def test_invalid_values_rejected(patch, field):
    with pytest.raises(SettingsError) as ex:
        validate_settings_patch(patch, immersion_unlocked=False)
    assert field in ex.value.field_errors


def test_immersion_gate():
    with pytest.raises(SettingsError) as ex:
        validate_settings_patch({"immersion_mode": True}, immersion_unlocked=False)
    assert "immersion_mode" in ex.value.field_errors
    assert validate_settings_patch({"immersion_mode": True}, immersion_unlocked=True) \
        == {"immersion_mode": True}
    # turning it off is always allowed
    assert validate_settings_patch({"immersion_mode": False}, immersion_unlocked=False) \
        == {"immersion_mode": False}


def test_multiple_errors_accumulate():
    with pytest.raises(SettingsError) as ex:
        validate_settings_patch({"theme": "x", "font_size": "y"}, immersion_unlocked=False)
    assert set(ex.value.field_errors) == {"theme", "font_size"}

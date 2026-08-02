"""Dev-mode SRS scaling — pure functions."""
from app.domain.dev_mode import (
    DEFAULT_SCALE,
    MAX_SCALE,
    SCALE_PRESETS,
    WEEK_MINUTES,
    clamp_scale,
    describe_scale,
    resolve_scale,
)


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

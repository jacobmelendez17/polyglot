"""Dashboard layout rules: normalization, add/remove/move, span clamping.

Pure functions. The theme running through these is that a layout should never
be able to break a dashboard — bad input degrades, it doesn't raise.
"""
import pytest

from app.domain.widgets import (
    CATALOG,
    CATALOG_BY_KEY,
    GRID_COLUMNS,
    MAX_WIDGETS,
    Layout,
    LayoutEntry,
    add_widget,
    available_to_add,
    catalog_dicts,
    default_layout,
    move_widget,
    normalize,
    remove_widget,
    reorder,
    set_span,
)


def keys(layout: Layout) -> list[str]:
    return [e.key for e in layout.entries]


# --- catalog --------------------------------------------------------------

def test_catalog_keys_are_unique():
    assert len({w.key for w in CATALOG}) == len(CATALOG)


def test_every_span_fits_the_grid():
    for w in CATALOG:
        assert 1 <= w.min_span <= w.span <= w.max_span <= GRID_COLUMNS


def test_default_layout_is_the_default_flagged_widgets():
    assert keys(default_layout()) == [w.key for w in CATALOG if w.default]


def test_catalog_serialises_for_the_api():
    entry = catalog_dicts()[0]
    assert set(entry) == {"key", "title", "description", "default", "span",
                          "min_span", "max_span"}


# --- normalization --------------------------------------------------------

def test_normalize_accepts_the_stored_shape():
    layout = normalize({"widgets": [{"key": "xp", "span": 1},
                                    {"key": "forecast", "span": 2}]})
    assert keys(layout) == ["xp", "forecast"]


def test_normalize_accepts_a_bare_list_of_keys():
    assert keys(normalize(["xp", "leech"])) == ["xp", "leech"]


def test_unknown_widgets_are_dropped_not_stored():
    """A stale client naming a widget we deleted must not wedge the dashboard."""
    layout = normalize({"widgets": [{"key": "xp"}, {"key": "ghost_widget"}]})
    assert keys(layout) == ["xp"]


def test_duplicates_collapse_to_the_first():
    layout = normalize({"widgets": [{"key": "xp", "span": 2}, {"key": "xp", "span": 1}]})
    assert keys(layout) == ["xp"]
    assert layout.entries[0].span == 2


def test_spans_are_clamped_to_what_the_widget_can_render():
    wide = normalize({"widgets": [{"key": "xp", "span": 99}]})
    assert wide.entries[0].span == CATALOG_BY_KEY["xp"].max_span
    narrow = normalize({"widgets": [{"key": "welcome", "span": 0}]})
    assert narrow.entries[0].span == CATALOG_BY_KEY["welcome"].min_span


def test_missing_span_falls_back_to_the_widget_default():
    layout = normalize({"widgets": [{"key": "progression"}]})
    assert layout.entries[0].span == CATALOG_BY_KEY["progression"].span


@pytest.mark.parametrize("junk", [None, 42, "widgets", {}, {"widgets": "nope"},
                                  {"widgets": None}])
def test_unreadable_input_degrades_to_defaults(junk):
    assert keys(normalize(junk)) == keys(default_layout())


def test_junk_entries_inside_a_valid_list_are_skipped():
    layout = normalize({"widgets": [None, 7, {"key": 5}, {"key": "xp"}, "leech"]})
    assert keys(layout) == ["xp", "leech"]


def test_an_empty_layout_is_legal():
    """Removing every widget is a choice, not an error to be corrected."""
    layout = normalize({"widgets": []})
    assert keys(layout) == []


def test_layout_is_capped():
    huge = {"widgets": [{"key": w.key} for w in CATALOG] * 10}
    assert len(normalize(huge).entries) <= MAX_WIDGETS


# --- add / remove ---------------------------------------------------------

def test_add_appends_a_widget():
    layout = add_widget(Layout(entries=(LayoutEntry("xp", 1),)), "leech")
    assert keys(layout) == ["xp", "leech"]


def test_adding_a_widget_twice_is_a_no_op():
    once = add_widget(default_layout(), "xp")
    assert keys(once) == keys(default_layout())


def test_adding_an_unknown_widget_is_a_no_op():
    assert keys(add_widget(default_layout(), "ghost")) == keys(default_layout())


def test_remove_takes_a_widget_out():
    layout = remove_widget(default_layout(), "xp")
    assert "xp" not in keys(layout)
    assert len(layout.entries) == len(default_layout().entries) - 1


def test_removing_something_absent_is_a_no_op():
    assert keys(remove_widget(default_layout(), "ghost")) == keys(default_layout())


def test_available_to_add_is_the_complement():
    layout = Layout(entries=(LayoutEntry("xp", 1),))
    available = [w.key for w in available_to_add(layout)]
    assert "xp" not in available
    assert "welcome" in available


# --- movement -------------------------------------------------------------

def test_move_shifts_a_widget():
    layout = normalize(["welcome", "progression", "xp"])
    assert keys(move_widget(layout, "xp", -1)) == ["welcome", "xp", "progression"]
    assert keys(move_widget(layout, "welcome", 1)) == ["progression", "welcome", "xp"]


def test_movement_clamps_at_the_ends_instead_of_wrapping():
    """Holding the arrow key at the top must not send a widget to the bottom."""
    layout = normalize(["welcome", "progression", "xp"])
    assert keys(move_widget(layout, "welcome", -5)) == ["welcome", "progression", "xp"]
    assert keys(move_widget(layout, "xp", 5)) == ["welcome", "progression", "xp"]


def test_moving_zero_or_an_absent_widget_changes_nothing():
    layout = normalize(["welcome", "xp"])
    assert keys(move_widget(layout, "xp", 0)) == ["welcome", "xp"]
    assert keys(move_widget(layout, "ghost", 1)) == ["welcome", "xp"]


def test_reorder_places_a_widget_at_an_index():
    layout = normalize(["welcome", "progression", "xp", "leech"])
    assert keys(reorder(layout, "leech", 0)) == ["leech", "welcome", "progression", "xp"]
    assert keys(reorder(layout, "welcome", 3)) == ["progression", "xp", "leech", "welcome"]


def test_reorder_is_stable_for_the_untouched_widgets():
    layout = normalize(["welcome", "progression", "xp", "leech", "fluent"])
    moved = reorder(layout, "xp", 4)
    assert keys(moved) == ["welcome", "progression", "leech", "fluent", "xp"]


# --- spans ----------------------------------------------------------------

def test_set_span_clamps():
    layout = set_span(normalize(["xp"]), "xp", 99)
    assert layout.entries[0].span == CATALOG_BY_KEY["xp"].max_span


def test_set_span_on_an_unknown_widget_is_a_no_op():
    layout = normalize(["xp"])
    assert set_span(layout, "ghost", 3).to_dict() == layout.to_dict()


def test_round_trip_through_dict_is_stable():
    layout = default_layout()
    assert normalize(layout.to_dict()).to_dict() == layout.to_dict()

from app.domain.normalize import normalize_term, strip_accents


def test_strip_accents():
    assert strip_accents("está") == "esta"
    assert strip_accents("niño") == "nino"


def test_normalize_preserves_accents_by_default():
    # esta vs está must remain distinguishable (PLANNING §8).
    assert normalize_term("Está") == "está"
    assert normalize_term("está") != normalize_term("esta")


def test_normalize_folds_accents_when_asked():
    assert normalize_term("Está", fold_accents=True) == "esta"


def test_normalize_collapses_space_and_punct():
    assert normalize_term("  ¿Cómo   estás?  ") == "cómo   estás".replace("   ", " ")
    assert normalize_term("¡Hola!") == "hola"

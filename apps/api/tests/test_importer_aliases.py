"""Slice 38 — importer accepts real-world CSV header shapes.

These cover the forgiving header-aliasing added in slice 38: the same parsers now
accept 'Word'/'Grammar'/'Term' for the term, 'Level'/'Unit' for the level, pull a
grammar gloss from 'Meaning' when 'Translation' is blank, ignore unknown columns,
and surface a clear error when no term column is present. Pure parser — no DB.
"""
from app.importer.curriculum_csv import parse_grammar, parse_vocabulary

# A grammar sheet shaped like the user's export: term lives in "Word", the gloss
# lives in "Meaning", Translation/PoS/Structure are blank, extra columns present.
GRAMMAR_WORD_HEADER = (
    "Word,Translation,Level,Batch,Pronunciation,IPA,PoS,Meaning,Example,"
    "Example Tran.,Synonyms,Variants,Castilian,Tags\r\n"
    "y,,1,5,,,,and,,,,,,\r\n"
    "con,,1,5,,,,with,,,,,,\r\n"
    "por qué,,2,5,,,,why,,,,,,\r\n"
)

# A vocab sheet using synonym headers: Term / Unit / Lesson instead of Word/Level/Batch.
VOCAB_ALIAS_HEADER = (
    "Term,Translation,Unit,Lesson,PoS\r\n"
    "gato,cat,1,1,noun\r\n"
    "correr,to run,1,2,verb\r\n"
    "sinnada,,1,1,\r\n"  # missing translation -> still a hard error
)


def test_grammar_accepts_word_header_and_pulls_gloss_from_meaning():
    items, rep = parse_grammar(GRAMMAR_WORD_HEADER)
    assert rep.rows_ok == 3
    assert not rep.errors
    by_title = {i.title: i for i in items}
    assert "y" in by_title
    # Gloss came from Meaning because Translation was blank.
    assert by_title["y"].translation == "and"
    assert by_title["con"].translation == "with"


def test_vocab_accepts_alias_headers():
    items, rep = parse_vocabulary(VOCAB_ALIAS_HEADER)
    terms = {i.term for i in items}
    assert "gato" in terms and "correr" in terms
    # 'Unit'/'Lesson' were understood as level/batch.
    gato = next(i for i in items if i.term == "gato")
    assert gato.level == 1 and gato.batch == 1
    # A genuinely missing translation is still a hard error (vocab semantics kept).
    assert any(e.value == "sinnada" for e in rep.errors)


def test_missing_term_column_is_a_clear_error():
    no_term = "Translation,Level\r\ncat,1\r\n"
    _, rep = parse_grammar(no_term)
    assert rep.rows_ok == 0
    assert any(i.field == "columns" for i in rep.errors)


def test_unknown_columns_are_ignored():
    csv_text = (
        "Word,Level,Batch,SomethingWeird,AnotherCol\r\n"
        "gato,1,1,ignore me,also ignored\r\n"
    )
    items, rep = parse_vocabulary(csv_text)
    # Row is missing Translation, so it errors — but the unknown columns didn't break parsing.
    assert rep.rows_seen == 1
    assert any(e.field == "Translation" for e in rep.errors)


def test_grammar_structure_warnings_are_aggregated_not_per_row():
    items, rep = parse_grammar(GRAMMAR_WORD_HEADER)
    structure_warnings = [w for w in rep.warnings if w.field == "Structure"]
    # One aggregated line, not one per row.
    assert len(structure_warnings) == 1
    assert "structure pattern" in structure_warnings[0].message

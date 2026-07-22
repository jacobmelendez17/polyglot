"""Importer parsing tests, including against the REAL uploaded CSVs."""
from app.importer.curriculum_csv import (
    parse_grammar,
    parse_vocabulary,
)

MINI_VOCAB = (
    "Word,Translation,Level,Batch,Pronunciation,IPA,PoS,Meaning,Example,"
    "Example Tran.,Synonyms,Variants,Castilian,Tags\r\n"
    "uno,one,1,1,oo-noh,/uno/,numeral,,,,N/A,\"una, unos\",N/A,number\r\n"
    "sinnada,,1,1,,,,,,,N/A,N/A,N/A,\r\n"                      # missing translation -> error
    "nunca,always,1,1,,,adverb,,,,N/A,N/A,N/A,\r\n"            # suspect translation -> warning
)

MINI_GRAMMAR = (
    "Grammar ,Translation,Structure,Level,PoS,Word Type,Example,Example Tran.\r\n"
    "subject pronouns,the,\"yo, tu\",1,,,,\r\n"
    "no structure,x,,1,,,,\r\n"                                # missing structure -> warning
)


def test_vocab_hard_error_on_missing_translation():
    items, rep = parse_vocabulary(MINI_VOCAB)
    terms = {i.term for i in items}
    assert "uno" in terms
    assert "sinnada" not in terms  # not emitted
    assert any(e.field == "Translation" and e.value == "sinnada" for e in rep.errors)


def test_vocab_flags_suspect_translation_without_fixing():
    items, rep = parse_vocabulary(MINI_VOCAB)
    nunca = next(i for i in items if i.term == "nunca")
    assert nunca.primary_translation == "always"  # NOT auto-corrected
    assert any("never" in w.message for w in rep.warnings)


def test_vocab_lists_split_and_na_is_empty():
    items, _ = parse_vocabulary(MINI_VOCAB)
    uno = next(i for i in items if i.term == "uno")
    assert uno.variations == ["una", "unos"]
    assert uno.synonyms == []           # \"N/A\" -> empty
    assert uno.castilian_variant == ""  # \"N/A\" -> empty


def test_vocab_article_never_guessed():
    items, _ = parse_vocabulary(MINI_VOCAB)
    assert all(i.article == "none" for i in items)  # importer never assigns articles


def test_grammar_missing_structure_is_warning_not_error():
    items, rep = parse_grammar(MINI_GRAMMAR)
    assert len(items) == 2
    assert not rep.errors
    assert any(w.field == "Structure" for w in rep.warnings)


# --- Real data tests -----------------------------------------------------

def test_real_vocab_counts_and_structure(real_csvs):
    items, rep = parse_vocabulary(real_csvs["vocab"])
    counts = rep.level_counts
    # Documented reality (PLANNING §0): L6 has 36 words, batch 4 missing.
    assert counts[6] == 36
    assert any("level 6 missing batch(es) [4]" in i.message for i in rep.warnings)
    # Row 41 (nosotros) is missing a translation -> exactly one hard error.
    assert len(rep.errors) == 1
    assert rep.errors[0].value == "nosotros"


def test_real_grammar_counts(real_csvs):
    items, rep = parse_grammar(real_csvs["grammar"])
    assert rep.level_counts == {1: 12, 2: 12, 3: 12, 4: 11, 5: 12}
    assert any("level 4 has 11 grammar points" in i.message for i in rep.warnings)
    # Grammar covers only levels 1-5.
    assert max(rep.level_counts) == 5

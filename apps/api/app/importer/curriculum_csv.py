"""Idempotent curriculum CSV importer.

Reads the \"Everything\" (vocabulary) and \"Grammar\" CSVs and produces a
structured plan of items to create/update, plus a report of warnings and errors.
The importer is PURE: it parses + validates and returns dataclasses. Persisting
those to the database is a thin separate step (import_service) so the parsing is
unit-testable without a database.

Design rules honored (docs/PLANNING.md §0, §5, §6):
- Content is imported in DRAFT status; nothing is auto-published.
- Missing enrichment (pronunciation, IPA, PoS, meaning, examples) => warnings, not failures.
- Known content problems (e.g. \"nunca\"=\"always\") are FLAGGED, never silently fixed.
- Article/gender are NOT guessed. Article stays \"none\" unless PoS is explicitly noun
  AND an article is provided; this respects \"only Spanish nouns get articles\".
- \"N/A\" and blank cells are treated as empty.
- Level 6 has 36 vocab words (batch 4 missing) and grammar covers only L1-5;
  the importer reports these as structural warnings rather than fabricating data.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from enum import Enum
from io import StringIO

from app.domain.normalize import normalize_term

EMPTY_TOKENS = {"", "n/a", "na", "none", "-"}
EXPECTED_VOCAB_PER_LEVEL = 48
EXPECTED_GRAMMAR_PER_LEVEL = 12
EXPECTED_BATCHES = 4
BATCH_SIZE = 12


class Severity(str, Enum):
    error = "error"       # row cannot be imported
    warning = "warning"   # imported, but needs admin attention


# A small, extensible table of translation pairs an editor should double-check.
# These are FLAGGED as warnings and never auto-corrected. Add entries here as
# review surfaces more; keeping it data-driven avoids guessing about content.
SUSPECT_TRANSLATIONS: dict[tuple[str, str], str] = {
    ("nunca", "always"): '"nunca" usually means "never", not "always"',
    ("siempre", "never"): '"siempre" usually means "always", not "never"',
}


def _translation_looks_suspect(term_norm: str, translation: str) -> str | None:
    """Return a warning message if a translation looks off, else None."""
    trans_norm = normalize_term(translation)
    if not trans_norm:
        return None
    hit = SUSPECT_TRANSLATIONS.get((term_norm, trans_norm))
    if hit:
        return hit
    if term_norm == trans_norm:
        return "term equals its translation — likely untranslated"
    return None


@dataclass
class Issue:
    severity: Severity
    row_number: int
    field: str
    message: str
    value: str = ""


@dataclass
class ParsedVocab:
    term: str
    normalized_term: str
    primary_translation: str
    level: int
    batch: int
    part_of_speech: str
    pronunciation: str
    ipa: str
    meaning: str
    synonyms: list[str]
    variations: list[str]
    castilian_variant: str
    article: str = "none"
    grammatical_gender: str = "none"


@dataclass
class ParsedGrammar:
    title: str
    translation: str
    structure_pattern: str
    level: int
    part_of_speech: str


@dataclass
class ImportReport:
    kind: str
    rows_seen: int = 0
    rows_ok: int = 0
    issues: list[Issue] = field(default_factory=list)
    level_counts: dict[int, int] = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.error]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity is Severity.warning]

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "rows_seen": self.rows_seen,
            "rows_ok": self.rows_ok,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "level_counts": self.level_counts,
            "issues": [
                {
                    "severity": i.severity.value,
                    "row": i.row_number,
                    "field": i.field,
                    "message": i.message,
                    "value": i.value,
                }
                for i in self.issues
            ],
        }


def _clean(value: str | None) -> str:
    v = (value or "").strip()
    return "" if v.lower() in EMPTY_TOKENS else v


def _split_list(value: str | None) -> list[str]:
    v = _clean(value)
    if not v:
        return []
    return [part.strip() for part in v.split(",") if part.strip()]


def _int_or_none(value: str | None) -> int | None:
    v = _clean(value)
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_vocabulary(csv_text: str) -> tuple[list[ParsedVocab], ImportReport]:
    report = ImportReport(kind="vocabulary")
    reader = csv.DictReader(StringIO(csv_text))
    items: list[ParsedVocab] = []

    for idx, raw in enumerate(reader, start=2):  # header is row 1
        term = _clean(raw.get("Word"))
        if not term:
            continue  # skip fully blank spacer rows silently
        report.rows_seen += 1

        translation = _clean(raw.get("Translation"))
        level = _int_or_none(raw.get("Level"))
        batch = _int_or_none(raw.get("Batch"))

        if not translation:
            report.issues.append(
                Issue(Severity.error, idx, "Translation", "missing translation", term)
            )
        if level is None:
            report.issues.append(Issue(Severity.error, idx, "Level", "missing/invalid level", term))
        if batch is None:
            report.issues.append(Issue(Severity.error, idx, "Batch", "missing/invalid batch", term))

        # Enrichment warnings (imported anyway, as draft).
        for col, label in (("Pronunciation", "pronunciation"), ("IPA", "IPA"),
                           ("PoS", "part of speech"), ("Meaning", "meaning")):
            if not _clean(raw.get(col)):
                report.issues.append(
                    Issue(Severity.warning, idx, col, f"missing {label}", term)
                )

        # Flag suspect translations (never auto-fix).
        if translation:
            suspect = _translation_looks_suspect(normalize_term(term), translation)
            if suspect:
                report.issues.append(
                    Issue(Severity.warning, idx, "Translation", suspect, translation)
                )

        pos = _clean(raw.get("PoS")).lower()
        # Article/gender are NOT inferred here; nouns get articles only when an
        # editor supplies them. So article stays none at import time.
        if level is None or batch is None or not translation:
            continue  # do not emit an item that failed a hard requirement

        items.append(
            ParsedVocab(
                term=term,
                normalized_term=normalize_term(term),
                primary_translation=translation,
                level=level,
                batch=batch,
                part_of_speech=pos,
                pronunciation=_clean(raw.get("Pronunciation")),
                ipa=_clean(raw.get("IPA")),
                meaning=_clean(raw.get("Meaning")),
                synonyms=_split_list(raw.get("Synonyms")),
                variations=_split_list(raw.get("Variants")),
                castilian_variant=_clean(raw.get("Castilian")),
            )
        )
        report.rows_ok += 1
        report.level_counts[level] = report.level_counts.get(level, 0) + 1

    _check_vocab_structure(items, report)
    # Merge in-level duplicates: keep the first occurrence so one import run is
    # all-creates and re-runs are all-updates (clean idempotency).
    deduped: list[ParsedVocab] = []
    seen: set[tuple[int, str]] = set()
    for it in items:
        key = (it.level, it.normalized_term)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped, report


def _check_vocab_structure(items: list[ParsedVocab], report: ImportReport) -> None:
    from collections import defaultdict

    by_level: dict[int, set[int]] = defaultdict(set)
    counts: dict[int, int] = defaultdict(int)
    seen: dict[tuple[int, str], int] = {}
    for it in items:
        by_level[it.level].add(it.batch)
        counts[it.level] += 1
        dkey = (it.level, it.normalized_term)
        if dkey in seen:
            report.issues.append(
                Issue(
                    Severity.warning, 0, "duplicate",
                    f"'{it.term}' appears more than once in level {it.level} "
                    f"— duplicate rows are merged into one item on import",
                    it.term,
                )
            )
        seen[dkey] = seen.get(dkey, 0) + 1
    for level in sorted(counts):
        if counts[level] != EXPECTED_VOCAB_PER_LEVEL:
            report.issues.append(
                Issue(
                    Severity.warning, 0, "structure",
                    f"level {level} has {counts[level]} vocab words "
                    f"(expected {EXPECTED_VOCAB_PER_LEVEL})",
                )
            )
        missing = {1, 2, 3, 4} - by_level[level]
        if missing:
            report.issues.append(
                Issue(Severity.warning, 0, "structure",
                      f"level {level} missing batch(es) {sorted(missing)}")
            )


def parse_grammar(csv_text: str) -> tuple[list[ParsedGrammar], ImportReport]:
    report = ImportReport(kind="grammar")
    reader = csv.DictReader(StringIO(csv_text))
    items: list[ParsedGrammar] = []

    # The grammar sheet header has a trailing space: \"Grammar \".
    for idx, raw in enumerate(reader, start=2):
        title = _clean(raw.get("Grammar ") or raw.get("Grammar"))
        if not title:
            continue
        report.rows_seen += 1
        level = _int_or_none(raw.get("Level"))
        translation = _clean(raw.get("Translation"))
        structure = _clean(raw.get("Structure"))

        if level is None:
            report.issues.append(
                Issue(Severity.error, idx, "Level", "missing/invalid level", title)
            )
            continue
        if not structure:
            report.issues.append(
                Issue(Severity.warning, idx, "Structure", "missing structure pattern", title)
            )

        items.append(
            ParsedGrammar(
                title=title,
                translation=translation,
                structure_pattern=structure,
                level=level,
                part_of_speech=_clean(raw.get("PoS")),
            )
        )
        report.rows_ok += 1
        report.level_counts[level] = report.level_counts.get(level, 0) + 1

    for level in sorted(report.level_counts):
        n = report.level_counts[level]
        if n != EXPECTED_GRAMMAR_PER_LEVEL:
            report.issues.append(
                Issue(Severity.warning, 0, "structure",
                      f"level {level} has {n} grammar points "
                      f"(expected {EXPECTED_GRAMMAR_PER_LEVEL})")
            )
    return items, report

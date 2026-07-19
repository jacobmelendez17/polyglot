"""Answer checking — pure, table-driven, deterministic (PLANNING §8).

Order of evaluation (first match wins):
    1. rejected_answers   → wrong, with a targeted message
    2. exact match        → correct
    3. accepted_answers   → correct
    4. synonyms           → correct (stored data only; never AI matching)
    5. typo tolerance     → correct with a warning, if within tolerance

Accents matter by default: "esta" != "está". In NORMAL mode a missing accent is
accepted *with a warning*; in STRICT/TEST mode it fails.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.domain.normalize import normalize_term, strip_accents


class CheckMode(str, Enum):
    strict = "strict"      # accents + spelling required
    normal = "normal"      # minor accent/capitalization slips warned but accepted
    practice = "practice"  # more forgiving
    test = "test"          # strict


class Warning(str, Enum):
    missing_accent = "missing_accent"
    wrong_accent = "wrong_accent"
    typo = "typo"
    synonym = "synonym"
    user_synonym = "user_synonym"
    capitalization = "capitalization"


@dataclass(frozen=True)
class CheckResult:
    correct: bool
    warnings: list[Warning] = field(default_factory=list)
    typo_forgiven: bool = False
    synonym_matched: bool = False
    matched: str | None = None       # which expected answer it matched
    message: str | None = None       # for rejected answers

    @property
    def warning_values(self) -> list[str]:
        return [w.value for w in self.warnings]


@dataclass(frozen=True)
class ExpectedAnswers:
    """Everything an item accepts. Built from the item row + user synonyms."""
    primary: str
    accepted: tuple[str, ...] = ()
    rejected: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()
    user_synonyms: tuple[str, ...] = ()


# --- typo distance -------------------------------------------------------

def damerau_levenshtein(a: str, b: str) -> int:
    """Edit distance including transposition of adjacent characters."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la

    # previous-previous, previous, current rows
    prev_prev: list[int] = []
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(
                cur[j - 1] + 1,          # insertion
                prev[j] + 1,             # deletion
                prev[j - 1] + cost,      # substitution
            )
            # transposition
            if (
                i > 1 and j > 1
                and a[i - 1] == b[j - 2]
                and a[i - 2] == b[j - 1]
            ):
                cur[j] = min(cur[j], prev_prev[j - 2] + 1)
        prev_prev, prev = prev, cur
    return prev[lb]


def _typo_tolerance(expected: str, mode: CheckMode) -> int:
    """Max edit distance allowed, scaled to answer length so short words
    aren't over-forgiven ('si' vs 'no' must never pass)."""
    if mode in (CheckMode.strict, CheckMode.test):
        return 0
    length = len(expected)
    if length <= 3:
        return 0          # too short to guess safely
    if length <= 6:
        return 1
    base = 2              # spec: "a couple letters swapped, or 1-2 missing"
    if mode is CheckMode.practice:
        return base + 1   # practice mode is more forgiving
    return base


# --- main entry point ----------------------------------------------------

def check_answer(
    submitted: str,
    expected: ExpectedAnswers,
    *,
    mode: CheckMode = CheckMode.normal,
    accept_user_synonyms: bool = False,
    allow_cheating: bool = False,
) -> CheckResult:
    raw = (submitted or "").strip()
    if not raw:
        return CheckResult(correct=False)

    sub = normalize_term(raw)
    sub_folded = strip_accents(sub)

    if allow_cheating and mode not in (CheckMode.strict, CheckMode.test):
        mode = CheckMode.practice

    # 1. Explicitly rejected answers — a targeted "no, not that one".
    for bad in expected.rejected:
        if sub == normalize_term(bad):
            return CheckResult(
                correct=False,
                message="That's a common mix-up — not quite the answer here.",
            )

    # Candidate pools, in priority order.
    primary_pool = [expected.primary, *expected.accepted]
    synonym_pool = list(expected.synonyms)
    if accept_user_synonyms or allow_cheating:
        synonym_pool += list(expected.user_synonyms)

    # 2/3. Exact (accent-sensitive) match against primary/accepted.
    for cand in primary_pool:
        if not cand:
            continue
        if sub == normalize_term(cand):
            return CheckResult(correct=True, matched=cand)

    # 4. Synonyms (stored data only).
    for cand in synonym_pool:
        if not cand:
            continue
        if sub == normalize_term(cand):
            is_user = cand in expected.user_synonyms
            return CheckResult(
                correct=True, synonym_matched=True, matched=cand,
                warnings=[Warning.user_synonym if is_user else Warning.synonym],
            )

    # Accent-insensitive comparison: right letters, wrong/missing accents.
    for cand in [*primary_pool, *synonym_pool]:
        if not cand:
            continue
        cand_norm = normalize_term(cand)
        if sub_folded == strip_accents(cand_norm):
            if mode in (CheckMode.strict, CheckMode.test):
                return CheckResult(correct=False, matched=cand,
                                   warnings=[Warning.missing_accent])
            warn = Warning.missing_accent if sub != cand_norm else Warning.wrong_accent
            return CheckResult(correct=True, matched=cand, warnings=[warn])

    # 5. Typo tolerance — last resort, accent-insensitive base comparison.
    best: tuple[int, str] | None = None
    for cand in [*primary_pool, *synonym_pool]:
        if not cand:
            continue
        cand_folded = strip_accents(normalize_term(cand))
        allowed = _typo_tolerance(cand_folded, mode)
        if allowed == 0:
            continue
        dist = damerau_levenshtein(sub_folded, cand_folded)
        if dist <= allowed and (best is None or dist < best[0]):
            best = (dist, cand)

    if best is not None:
        return CheckResult(
            correct=True, typo_forgiven=True, matched=best[1],
            warnings=[Warning.typo],
        )

    return CheckResult(correct=False)


def expected_from_item(
    *, primary: str, accepted: list | None = None, rejected: list | None = None,
    synonyms: list | None = None, user_synonyms: list | None = None,
) -> ExpectedAnswers:
    """Build ExpectedAnswers from raw JSON columns, tolerating both
    ["str", ...] and [{"text": "..."}] shapes."""
    def _flatten(values) -> tuple[str, ...]:
        out: list[str] = []
        for v in values or []:
            if isinstance(v, str):
                out.append(v)
            elif isinstance(v, dict):
                text = v.get("text") or v.get("answer")
                if text:
                    out.append(str(text))
        return tuple(out)

    return ExpectedAnswers(
        primary=primary,
        accepted=_flatten(accepted),
        rejected=_flatten(rejected),
        synonyms=_flatten(synonyms),
        user_synonyms=_flatten(user_synonyms),
    )

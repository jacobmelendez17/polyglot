"""Speech / utterance scoring — pure functions (spec §7, §33).

The MVP path is browser-native speech recognition: the user's device transcribes
what they said, and only that *transcript* reaches the server — never the audio.
This module scores a transcript against the expected phrase and produces a score
plus a word-by-word breakdown the UI can highlight. It's deliberately deterministic
so the scoring rule is unit-testable, exactly like the SRS and placement cores.

Scoring is token-level and Spanish-aware: both sides are normalized (accents
stripped, lower-cased, punctuation dropped) before comparison, because consumer
speech-to-text routinely drops accents and adds punctuation of its own. The score
is an F1-like overlap of the two word sequences via their longest common
subsequence, so both missing words and extra words cost you — and the word flags
come from that same alignment, so what's highlighted matches the number shown.

The engine scores a transcript; it is not tied to *how* that transcript was
produced. `services/speech.py` wraps it behind a provider seam so a third-party
scorer (phoneme-level, audio-in) can replace the local path later without touching
this logic.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

# A said phrase counts as "got it" at this overlap or better. Chosen for consumer
# STT: high enough to require the real words, forgiving of one slip or filler.
PASS_THRESHOLD = 80


@dataclass
class WordFlag:
    word: str          # the expected word, as written (for display)
    matched: bool      # did the learner's transcript cover it?


@dataclass
class UtteranceScore:
    score: int                       # 0..100
    passed: bool
    expected: str                    # the variant we scored against (best match)
    heard: str                       # normalized transcript, for feedback
    words: list[WordFlag] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)   # expected words not covered
    extra: list[str] = field(default_factory=list)     # heard words not expected


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", (text or "").strip().lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return _normalize(text).split()


def _lcs_matches(expected: list[str], heard: list[str]) -> list[bool]:
    """Longest common subsequence alignment. Returns, for each expected token, a
    flag for whether it participates in the LCS with the heard tokens."""
    n, m = len(expected), len(heard)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = (dp[i + 1][j + 1] + 1) if expected[i] == heard[j] \
                else max(dp[i + 1][j], dp[i][j + 1])
    matched = [False] * n
    i = j = 0
    while i < n and j < m:
        if expected[i] == heard[j]:
            matched[i] = True
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            i += 1
        else:
            j += 1
    return matched


def _extra_tokens(expected: list[str], heard: list[str]) -> list[str]:
    """Heard tokens left over after removing one match per expected token."""
    remaining = list(expected)
    extra: list[str] = []
    for tok in heard:
        if tok in remaining:
            remaining.remove(tok)
        else:
            extra.append(tok)
    return extra


def _similarity(expected: list[str], heard: list[str]) -> float:
    if not expected and not heard:
        return 1.0
    if not expected or not heard:
        return 0.0
    lcs = sum(_lcs_matches(expected, heard))
    return (2 * lcs) / (len(expected) + len(heard))   # F1-like, symmetric


def score_utterance(
    transcript: str, expected: str, accepted: list[str] | None = None,
    *, threshold: int = PASS_THRESHOLD,
) -> UtteranceScore:
    """Score a spoken attempt against the expected phrase (and any accepted
    variants), returning the best match with a word-level breakdown."""
    heard_tokens = _tokens(transcript)
    candidates = [expected, *(accepted or [])]

    best_text = expected
    best_sim = -1.0
    best_tokens: list[str] = _tokens(expected)
    for cand in candidates:
        cand_tokens = _tokens(cand)
        sim = _similarity(cand_tokens, heard_tokens)
        if sim > best_sim:
            best_sim, best_text, best_tokens = sim, cand, cand_tokens

    matched = _lcs_matches(best_tokens, heard_tokens) if best_tokens else []
    # Display words: the best variant as written, aligned to its normalized tokens
    # when the counts line up (they do for ordinary phrases); else fall back.
    display = best_text.split()
    if len(display) != len(best_tokens):
        display = best_tokens
    words = [WordFlag(word=display[i], matched=matched[i]) for i in range(len(best_tokens))]
    missed = [best_tokens[i] for i in range(len(best_tokens)) if not matched[i]]
    extra = _extra_tokens(best_tokens, heard_tokens)

    score = round(100 * max(best_sim, 0.0))
    return UtteranceScore(
        score=score, passed=score >= threshold, expected=best_text,
        heard=" ".join(heard_tokens), words=words, missed=missed, extra=extra,
    )

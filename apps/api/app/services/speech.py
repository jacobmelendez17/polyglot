"""Speech-scoring provider seam (spec §7, §33).

The spec is explicit: use browser-native recognition for the MVP, but build the
system so a third-party scorer can be swapped in later. This module is that seam.

A `SpeechScorer` takes a transcript and the expected phrase and returns an
`UtteranceScore`. The default `LocalScorer` uses the pure `domain.speech` engine —
it scores the transcript the browser already produced, needs no external service,
and never sees audio. `ExternalScorer` is a placeholder for a future provider
(e.g. an audio-in, phoneme-level service); it's registered but not wired, so the
seam is real and testable while the MVP stays fully local.

Selection is by name via `get_scorer()`, defaulting to the `SPEECH_PROVIDER`
environment variable (default "local"). Switching providers later is a config
change plus one adapter — not a rewrite of the practice flow.
"""
from __future__ import annotations

import os
from typing import Protocol, runtime_checkable

from app.domain.speech import UtteranceScore, score_utterance


class SpeechProviderNotConfigured(RuntimeError):
    """Raised when a provider is selected but has no working configuration."""


@runtime_checkable
class SpeechScorer(Protocol):
    def score(self, transcript: str, expected: str,
              accepted: list[str] | None = None) -> UtteranceScore: ...


class LocalScorer:
    """MVP default. Scores the browser-produced transcript with the pure engine."""

    name = "local"

    def score(self, transcript: str, expected: str,
              accepted: list[str] | None = None) -> UtteranceScore:
        return score_utterance(transcript, expected, accepted)


class ExternalScorer:
    """Seam for a future third-party service (audio-in, phoneme-level).

    Deliberately not wired for the MVP: calling it without configuration raises a
    clear error rather than silently degrading, so the swap point is explicit.
    A real adapter would call the provider here and map its response onto
    `UtteranceScore`.
    """

    name = "external"

    def score(self, transcript: str, expected: str,
              accepted: list[str] | None = None) -> UtteranceScore:
        raise SpeechProviderNotConfigured(
            "The external speech provider isn't configured. Set SPEECH_PROVIDER=local "
            "for the browser-native MVP path, or add the provider adapter."
        )


_REGISTRY: dict[str, type] = {
    "local": LocalScorer,
    "external": ExternalScorer,
}


def get_scorer(name: str | None = None) -> SpeechScorer:
    key = (name or os.getenv("SPEECH_PROVIDER") or "local").strip().lower()
    scorer_cls = _REGISTRY.get(key, LocalScorer)
    return scorer_cls()

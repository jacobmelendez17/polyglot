"""Speech provider seam — the swap point stays real and testable."""
import pytest

from app.domain.speech import UtteranceScore
from app.services.speech import (
    ExternalScorer,
    LocalScorer,
    SpeechProviderNotConfigured,
    SpeechScorer,
    get_scorer,
)


def test_default_is_the_local_scorer():
    scorer = get_scorer()
    assert isinstance(scorer, LocalScorer)
    assert isinstance(scorer, SpeechScorer)  # satisfies the protocol


def test_local_scorer_scores_via_the_pure_engine():
    result = get_scorer("local").score("hola mundo", "hola mundo")
    assert isinstance(result, UtteranceScore)
    assert result.score == 100 and result.passed


def test_env_var_selects_the_provider(monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "local")
    assert isinstance(get_scorer(), LocalScorer)


def test_unknown_provider_falls_back_to_local():
    assert isinstance(get_scorer("does-not-exist"), LocalScorer)


def test_external_provider_is_registered_but_not_configured():
    scorer = get_scorer("external")
    assert isinstance(scorer, ExternalScorer)
    # The seam is real: selecting it is fine, but using it without an adapter is a
    # clear, loud failure rather than a silent degrade.
    with pytest.raises(SpeechProviderNotConfigured):
        scorer.score("hola", "hola")

"""Audio resolution: stored assets beat browser speech, and the naming contract."""
from app.domain.audio import (
    AudioMode,
    BrowserSpeechProvider,
    StoredAsset,
    StoredAssetProvider,
    asset_storage_path,
    resolve_audio,
)


def test_stored_asset_wins_over_browser_speech():
    ref = resolve_audio(
        "hola",
        asset=StoredAsset("audio/vocabulary_1_es-MX_maria_1.mp3", "es-MX", "maria", "human"),
        base_url="https://cdn.example.com",
    )
    assert ref.mode is AudioMode.stored
    assert ref.url == "https://cdn.example.com/audio/vocabulary_1_es-MX_maria_1.mp3"
    assert ref.source == "human"


def test_browser_speech_is_the_fallback():
    ref = resolve_audio("hola")
    assert ref.mode is AudioMode.browser_tts
    assert ref.text == "hola"
    assert ref.locale == "es-MX"


def test_empty_text_is_unavailable():
    assert resolve_audio("").mode is AudioMode.unavailable
    assert resolve_audio("   ").mode is AudioMode.unavailable


def test_fallback_can_be_disabled():
    ref = resolve_audio("hola", allow_browser_fallback=False)
    assert ref.mode is AudioMode.unavailable


def test_relative_url_when_no_base_url():
    p = StoredAssetProvider()
    assert p.url_for("audio/x.mp3") == "/audio/x.mp3"
    assert p.url_for("/audio/x.mp3") == "/audio/x.mp3"


def test_base_url_trailing_slash_is_handled():
    p = StoredAssetProvider("https://cdn.example.com/")
    assert p.url_for("audio/x.mp3") == "https://cdn.example.com/audio/x.mp3"


def test_storage_path_follows_the_naming_contract():
    # {content_type}_{content_id}_{locale}_{voice}_{version}.{ext}  (PLANNING §33)
    path = asset_storage_path(
        content_type="vocabulary", content_id="abc123", locale="es-MX",
        voice_id="maria", version=2, ext="mp3",
    )
    assert path == "audio/vocabulary_abc123_es-MX_maria_2.mp3"


def test_browser_provider_trims_whitespace():
    ref = BrowserSpeechProvider().resolve("  hola  ", locale="es-MX")
    assert ref.text == "hola"


def test_audio_ref_serialises_for_the_api():
    d = resolve_audio("hola").to_dict()
    assert d["mode"] == "browser_tts"
    assert set(d) == {"mode", "text", "url", "locale", "voice_id", "source"}

"""Audio resolution — pure, provider-agnostic (PLANNING §33, R-16).

The question "how do I play this word?" has two possible answers:

  1. a stored asset  — a real file (curated TTS or a human recording) served
     from storage. Always preferred when it exists.
  2. browser speech  — the client's own speech synthesiser, used as the MVP
     fallback so listening works today with no vendor, key, or per-request cost.

Keeping this behind `resolve_audio` means adding a cloud TTS vendor later is a
new provider plus a row in audio_assets — no call site changes. It also means
human recordings can replace TTS gradually, item by item, with no migration:
the moment an asset exists, it wins.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class AudioMode(str, Enum):
    stored = "stored"           # play this URL
    browser_tts = "browser_tts"  # synthesise this text client-side
    unavailable = "unavailable"  # nothing to play


@dataclass(frozen=True)
class AudioRef:
    """Everything the client needs to produce sound for one item."""
    mode: AudioMode
    text: str = ""            # what to say (browser_tts)
    url: str | None = None    # where to fetch it (stored)
    locale: str = "es-MX"
    voice_id: str = ""
    source: str = ""          # tts | human, when known

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value, "text": self.text, "url": self.url,
            "locale": self.locale, "voice_id": self.voice_id, "source": self.source,
        }


@dataclass(frozen=True)
class StoredAsset:
    """The subset of an audio_assets row this module cares about."""
    storage_path: str
    locale: str
    voice_id: str = ""
    source: str = "tts"


class AudioProvider(Protocol):
    """A source of audio for a piece of text."""

    def resolve(self, text: str, *, locale: str, voice_id: str = "") -> AudioRef:
        ...


class StoredAssetProvider:
    """Serves a real file when one has been produced for this item."""

    def __init__(self, base_url: str = "") -> None:
        self.base_url = base_url.rstrip("/")

    def url_for(self, storage_path: str) -> str:
        path = storage_path.lstrip("/")
        return f"{self.base_url}/{path}" if self.base_url else f"/{path}"

    def resolve_asset(self, asset: StoredAsset) -> AudioRef:
        return AudioRef(
            mode=AudioMode.stored, url=self.url_for(asset.storage_path),
            locale=asset.locale, voice_id=asset.voice_id, source=asset.source,
        )

    def resolve(self, text: str, *, locale: str, voice_id: str = "") -> AudioRef:
        # Without an asset row there is nothing stored to serve.
        return AudioRef(mode=AudioMode.unavailable, text=text, locale=locale)


class BrowserSpeechProvider:
    """MVP: let the browser speak it.

    Free, keyless, and available in every current browser, which is what makes
    listening practice shippable now. Quality varies by platform, so stored
    assets always take precedence.
    """

    def resolve(self, text: str, *, locale: str, voice_id: str = "") -> AudioRef:
        clean = (text or "").strip()
        if not clean:
            return AudioRef(mode=AudioMode.unavailable, locale=locale)
        return AudioRef(
            mode=AudioMode.browser_tts, text=clean, locale=locale,
            voice_id=voice_id, source="tts",
        )


# Naming per PLANNING §33: {content_type}_{content_id}_{locale}_{voice}_{version}.{ext}
def asset_storage_path(
    *, content_type: str, content_id: str, locale: str,
    voice_id: str = "default", version: int = 1, ext: str = "mp3",
) -> str:
    return f"audio/{content_type}_{content_id}_{locale}_{voice_id}_{version}.{ext}"


def resolve_audio(
    text: str, *, locale: str = "es-MX", asset: StoredAsset | None = None,
    voice_id: str = "", base_url: str = "",
    allow_browser_fallback: bool = True,
) -> AudioRef:
    """Stored asset wins; otherwise fall back to browser speech."""
    if asset is not None:
        return StoredAssetProvider(base_url).resolve_asset(asset)
    if allow_browser_fallback:
        return BrowserSpeechProvider().resolve(text, locale=locale, voice_id=voice_id)
    return AudioRef(mode=AudioMode.unavailable, text=text, locale=locale)

"use client";

import { useEffect, useRef, useState } from "react";
import { type AudioRef, loadVoices, playAudio, speechSupported, stopSpeech } from "@/lib/speech";

/**
 * Play button for a prompt's audio. Renders nothing when there's nothing to
 * play, so callers can drop it in unconditionally.
 */
export function AudioButton({
  audio, autoPlay = false, size = "md", label = "play audio",
}: {
  audio: AudioRef | null | undefined;
  autoPlay?: boolean;
  size?: "sm" | "md" | "lg";
  label?: string;
}) {
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const autoPlayed = useRef<string | null>(null);

  useEffect(() => { loadVoices(); }, []);

  const key = audio ? `${audio.mode}:${audio.url ?? audio.text}` : null;

  useEffect(() => {
    // Autoplay once per prompt, never repeatedly on re-render.
    if (!autoPlay || !audio || !key || autoPlayed.current === key) return;
    autoPlayed.current = key;
    play();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, autoPlay]);

  useEffect(() => () => stopSpeech(), []);

  async function play() {
    if (!audio) return;
    setFailed(false);
    setPlaying(true);
    const ok = await playAudio(audio, {
      onEnd: () => setPlaying(false),
      onError: () => { setPlaying(false); setFailed(true); },
    });
    if (!ok) { setPlaying(false); setFailed(true); }
  }

  if (!audio || audio.mode === "unavailable") return null;
  if (audio.mode === "browser_tts" && !speechSupported()) return null;

  const dims = size === "lg" ? "h-16 w-16 text-2xl"
    : size === "sm" ? "h-8 w-8 text-sm"
    : "h-11 w-11 text-lg";

  return (
    <button
      type="button"
      onClick={play}
      aria-label={label}
      title={failed ? "audio unavailable" : label}
      className={`inline-flex items-center justify-center rounded-full bg-terraza-pill text-terraza-ink transition-transform hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink ${dims} ${
        playing ? "animate-pulse" : ""
      } ${failed ? "opacity-50" : ""}`}
    >
      {playing ? "◉" : "▶"}
    </button>
  );
}

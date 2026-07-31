// Browser speech-recognition hook (spec §33: browser-native recognition for the
// MVP, behind an abstraction). This hook is the client-side seam: it wraps the Web
// Speech API and hands back a plain transcript string. A future service-based
// recorder can replace this hook without changing the practice page — the page
// only consumes { supported, listening, transcript, start, stop, reset }.
//
// The audio never leaves the device: recognition happens in the browser and only
// the resulting text is submitted for scoring.

import { useCallback, useEffect, useRef, useState } from "react";

type Rec = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: unknown) => void) | null;
  onerror: ((e: unknown) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
};

function getRecognition(): Rec | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    (window as unknown as { SpeechRecognition?: new () => Rec }).SpeechRecognition ??
    (window as unknown as { webkitSpeechRecognition?: new () => Rec }).webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export interface SpeechRecognitionState {
  supported: boolean;
  listening: boolean;
  transcript: string;
  interim: string;
  error: string | null;
  start: () => void;
  stop: () => void;
  reset: () => void;
}

export function useSpeechRecognition(lang = "es-MX"): SpeechRecognitionState {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<Rec | null>(null);

  useEffect(() => {
    const rec = getRecognition();
    setSupported(!!rec);
    recRef.current = rec;
    return () => { try { rec?.abort(); } catch { /* noop */ } };
  }, []);

  const start = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    setError(null); setTranscript(""); setInterim("");
    rec.lang = lang;
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (e: unknown) => {
      const ev = e as { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> };
      let finalText = "";
      let interimText = "";
      for (let i = 0; i < ev.results.length; i++) {
        const res = ev.results[i];
        const text = res[0]?.transcript ?? "";
        if (res.isFinal) finalText += text;
        else interimText += text;
      }
      if (finalText) setTranscript((prev) => (prev ? `${prev} ${finalText}` : finalText).trim());
      setInterim(interimText);
    };
    rec.onerror = (e: unknown) => {
      const code = (e as { error?: string })?.error ?? "error";
      setError(
        code === "not-allowed" || code === "service-not-allowed"
          ? "microphone permission is blocked — check your browser settings."
          : code === "no-speech"
            ? "didn't catch that — try again."
            : "speech recognition hit a snag.",
      );
      setListening(false);
    };
    rec.onend = () => { setListening(false); setInterim(""); };
    try { rec.start(); setListening(true); }
    catch { /* already started */ }
  }, [lang]);

  const stop = useCallback(() => {
    try { recRef.current?.stop(); } catch { /* noop */ }
    setListening(false);
  }, []);

  const reset = useCallback(() => {
    setTranscript(""); setInterim(""); setError(null);
  }, []);

  return { supported, listening, transcript, interim, error, start, stop, reset };
}

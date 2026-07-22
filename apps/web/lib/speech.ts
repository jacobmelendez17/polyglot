// Speech playback for audio prompts.
//
// Two paths, matching what the API returns:
//   mode "stored"      → play a real recording (curated TTS or human audio)
//   mode "browser_tts" → synthesise with the browser's own speech engine
//
// Browser speech is the MVP: free, keyless, works offline, and available in
// every current browser. When real recordings land, the API starts returning
// "stored" and this file needs no changes.

export interface AudioRef {
  mode: "stored" | "browser_tts" | "unavailable";
  text: string;
  url: string | null;
  locale: string;
  voice_id: string;
  source: string;
}

let cachedVoices: SpeechSynthesisVoice[] = [];

export function speechSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Voices load asynchronously in most browsers, so refresh the cache on demand. */
export function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!speechSupported()) return Promise.resolve([]);
  const existing = window.speechSynthesis.getVoices();
  if (existing.length) {
    cachedVoices = existing;
    return Promise.resolve(existing);
  }
  return new Promise((resolve) => {
    const done = () => {
      cachedVoices = window.speechSynthesis.getVoices();
      resolve(cachedVoices);
    };
    window.speechSynthesis.addEventListener("voiceschanged", done, { once: true });
    // Some browsers never fire the event if voices are already warm.
    setTimeout(done, 600);
  });
}

/** Prefer a Mexican/LatAm Spanish voice, then any Spanish, then nothing. */
export function pickVoice(
  voices: SpeechSynthesisVoice[], locale = "es-MX", preferredName = "",
): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  if (preferredName) {
    const named = voices.find((v) => v.name === preferredName);
    if (named) return named;
  }
  const exact = voices.find((v) => v.lang.replace("_", "-") === locale);
  if (exact) return exact;
  const langOnly = locale.split("-")[0];
  const latam = voices.find(
    (v) => v.lang.startsWith(langOnly) && /MX|US|419|LA/i.test(v.lang),
  );
  if (latam) return latam;
  return voices.find((v) => v.lang.startsWith(langOnly)) ?? null;
}

export interface SpeakOptions {
  rate?: number;
  preferredVoice?: string;
  onEnd?: () => void;
  onError?: () => void;
}

let currentAudio: HTMLAudioElement | null = null;

/** Stop anything currently playing. Called before every new prompt. */
export function stopSpeech(): void {
  if (speechSupported()) window.speechSynthesis.cancel();
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
}

/** Play an AudioRef. Resolves false when nothing could be played. */
export async function playAudio(
  ref: AudioRef | null | undefined, opts: SpeakOptions = {},
): Promise<boolean> {
  if (!ref || ref.mode === "unavailable") return false;
  stopSpeech();

  if (ref.mode === "stored" && ref.url) {
    try {
      const el = new Audio(ref.url);
      currentAudio = el;
      el.onended = () => opts.onEnd?.();
      el.onerror = () => opts.onError?.();
      await el.play();
      return true;
    } catch {
      opts.onError?.();
      return false;
    }
  }

  if (ref.mode === "browser_tts") {
    if (!speechSupported()) {
      opts.onError?.();
      return false;
    }
    const voices = cachedVoices.length ? cachedVoices : await loadVoices();
    const utter = new SpeechSynthesisUtterance(ref.text);
    utter.lang = ref.locale || "es-MX";
    utter.rate = opts.rate ?? 1;
    const voice = pickVoice(voices, utter.lang, opts.preferredVoice ?? ref.voice_id);
    if (voice) utter.voice = voice;
    utter.onend = () => opts.onEnd?.();
    utter.onerror = () => opts.onError?.();
    window.speechSynthesis.speak(utter);
    return true;
  }
  return false;
}

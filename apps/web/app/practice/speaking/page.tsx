"use client";

// Speaking practice (spec §7, §33). Say the phrase; the browser transcribes it and
// only the text is scored — no audio leaves the device. When speech recognition
// isn't available (or the mic is blocked), a typed fallback keeps the exercise
// usable. Word-level feedback never relies on colour alone (a ✓/· marker carries
// the meaning too); animations respect reduced-motion; the prompt has a replay
// (text-to-speech) control.

import { useMemo, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { speaking, type SpeakingPrompt, type UtteranceScore } from "@/lib/speech-api";
import { useSpeechRecognition } from "@/lib/use-speech-recognition";

type Phase = "loading" | "empty" | "practice" | "error" | "done";

export default function SpeakingPracticePage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-10">
        <Speaking />
      </main>
    </Protected>
  );
}

function useLoadPrompts() {
  const [phase, setPhase] = useState<Phase>("loading");
  const [prompts, setPrompts] = useState<SpeakingPrompt[]>([]);
  const load = useMemo(
    () => async () => {
      setPhase("loading");
      try {
        const r = await speaking.start();
        if (!r.prompts.length) { setPhase("empty"); return; }
        setPrompts(r.prompts); setPhase("practice");
      } catch { setPhase("error"); }
    },
    [],
  );
  return { phase, setPhase, prompts, load };
}

function Speaking() {
  const { phase, setPhase, prompts, load } = useLoadPrompts();
  const [started, setStarted] = useState(false);
  const [i, setI] = useState(0);

  if (!started) {
    return (
      <Card>
        <h1 className="text-2xl lowercase tracking-cozy">speaking practice</h1>
        <p className="mt-3 text-terraza-soft">
          say each phrase out loud. your device transcribes it and we score how close
          you were — the audio never leaves your browser. no microphone? you can type
          instead.
        </p>
        <Button className="mt-6" onClick={() => { setStarted(true); load(); }}>
          start
        </Button>
      </Card>
    );
  }

  if (phase === "loading") {
    return <Card><p className="font-empty italic text-terraza-soft">un momento ~</p></Card>;
  }
  if (phase === "empty") {
    return (
      <Card>
        <p className="font-empty italic text-terraza-soft">
          learn a few words first — speaking practice draws from what you already know.
        </p>
      </Card>
    );
  }
  if (phase === "error") {
    return (
      <Card>
        <p role="alert" className="text-terraza-danger">couldn&apos;t load speaking practice.</p>
        <Button className="mt-4" onClick={load}>try again</Button>
      </Card>
    );
  }
  if (phase === "done") {
    return (
      <Card>
        <p className="text-lg lowercase tracking-cozy">¡bien hecho! ✦</p>
        <p className="mt-2 text-terraza-soft">that&apos;s the batch. come back for more anytime.</p>
      </Card>
    );
  }

  const prompt = prompts[i];
  return (
    <div>
      <div className="mb-4 flex items-baseline text-xs tracking-label text-terraza-soft">
        <span>SPEAKING</span>
        <span className="ml-auto">{i + 1} / {prompts.length}</span>
      </div>
      <PromptCard
        key={prompt.idx}
        prompt={prompt}
        onNext={() => {
          if (i + 1 < prompts.length) setI(i + 1);
          else setPhase("done");
        }}
      />
    </div>
  );
}

function PromptCard({ prompt, onNext }: { prompt: SpeakingPrompt; onNext: () => void }) {
  const rec = useSpeechRecognition("es-MX");
  const [typed, setTyped] = useState("");
  const [result, setResult] = useState<UtteranceScore | null>(null);
  const [busy, setBusy] = useState(false);
  const [showHint, setShowHint] = useState(false);

  function play() {
    try {
      const u = new SpeechSynthesisUtterance(prompt.prompt);
      u.lang = "es-MX";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch { /* TTS unavailable — the text is shown regardless */ }
  }

  async function submit(transcript: string) {
    if (!transcript.trim()) return;
    setBusy(true);
    try {
      const r = await speaking.score({
        item_type: prompt.item_type, item_id: prompt.item_id,
        transcript, idempotency_key: crypto.randomUUID(),
      });
      setResult(r);
    } catch {
      setResult(null);
    } finally { setBusy(false); }
  }

  const heard = rec.transcript || typed;

  return (
    <Card>
      <div className="text-center">
        <p className="text-sm text-terraza-soft">say this out loud</p>
        <p className="mt-2 text-3xl lowercase tracking-cozy" lang="es">{prompt.prompt}</p>
        <button onClick={play}
          className="mt-2 rounded-full bg-terraza-pill px-4 py-1 text-sm tracking-cozy"
          aria-label="Hear the phrase">
          🔊 hear it
        </button>
        <div className="mt-1">
          <button onClick={() => setShowHint((h) => !h)}
            className="text-xs text-terraza-soft underline">
            {showHint ? prompt.hint || "—" : "show meaning"}
          </button>
        </div>
      </div>

      {!result && (
        <div className="mt-6">
          {rec.supported ? (
            <div className="text-center">
              <button
                onClick={() => (rec.listening ? rec.stop() : rec.start())}
                disabled={busy}
                aria-pressed={rec.listening}
                className={`rounded-full px-6 py-3 text-lg tracking-cozy ${
                  rec.listening ? "bg-terraza-danger text-white" : "bg-terraza-accent text-terraza-accentInk"
                }`}
              >
                {rec.listening ? "◼ stop" : "● record"}
              </button>
              <p className="mt-3 min-h-[1.5rem] text-terraza-soft" aria-live="polite">
                {rec.listening
                  ? (rec.interim || "listening…")
                  : rec.transcript
                    ? `heard: "${rec.transcript}"`
                    : "tap record and say the phrase"}
              </p>
              {rec.error && <p role="alert" className="text-sm text-terraza-danger">{rec.error}</p>}
            </div>
          ) : (
            <div>
              <p className="mb-2 text-sm text-terraza-soft">
                speech recognition isn&apos;t available here — type what you&apos;d say instead.
              </p>
              <input
                value={typed} onChange={(e) => setTyped(e.target.value)}
                lang="es" maxLength={1000} placeholder="type the phrase…"
                className="w-full rounded-card border border-terraza-dash bg-terraza-bg px-4 py-3"
              />
            </div>
          )}

          <div className="mt-4 flex justify-center gap-3">
            <Button onClick={() => submit(heard)} disabled={busy || !heard.trim()}>
              {busy ? "scoring…" : "check"}
            </Button>
            {rec.supported && rec.transcript && (
              <button onClick={rec.reset}
                className="rounded-full px-5 py-2 text-sm text-terraza-soft hover:bg-terraza-pill">
                redo
              </button>
            )}
          </div>
        </div>
      )}

      {result && <Feedback result={result} onNext={onNext} />}
    </Card>
  );
}

function Feedback({ result, onNext }: { result: UtteranceScore; onNext: () => void }) {
  return (
    <div className="mt-6">
      <div className="text-center">
        <p className="text-4xl lowercase tracking-cozy">{result.score}<span className="text-lg text-terraza-soft">/100</span></p>
        <p className={`mt-1 lowercase tracking-cozy ${result.passed ? "text-terraza-green" : "text-terraza-soft"}`}>
          {result.passed ? "✓ nailed it" : "· not quite — give it another go sometime"}
        </p>
      </div>

      <p className="mt-4 flex flex-wrap justify-center gap-x-2 gap-y-1">
        {result.words.map((w, idx) => (
          <span key={idx} className={w.matched ? "text-terraza-ink" : "text-terraza-soft line-through decoration-terraza-danger"}>
            <span aria-hidden="true">{w.matched ? "✓" : "·"}</span> {w.word}
          </span>
        ))}
      </p>
      {result.extra.length > 0 && (
        <p className="mt-2 text-center text-xs text-terraza-soft">
          extra words heard: {result.extra.join(", ")}
        </p>
      )}
      {result.xp_awarded > 0 && (
        <p className="mt-2 text-center text-sm text-terraza-green">+{result.xp_awarded} xp{result.perfect ? " · perfect ✦" : ""}</p>
      )}

      <div className="mt-6 flex justify-center">
        <Button onClick={onNext}>next →</Button>
      </div>
    </div>
  );
}

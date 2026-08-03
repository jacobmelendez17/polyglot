"use client";

// Test runner (spec §7): audio (TTS on the caption for now) + caption, a question,
// four options; pick one, see if it was right, then next. Results at the end.
// Keyboard-operable options; feedback never relies on colour alone (a ✓/✗ marker
// carries the meaning too). Loading / empty / error states throughout.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import {
  testing,
  type AnswerResult,
  type CompleteResult,
  type TestQuestion,
} from "@/lib/testing-api";

type Phase = "intro" | "loading" | "empty" | "error" | "running" | "done";

export default function TestRunnerPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-8">
        <Runner />
      </main>
    </Protected>
  );
}

function Runner() {
  const { map } = useParams<{ map: string }>();
  const [phase, setPhase] = useState<Phase>("intro");
  const [attemptId, setAttemptId] = useState("");
  const [questions, setQuestions] = useState<TestQuestion[]>([]);
  const [i, setI] = useState(0);
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [summary, setSummary] = useState<CompleteResult | null>(null);
  const [busy, setBusy] = useState(false);

  const start = useMemo(() => async () => {
    setPhase("loading");
    try {
      const r = await testing.start(map);
      if (!r.questions.length) { setPhase("empty"); return; }
      setAttemptId(r.attempt_id); setQuestions(r.questions);
      setI(0); setResult(null); setPicked(null);
      setPhase("running");
    } catch { setPhase("error"); }
  }, [map]);

  function play(caption: string) {
    try {
      const u = new SpeechSynthesisUtterance(caption);
      u.lang = "es-MX";
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(u);
    } catch { /* TTS unavailable — the caption is shown anyway */ }
  }

  async function choose(idx: number) {
    if (result || busy) return;
    setPicked(idx); setBusy(true);
    try {
      setResult(await testing.answer(attemptId, questions[i].id, idx, crypto.randomUUID()));
    } catch { setPicked(null); } finally { setBusy(false); }
  }

  async function next() {
    if (i + 1 < questions.length) {
      setI(i + 1); setResult(null); setPicked(null);
    } else {
      setBusy(true);
      try { setSummary(await testing.complete(attemptId)); setPhase("done"); }
      finally { setBusy(false); }
    }
  }

  if (phase === "intro")
    return (
      <Card>
        <Link href="/tests" className="text-sm text-terraza-accent">← testing</Link>
        <h1 className="mt-2 text-2xl lowercase tracking-cozy">{map} test</h1>
        <p className="mt-2 text-terraza-soft">
          you&apos;ll hear a short clip, read a question, and pick from four answers.
        </p>
        <Button className="mt-4" onClick={start}>start</Button>
      </Card>
    );
  if (phase === "loading")
    return <Card><p className="font-empty italic text-terraza-soft">un momento ~</p></Card>;
  if (phase === "empty")
    return (
      <Card>
        <p className="font-empty italic text-terraza-soft">
          no questions here yet{map === "app" ? " — learn a level first" : ""}.
        </p>
        <Link href="/tests" className="mt-3 inline-block text-sm text-terraza-accent">← back</Link>
      </Card>
    );
  if (phase === "error")
    return (
      <Card>
        <p role="alert" className="text-terraza-danger">couldn&apos;t start the test.</p>
        <Button className="mt-3" onClick={start}>try again</Button>
      </Card>
    );
  if (phase === "done" && summary)
    return (
      <Card className="text-center">
        <p className="text-4xl tracking-cozy">{summary.score}<span className="text-lg text-terraza-soft">/{summary.total}</span></p>
        <p className="mt-1 lowercase tracking-cozy text-terraza-green">{summary.percentage}% ✦</p>
        <p className="mt-2 text-terraza-soft">nice work on the {summary.map} map.</p>
        <div className="mt-4 flex justify-center gap-3">
          <Button onClick={start}>again</Button>
          <Link href="/tests"><button className="rounded-full px-5 py-2 text-sm text-terraza-soft hover:bg-terraza-pill">other maps</button></Link>
        </div>
      </Card>
    );

  const q = questions[i];
  return (
    <div>
      <div className="mb-4 flex items-baseline text-xs tracking-label text-terraza-soft">
        <span>{map.toUpperCase()}</span>
        <span className="ml-auto">{i + 1} / {questions.length}</span>
      </div>
      <Card>
        {q.caption && (
          <div className="mb-4 rounded-card bg-terraza-pill p-3 text-center">
            <p lang="es" className="text-terraza-ink">{q.caption}</p>
            <button onClick={() => play(q.caption)}
              className="mt-1 text-sm text-terraza-accent" aria-label="Play audio">🔊 play</button>
          </div>
        )}
        <p className="text-lg tracking-cozy">{q.stem}</p>

        <div className="mt-4 flex flex-col gap-2">
          {q.options.map((o, idx) => {
            const isPicked = picked === idx;
            const isAnswer = result && idx === result.correct_index;
            const state = !result ? "idle" : isAnswer ? "right" : isPicked ? "wrong" : "idle";
            return (
              <button key={idx} onClick={() => choose(idx)} disabled={!!result || busy}
                className={`flex items-center gap-2 rounded-card border px-4 py-3 text-left tracking-cozy transition-colors ${
                  state === "right" ? "border-terraza-green bg-terraza-green/10"
                  : state === "wrong" ? "border-terraza-danger bg-terraza-danger/10"
                  : "border-terraza-dash hover:bg-terraza-pill"}`}>
                <span aria-hidden="true" className="w-4 shrink-0">
                  {state === "right" ? "✓" : state === "wrong" ? "✗" : ""}
                </span>
                <span lang="es">{o.text}</span>
              </button>
            );
          })}
        </div>

        {result && (
          <div className="mt-4">
            <p className={result.correct ? "text-terraza-green" : "text-terraza-soft"}>
              {result.correct ? "✓ correct" : "✗ not quite"}
              {result.xp_awarded > 0 && <span className="text-terraza-green"> · +{result.xp_awarded} xp</span>}
            </p>
            {result.explanation && <p className="mt-1 text-sm text-terraza-soft">{result.explanation}</p>}
            <div className="mt-4 flex justify-end">
              <Button onClick={next} disabled={busy}>
                {i + 1 < questions.length ? "next →" : "finish"}
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

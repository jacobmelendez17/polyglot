"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, Input } from "@/components/ui";
import {
  newKey, practice, PRACTICE_MODES,
  type PracticeGrade, type PracticePrompt, type PracticeSession,
} from "@/lib/learn-api";

type Phase = "loading" | "asking" | "feedback" | "done" | "empty" | "error";

export default function PracticePage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-8">
        <PracticeRunner />
      </main>
    </Protected>
  );
}

function PracticeRunner() {
  const params = useParams();
  const mode = String(params.mode);
  const meta = PRACTICE_MODES.find((m) => m.id === mode);

  const [session, setSession] = useState<PracticeSession | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [grade, setGrade] = useState<PracticeGrade | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [xp, setXp] = useState(0);
  const [correct, setCorrect] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    practice.start(mode)
      .then((s) => { setSession(s); setPhase(s.prompts.length ? "asking" : "empty"); })
      .catch((e) => { setError(e.message); setPhase("error"); });
  }, [mode]);

  useEffect(() => { if (phase === "asking") inputRef.current?.focus(); }, [phase, index]);

  const prompt: PracticePrompt | null = session?.prompts[index] ?? null;

  const submit = useCallback(async () => {
    if (!session || !prompt || !answer.trim()) return;
    try {
      const g = await practice.answer(session.session_id, {
        item_type: prompt.item_type, item_id: prompt.item_id, mode, answer,
        tense: prompt.tense ?? null, person: prompt.person ?? null,
        idempotency_key: newKey(),
      });
      setGrade(g);
      setPhase("feedback");
      if (g.correct) setCorrect((c) => c + 1);
      if (g.xp_awarded) setXp((x) => x + g.xp_awarded);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit.");
    }
  }, [session, prompt, answer, mode]);

  const next = useCallback(() => {
    setAnswer(""); setGrade(null);
    if (!session) return;
    if (index + 1 >= session.prompts.length) {
      practice.finish(session.session_id).catch(() => {});
      setPhase("done");
    } else {
      setIndex((i) => i + 1);
      setPhase("asking");
    }
  }, [index, session]);

  if (phase === "loading") return <p className="mt-10 text-center font-empty italic text-terraza-soft">un momento ~</p>;
  if (phase === "error") return <Card><p className="text-terraza-danger">{error}</p></Card>;
  if (phase === "empty") {
    return (
      <Card className="text-center">
        <p className="font-empty italic text-terraza-soft">nothing to practice here yet ~</p>
        <p className="mt-2 text-sm text-terraza-soft">
          {mode === "conjugation"
            ? "learn some verbs first, then come back to conjugate them."
            : mode === "fill_blank"
            ? "this needs example sentences on your learned words."
            : "learn a few lessons first, then practice what gives you trouble."}
        </p>
        <Link href="/practice" className="mt-5 inline-block rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">
          ← other practice
        </Link>
      </Card>
    );
  }
  if (phase === "done") {
    const total = session?.prompts.length ?? 0;
    return (
      <Card className="text-center">
        <p className="text-2xl lowercase tracking-cozy">¡práctica completa! ✦</p>
        <p className="mt-3 text-terraza-soft">{correct} / {total} correct · +{xp} XP</p>
        <div className="mt-5 flex justify-center gap-3">
          <Link href="/practice" className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">more practice</Link>
          <Link href="/dashboard" className="rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">dashboard</Link>
        </div>
      </Card>
    );
  }

  const total = session?.prompts.length ?? 0;
  return (
    <>
      <Link href="/practice" className="text-sm text-terraza-soft">← practice</Link>
      <div className="mb-6 mt-2">
        <div className="h-2 overflow-hidden rounded-full bg-terraza-pill">
          <div className="h-full rounded-full bg-terraza-accent transition-all"
               style={{ width: `${(index / total) * 100}%` }} />
        </div>
        <div className="mt-2 flex text-xs tracking-label text-terraza-soft">
          <span>{meta?.title} · {index + 1} / {total}</span>
          <span className="ml-auto">+{xp} XP</span>
        </div>
      </div>

      <Card className="text-center">
        <span className="text-xs tracking-label text-terraza-soft">
          {mode === "conjugation" ? "CONJUGATE"
            : mode === "fill_blank" ? "FILL THE BLANK"
            : mode === "listening" ? "WHAT DID YOU HEAR?"
            : "TRANSLATE"}
        </span>

        {mode === "listening" ? (
          // The word is deliberately never shown — listening is the whole test.
          <div className="mt-6 flex flex-col items-center gap-3">
            <AudioButton audio={prompt?.audio} size="lg" autoPlay label="hear the word again" />
            <p className="text-sm text-terraza-soft">tap to replay</p>
          </div>
        ) : (
          <>
            <p className="mt-5 text-2xl lowercase tracking-cozy">{prompt?.shown}</p>
            {prompt?.translation && mode !== "conjugation" && (
              <p className="mt-2 text-sm text-terraza-soft">({prompt.translation})</p>
            )}
          </>
        )}

        {phase === "asking" ? (
          <div className="mt-6">
            <Input ref={inputRef} value={answer} onChange={(e) => setAnswer(e.target.value)}
                   onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
                   placeholder={mode === "listening" ? "type what you heard…" : "escribe en español…"}
                   autoComplete="off" autoCorrect="off"
                   autoCapitalize="off" spellCheck={false} aria-label="Your answer" />
            <Button onClick={submit} disabled={!answer.trim()} className="mt-4">check</Button>
          </div>
        ) : (
          <div className="mt-6">
            <div className={`rounded-[14px] px-4 py-3 ${grade?.correct ? "bg-terraza-green" : "bg-terraza-pink"}`}>
              <p className="tracking-cozy">{grade?.correct ? "¡correcto! ✦" : "not quite"}</p>
              {(!grade?.correct || mode === "listening") && (
                <p className="mt-1 text-sm">
                  {grade?.correct ? "you heard: " : "answer: "}
                  <span className="tracking-cozy">{grade?.expected}</span>
                </p>
              )}
              {mode === "listening" && prompt?.translation && (
                <p className="mt-1 text-sm">({prompt.translation})</p>
              )}
              {grade?.perfect && <p className="mt-1 text-sm">perfect status reached! ✦</p>}
            </div>
            <Button onClick={next} className="mt-5">continue →</Button>
          </div>
        )}
      </Card>
    </>
  );
}


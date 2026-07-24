"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, Input } from "@/components/ui";
import {
  learn, newKey, STAGE_NAMES, type AnswerResult, type Prompt, type Session,
} from "@/lib/learn-api";
import { useEnterAdvance } from "@/lib/use-enter-advance";

type Phase = "loading" | "asking" | "feedback" | "done" | "empty" | "error";

export default function ReviewsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-8">
        <ReviewSession />
      </main>
    </Protected>
  );
}

function ReviewSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState<AnswerResult | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [xp, setXp] = useState(0);
  const [correct, setCorrect] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    learn.startSession()
      .then((s) => {
        setSession(s);
        setPhase(s.prompts.length ? "asking" : "empty");
      })
      .catch((e) => { setError(e.message); setPhase("error"); });
  }, []);

  useEffect(() => {
    if (phase === "asking") inputRef.current?.focus();
  }, [phase, index]);

  const prompt: Prompt | null = session?.prompts[index] ?? null;

  const submit = useCallback(async () => {
    // The guard matters now that Enter submits: two fast keystrokes would
    // otherwise post two answers with two different idempotency keys.
    if (!session || !prompt || !answer.trim() || submitting) return;
    setSubmitting(true);
    try {
      const r = await learn.submit(session.session_id, {
        item_type: prompt.item_type, item_id: prompt.item_id,
        direction: prompt.direction, answer, idempotency_key: newKey(),
      });
      setResult(r);
      setPhase("feedback");
      if (r.final_correct) setCorrect((c) => c + 1);
      if (r.xp_awarded) setXp((x) => x + r.xp_awarded);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit your answer.");
    } finally {
      setSubmitting(false);
    }
  }, [session, prompt, answer, submitting]);

  const next = useCallback(() => {
    setAnswer("");
    setResult(null);
    if (!session) return;
    if (index + 1 >= session.prompts.length) {
      learn.finishSession(session.session_id).catch(() => {});
      setPhase("done");
    } else {
      setIndex((i) => i + 1);
      setPhase("asking");
    }
  }, [index, session]);

  // Enter answers, then Enter again continues.
  useEnterAdvance({ active: phase === "feedback", onAdvance: next });

  async function undo() {
    if (!result?.answer_id) return;
    await learn.undo(result.answer_id, "marked correct by user");
    setResult({ ...result, final_correct: true });
    setCorrect((c) => c + 1);
  }

  if (phase === "loading") {
    return <p className="mt-10 text-center font-empty italic text-terraza-soft">un momento ~</p>;
  }
  if (phase === "error") {
    return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  }
  if (phase === "empty") {
    return (
      <Card className="text-center">
        <p className="font-empty italic text-terraza-soft">nothing due right now ~</p>
        <p className="mt-2 text-sm text-terraza-soft">
          reviews appear on a schedule. finish a lesson to add more items.
        </p>
        <Link href="/levels"
          className="mt-5 inline-block rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
          browse levels
        </Link>
      </Card>
    );
  }
  if (phase === "done") {
    const total = session?.prompts.length ?? 0;
    return (
      <Card className="text-center">
        <p className="text-2xl lowercase tracking-cozy">¡sesión completa! ✦</p>
        <p className="mt-3 text-terraza-soft">
          {correct} / {total} correct · +{xp} XP
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <Link href="/dashboard"
            className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">dashboard</Link>
          <button onClick={() => window.location.reload()}
            className="rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
            review more
          </button>
        </div>
      </Card>
    );
  }

  const total = session?.prompts.length ?? 0;
  const askingSpanish = prompt?.direction === "en_to_es";

  return (
    <>
      <div className="mb-6">
        <div className="h-2 overflow-hidden rounded-full bg-terraza-pill">
          <div className="h-full rounded-full bg-terraza-accent transition-all motion-reduce:transition-none"
               style={{ width: `${(index / total) * 100}%` }} />
        </div>
        <div className="mt-2 flex text-xs tracking-label text-terraza-soft">
          <span>{index + 1} / {total}</span>
          <span className="ml-auto">+{xp} XP</span>
        </div>
      </div>

      <Card className="text-center">
        <span className="text-xs tracking-label text-terraza-soft">
          {askingSpanish ? "TYPE IT IN SPANISH" : "TYPE IT IN ENGLISH"}
          {prompt && prompt.srs_stage >= 5 && (
            <span className="ml-2 rounded-full bg-terraza-gold px-2 py-0.5">
              {STAGE_NAMES[prompt.srs_stage]}
            </span>
          )}
        </span>

        <div className="mt-5 flex items-center justify-center gap-3">
          <p className="text-3xl lowercase tracking-cozy">{prompt?.shown}</p>
          {/* Only offer audio for the Spanish side — hearing the English is no help. */}
          {prompt?.direction === "es_to_en" && (
            <AudioButton audio={prompt?.audio} label="hear this word" />
          )}
        </div>
        {prompt?.article && (
          <p className="mt-1 text-sm text-terraza-soft">include the article</p>
        )}
        {prompt?.part_of_speech && (
          <p className="mt-1 text-xs tracking-label text-terraza-soft">
            {prompt.part_of_speech.toUpperCase()}
          </p>
        )}

        {phase === "asking" ? (
          <div className="mt-6">
            <Input
              ref={inputRef}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submit(); } }}
              placeholder={askingSpanish ? "escribe en español…" : "type in english…"}
              autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck={false}
              aria-label="Your answer"
              aria-describedby="answer-hint"
              disabled={submitting}
            />
            <Button onClick={submit} disabled={!answer.trim() || submitting} className="mt-4">
              {submitting ? "checking…" : "check"}
            </Button>
            <p id="answer-hint" className="mt-3 text-xs text-terraza-soft">
              press enter to check
            </p>
          </div>
        ) : (
          <Feedback result={result!} onNext={next} onUndo={undo} />
        )}
      </Card>

      <p className="mt-4 text-center text-sm text-terraza-soft">
        <Link href="/dashboard" className="underline underline-offset-2">exit session</Link>
        {" · "}unfinished pairs keep their current stage
      </p>
    </>
  );
}

function Feedback({
  result, onNext, onUndo,
}: { result: AnswerResult; onNext: () => void; onUndo: () => void }) {
  const ok = result.final_correct;
  return (
    <div className="mt-6">
      <div
        role="status"
        aria-live="polite"
        className={`rounded-[14px] px-4 py-3 ${ok ? "bg-terraza-green" : "bg-terraza-pink"}`}
      >
        <p className="tracking-cozy">{ok ? "¡correcto! ✦" : "not quite"}</p>
        {!ok && (
          <p className="mt-1 text-sm">
            answer: <span className="tracking-cozy">{result.expected}</span>
          </p>
        )}
        {result.message && <p className="mt-1 text-sm">{result.message}</p>}
        {result.warnings.includes("missing_accent") && ok && (
          <p className="mt-1 text-sm">watch the accent: {result.expected}</p>
        )}
        {result.typo_forgiven && (
          <p className="mt-1 text-sm">close enough — the spelling is {result.expected}</p>
        )}
        {result.synonym_matched && <p className="mt-1 text-sm">that works too ✦</p>}
      </div>

      {result.pair_resolved && result.srs_stage_after != null && (
        <p className="mt-3 text-sm text-terraza-soft">
          {result.srs_stage_after > (result.srs_stage_before ?? 0)
            ? `↑ ${STAGE_NAMES[result.srs_stage_after]}`
            : `↓ ${STAGE_NAMES[result.srs_stage_after]}`}
          {result.xp_awarded ? ` · +${result.xp_awarded} XP` : ""}
        </p>
      )}

      <div className="mt-5 flex justify-center gap-3">
        {!ok && result.answer_id && (
          <button onClick={onUndo}
            className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy">
            i was right (undo)
          </button>
        )}
        <Button onClick={onNext} aria-keyshortcuts="Enter">continue →</Button>
      </div>

      <p className="mt-3 text-xs text-terraza-soft">press enter to continue</p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, Input } from "@/components/ui";
import {
  learn, newKey, quiz as quizApi,
  type LessonItem, type QuizPrompt, type QuizSession,
} from "@/lib/learn-api";

// Lesson flow, WaniKani-style:
//   teach the items  →  quiz on them  →  only then do they enter the SRS
type Phase = "loading" | "teaching" | "quiz" | "quizFeedback" | "done" | "error";

export default function LessonPage() {
  const params = useParams();
  const level = Number(params.level);
  const lesson = Number(params.lesson);

  const [items, setItems] = useState<LessonItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);

  // quiz state
  const [session, setSession] = useState<QuizSession | null>(null);
  const [queue, setQueue] = useState<QuizPrompt[]>([]);   // wrong answers cycle back
  const [answer, setAnswer] = useState("");
  const [lastResult, setLastResult] = useState<{ correct: boolean; expected: string } | null>(null);
  const [passed, setPassed] = useState(0);

  const [done, setDone] = useState<{ xp: number; unlocked: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [key] = useState(() => newKey());
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!level || !lesson) return;
    learn.lessonDetail(level, lesson)
      .then((d) => { setItems(d.items); setPhase("teaching"); })
      .catch((e) => { setError(e.message); setPhase("error"); });
  }, [level, lesson]);

  useEffect(() => { if (phase === "quiz") inputRef.current?.focus(); }, [phase, queue.length]);

  async function startQuiz() {
    try {
      const s = await quizApi.start(level, lesson);
      setSession(s);
      setQueue(s.prompts);
      setPassed(0);
      setPhase("quiz");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the quiz.");
      setPhase("error");
    }
  }

  async function submitQuiz() {
    if (!session || queue.length === 0 || !answer.trim()) return;
    const current = queue[0];
    try {
      const r = await quizApi.answer(session.session_id, {
        item_type: current.item_type, item_id: current.item_id,
        answer, idempotency_key: newKey(),
      });
      setLastResult({ correct: r.correct, expected: r.expected });
      setPhase("quizFeedback");
      if (r.correct) setPassed((p) => p + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not submit.");
    }
  }

  function nextQuiz() {
    const wasCorrect = lastResult?.correct;
    setAnswer("");
    setLastResult(null);
    setQueue((q) => {
      const [current, ...rest] = q;
      // Correct: it leaves the queue. Wrong: it goes to the back to try again.
      return wasCorrect ? rest : [...rest, current];
    });
    setPhase("quiz");
  }

  async function finish() {
    setSaving(true);
    try {
      const r = await learn.completeLesson(level, lesson, key);
      setDone({ xp: r.xp_awarded, unlocked: r.unlocked });
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your progress.");
      setSaving(false);
    }
  }

  // Quiz is finished when the retry queue empties.
  useEffect(() => {
    if (phase === "quiz" && session && queue.length === 0 && passed > 0) finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, queue.length, session, passed]);

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Link href={`/levels/${level}`} className="text-sm text-terraza-soft">← level {level}</Link>

        {error && <Card className="mt-4"><p className="text-terraza-danger">{error}</p></Card>}
        {phase === "loading" && <p className="mt-8 font-empty italic text-terraza-soft">un momento ~</p>}

        {phase === "done" && done && (
          <Card className="mt-6 text-center">
            <p className="text-2xl lowercase tracking-cozy">¡lección completa! ✦</p>
            <p className="mt-3 text-terraza-soft">
              +{done.xp} XP · {done.unlocked} items added to your reviews
            </p>
            <p className="mt-1 text-sm text-terraza-soft">
              your first review lands in about 4 hours.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <Link href={`/levels/${level}`} className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">
                back to level
              </Link>
              <Link href="/dashboard" className="rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
                dashboard
              </Link>
            </div>
          </Card>
        )}

        {/* ---- teaching phase ---- */}
        {phase === "teaching" && items && items.length > 0 && (
          <>
            <div className="mt-4 mb-6">
              <div className="h-2 overflow-hidden rounded-full bg-terraza-pill">
                <div className="h-full rounded-full bg-terraza-accent transition-all"
                     style={{ width: `${((index + 1) / items.length) * 100}%` }} />
              </div>
              <p className="mt-2 text-xs tracking-label text-terraza-soft">
                LEARNING · {index + 1} / {items.length}
              </p>
            </div>
            <ItemCard item={items[index]} />
            <div className="mt-6 flex justify-between">
              <button onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0}
                className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy disabled:opacity-40">
                ← back
              </button>
              {index < items.length - 1 ? (
                <Button onClick={() => setIndex((i) => i + 1)}>next →</Button>
              ) : (
                <Button onClick={startQuiz}>quiz me →</Button>
              )}
            </div>
          </>
        )}

        {/* ---- quiz phase ---- */}
        {(phase === "quiz" || phase === "quizFeedback") && queue.length > 0 && (
          <>
            <div className="mt-4 mb-6">
              <div className="h-2 overflow-hidden rounded-full bg-terraza-pill">
                <div className="h-full rounded-full bg-terraza-gold transition-all"
                     style={{ width: `${(passed / (passed + queue.length)) * 100}%` }} />
              </div>
              <p className="mt-2 text-xs tracking-label text-terraza-soft">
                QUIZ · {queue.length} left
              </p>
            </div>

            <Card className="text-center">
              <span className="text-xs tracking-label text-terraza-soft">WHAT DOES THIS MEAN?</span>
              <p className="mt-5 text-3xl lowercase tracking-cozy">{queue[0].shown}</p>
              {queue[0].hint && (
                <p className="mt-1 text-xs tracking-label text-terraza-soft">
                  {queue[0].hint.toUpperCase()}
                </p>
              )}

              {phase === "quiz" ? (
                <div className="mt-6">
                  <Input ref={inputRef} value={answer} onChange={(e) => setAnswer(e.target.value)}
                         onKeyDown={(e) => { if (e.key === "Enter") submitQuiz(); }}
                         placeholder="type the meaning in english…" autoComplete="off"
                         autoCorrect="off" autoCapitalize="off" spellCheck={false}
                         aria-label="Your answer" />
                  <Button onClick={submitQuiz} disabled={!answer.trim()} className="mt-4">check</Button>
                </div>
              ) : (
                <div className="mt-6">
                  <div className={`rounded-[14px] px-4 py-3 ${
                    lastResult?.correct ? "bg-terraza-green" : "bg-terraza-pink"}`}>
                    <p className="tracking-cozy">{lastResult?.correct ? "¡correcto! ✦" : "not quite"}</p>
                    {!lastResult?.correct && (
                      <>
                        <p className="mt-1 text-sm">
                          answer: <span className="tracking-cozy">{lastResult?.expected}</span>
                        </p>
                        <p className="mt-1 text-sm">we&apos;ll come back to this one.</p>
                      </>
                    )}
                  </div>
                  <Button onClick={nextQuiz} className="mt-5">continue →</Button>
                </div>
              )}
            </Card>
            <p className="mt-4 text-center text-sm text-terraza-soft">
              answer each item once to add it to your reviews
            </p>
          </>
        )}

        {saving && <p className="mt-6 text-center font-empty italic text-terraza-soft">guardando ~</p>}
      </main>
    </Protected>
  );
}

function ItemCard({ item }: { item: LessonItem }) {
  const isGrammar = item.item_type === "grammar";
  return (
    <Card className="text-center">
      <span className="text-xs tracking-label text-terraza-soft">
        {isGrammar ? "GRAMMAR" : (item.part_of_speech || "VOCABULARY").toUpperCase()}
      </span>
      <p className="mt-4 text-3xl lowercase tracking-cozy">
        {item.article ? <span className="text-terraza-soft">{item.article} </span> : null}
        {item.term}
      </p>
      <p className="mt-2 text-lg text-terraza-accent">{item.translation}</p>
      {item.pronunciation && (
        <p className="mt-3 text-sm text-terraza-soft">say it: {item.pronunciation}</p>
      )}
      {item.ipa && <p className="text-sm text-terraza-soft">/{item.ipa}/</p>}
      {item.structure && (
        <p className="mt-3 rounded-[12px] bg-terraza-bg px-3 py-2 text-sm">{item.structure}</p>
      )}
      {item.meaning && <p className="mt-3 text-sm text-terraza-soft">{item.meaning}</p>}
      {item.explanation && (
        <p className="mt-3 text-left text-sm text-terraza-soft">{item.explanation}</p>
      )}
    </Card>
  );
}

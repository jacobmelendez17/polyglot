"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, Input } from "@/components/ui";
import { items as itemsApi, type ExampleSentence } from "@/lib/items-api";
import {
  learn, newKey, quiz as quizApi,
  type LessonItem, type QuizPrompt, type QuizSession,
} from "@/lib/learn-api";
import { useEnterAdvance } from "@/lib/use-enter-advance";

// Lesson flow, WaniKani-style:
//   teach the items  →  quiz on them  →  only then do they enter the SRS
type Phase = "loading" | "teaching" | "quiz" | "quizFeedback" | "done" | "error";
type TabKey = "details" | "reading" | "examples";
const TABS: { key: TabKey; label: string }[] = [
  { key: "details", label: "details" },
  { key: "reading", label: "reading" },
  { key: "examples", label: "examples" },
];

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

  // teaching-phase card: tabs, examples (fetched per item), scroll state
  const [activeTab, setActiveTab] = useState<TabKey>("details");
  const [examples, setExamples] = useState<Record<string, ExampleSentence[]>>({});
  const [examplesLoading, setExamplesLoading] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const detailsRef = useRef<HTMLDivElement>(null);
  const readingRef = useRef<HTMLDivElement>(null);
  const examplesRef = useRef<HTMLDivElement>(null);
  const tabRefs = { details: detailsRef, reading: readingRef, examples: examplesRef };

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

  // Enter answers, then Enter again continues — same accelerator as reviews.
  useEnterAdvance({ active: phase === "quizFeedback", onAdvance: nextQuiz });

  function goBack() {
    setIndex((i) => Math.max(0, i - 1));
  }
  function goForward() {
    if (!items) return;
    if (index < items.length - 1) setIndex((i) => i + 1);
    else startQuiz();
  }

  // ←/→ mirror the back/next buttons exactly, including "next" becoming
  // "quiz me" on the last item. Only live during teaching — quiz has its own
  // check/continue flow (continue already gets Enter, above).
  useEffect(() => {
    if (phase !== "teaching" || !items) return;
    function onKey(e: KeyboardEvent) {
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); goBack(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); goForward(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, items, index]);

  // Examples are extra detail, not in the lesson payload — fetched per item and
  // cached so flipping back to an item already seen doesn't refetch.
  useEffect(() => {
    if (phase !== "teaching" || !items) return;
    const it = items[index];
    const k = `${it.item_type}:${it.item_id}`;
    if (examples[k] !== undefined) return;
    setExamplesLoading(true);
    itemsApi.detail(it.item_type as "vocabulary" | "grammar", it.item_id)
      .then((d) => setExamples((e) => ({ ...e, [k]: d.examples })))
      .catch(() => setExamples((e) => ({ ...e, [k]: [] })))
      .finally(() => setExamplesLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, items, index]);

  // A new item resets the tab, the scroll, and the mini-header/back-to-top state —
  // otherwise "next" could land you mid-scroll on unrelated content.
  useEffect(() => {
    if (phase !== "teaching") return;
    setActiveTab("details");
    setScrolled(false);
    window.scrollTo({ top: 0, behavior: "auto" });
  }, [index, phase]);

  // Mini-header + back-to-top appear once the pinned word/translation block has
  // scrolled past — the sentinel sits right below it.
  useEffect(() => {
    if (phase !== "teaching") return;
    const el = sentinelRef.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(([e]) => setScrolled(!e.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, [phase, index]);

  function goToTab(tab: TabKey) {
    setActiveTab(tab);
    tabRefs[tab].current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const teaching = phase === "teaching" && items && items.length > 0;
  const currentItem = items?.[index] ?? null;

  return (
    <Protected>
      <Header />

      {/* Appears once the word/translation block scrolls out of view — sticks
          at the top in the header's place. */}
      {teaching && scrolled && currentItem && (
        <div className="sticky top-0 z-30 border-b border-terraza-dash bg-terraza-bg/90 px-4 py-2 text-center backdrop-blur">
          <p className="tracking-cozy">
            {currentItem.term} <span className="text-terraza-soft">· {currentItem.translation}</span>
          </p>
        </div>
      )}

      <main className={`mx-auto max-w-2xl px-4 py-8 ${teaching ? "pb-28" : ""}`}>
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
        {teaching && items && (
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
            <ItemCard
              item={items[index]}
              examples={examples[`${items[index].item_type}:${items[index].item_id}`] ?? []}
              examplesLoading={examplesLoading}
              activeTab={activeTab}
              onTabClick={goToTab}
              sentinelRef={sentinelRef}
              detailsRef={detailsRef}
              readingRef={readingRef}
              examplesRef={examplesRef}
            />
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
              <div className="mt-5 flex items-center justify-center gap-3">
                <p className="text-3xl lowercase tracking-cozy">{queue[0].shown}</p>
                <AudioButton audio={queue[0].audio} label="hear this word" />
              </div>
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

      {/* Stationary back/next — fixed near the bottom of the page, so a taller
          card (more details/examples) never shifts them. */}
      {teaching && items && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-terraza-dash bg-terraza-bg/90 px-4 py-3 backdrop-blur">
          <div className="mx-auto flex max-w-2xl items-center justify-between">
            <button
              onClick={goBack}
              disabled={index === 0}
              aria-keyshortcuts="ArrowLeft"
              className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy disabled:opacity-40"
            >
              ← back
            </button>
            {index < items.length - 1 ? (
              <Button onClick={goForward} aria-keyshortcuts="ArrowRight">next →</Button>
            ) : (
              <Button onClick={goForward} aria-keyshortcuts="ArrowRight">quiz me →</Button>
            )}
          </div>
        </div>
      )}

      {teaching && scrolled && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-24 right-4 z-20 rounded-full bg-terraza-accent px-4 py-3 text-sm tracking-cozy text-terraza-accentInk shadow-lg transition-transform hover:-translate-y-0.5"
          aria-label="back to top"
        >
          ↑ top
        </button>
      )}
    </Protected>
  );
}

function ItemCard({
  item, examples, examplesLoading, activeTab, onTabClick,
  sentinelRef, detailsRef, readingRef, examplesRef,
}: {
  item: LessonItem;
  examples: ExampleSentence[];
  examplesLoading: boolean;
  activeTab: TabKey;
  onTabClick: (tab: TabKey) => void;
  sentinelRef: React.RefObject<HTMLDivElement | null>;
  detailsRef: React.RefObject<HTMLDivElement | null>;
  readingRef: React.RefObject<HTMLDivElement | null>;
  examplesRef: React.RefObject<HTMLDivElement | null>;
}) {
  const isGrammar = item.item_type === "grammar";
  const hasArticle = item.article && item.article !== "none";
  const hasGender = item.gender && item.gender !== "none";
  const hasReading = Boolean(item.pronunciation || item.ipa);

  return (
    <div
      className="overflow-hidden rounded-card border border-terraza-dash bg-terraza-card/50 backdrop-blur-sm"
      style={{ boxShadow: "0 2px 0 var(--lg-dash)" }}
    >
      {/* pinned: type tag, term + audio, translation — never grows with detail content */}
      <div className="p-6 text-center">
        <span className="text-xs tracking-label text-terraza-soft">
          {isGrammar ? "GRAMMAR" : (item.part_of_speech || "VOCABULARY").toUpperCase()}
        </span>
        <div className="mt-4 flex items-center justify-center gap-3">
          <p className="text-3xl lowercase tracking-cozy">
            {hasArticle ? <span className="text-terraza-soft">{item.article} </span> : null}
            {item.term}
          </p>
          <AudioButton audio={item.audio} label={`hear ${item.term}`} />
        </div>
        <p className="mt-2 text-lg text-terraza-accent">{item.translation}</p>
      </div>

      <div ref={sentinelRef} />

      {/* scrollable info — tabs below jump here */}
      <div className="flex flex-col gap-5 px-6 pb-6 text-left">
        <section ref={detailsRef} id="tab-details" className="scroll-mt-24">
          <h3 className="mb-2 text-xs tracking-label text-terraza-soft">DETAILS</h3>
          <dl className="flex flex-col gap-1.5 text-sm">
            {item.part_of_speech && <DetailRow label="part of speech" value={item.part_of_speech} />}
            {hasArticle && <DetailRow label="article" value={item.article!} />}
            {hasGender && <DetailRow label="gender" value={item.gender!} />}
            {item.structure && <DetailRow label="structure" value={item.structure} />}
            {item.meaning && <DetailRow label="meaning" value={item.meaning} />}
            {item.explanation && <DetailRow label="explanation" value={item.explanation} />}
          </dl>
          {!item.part_of_speech && !hasArticle && !hasGender && !item.structure
            && !item.meaning && !item.explanation && (
            <p className="font-empty italic text-terraza-soft">nothing extra for this item ~</p>
          )}
        </section>

        <section ref={readingRef} id="tab-reading" className="scroll-mt-24 border-t border-terraza-dash pt-4">
          <h3 className="mb-2 text-xs tracking-label text-terraza-soft">READING</h3>
          {hasReading ? (
            <div className="flex flex-col gap-1 text-sm">
              {item.pronunciation && (
                <p>say it: <span className="tracking-cozy">{item.pronunciation}</span></p>
              )}
              {item.ipa && <p className="text-terraza-soft">/{item.ipa}/</p>}
            </div>
          ) : (
            <p className="font-empty italic text-terraza-soft">no pronunciation guide for this item ~</p>
          )}
        </section>

        <section ref={examplesRef} id="tab-examples" className="scroll-mt-24 border-t border-terraza-dash pt-4">
          <h3 className="mb-2 text-xs tracking-label text-terraza-soft">EXAMPLES</h3>
          {examplesLoading ? (
            <p className="font-empty italic text-terraza-soft">un momento ~</p>
          ) : examples.length === 0 ? (
            <p className="font-empty italic text-terraza-soft">no example sentences yet ~</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {examples.map((ex) => (
                <li key={ex.id} className="flex items-start gap-2">
                  <AudioButton audio={ex.audio} label={`hear: ${ex.text_es}`} size="sm" />
                  <div>
                    <p className="tracking-cozy">{ex.text_es}</p>
                    {ex.text_en && <p className="text-sm text-terraza-soft">{ex.text_en}</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* tabs at the bottom border of the card */}
      <div className="flex border-t border-terraza-dash">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onTabClick(t.key)}
            aria-current={activeTab === t.key ? "true" : undefined}
            className={`flex-1 py-3 text-sm tracking-cozy transition-colors ${
              activeTab === t.key ? "bg-terraza-pill text-terraza-ink" : "text-terraza-soft hover:bg-terraza-pill/50"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-terraza-soft">{label}</dt>
      <dd className="text-right">{value}</dd>
    </div>
  );
}

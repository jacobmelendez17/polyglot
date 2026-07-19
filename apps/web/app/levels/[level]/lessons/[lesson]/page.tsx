"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { learn, newKey, type LessonItem } from "@/lib/learn-api";

export default function LessonPage() {
  const params = useParams();
  const router = useRouter();
  const level = Number(params.level);
  const lesson = Number(params.lesson);

  const [items, setItems] = useState<LessonItem[] | null>(null);
  const [index, setIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ xp: number; unlocked: number } | null>(null);
  const [saving, setSaving] = useState(false);
  // One key for the whole lesson: retrying the finish never double-awards XP.
  const [key] = useState(() => newKey());

  useEffect(() => {
    if (!level || !lesson) return;
    learn.lessonDetail(level, lesson)
      .then((d) => setItems(d.items))
      .catch((e) => setError(e.message));
  }, [level, lesson]);

  async function finish() {
    setSaving(true);
    try {
      const r = await learn.completeLesson(level, lesson, key);
      setDone({ xp: r.xp_awarded, unlocked: r.unlocked });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save your progress.");
      setSaving(false);
    }
  }

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Link href={`/levels/${level}`} className="text-sm text-terraza-soft">← level {level}</Link>

        {error && <Card className="mt-4"><p className="text-terraza-danger">{error}</p></Card>}
        {!items && !error && (
          <p className="mt-8 font-empty italic text-terraza-soft">un momento ~</p>
        )}

        {done ? (
          <Card className="mt-6 text-center">
            <p className="text-2xl lowercase tracking-cozy">¡lección completa! ✦</p>
            <p className="mt-3 text-terraza-soft">
              +{done.xp} XP · {done.unlocked} items added to your reviews
            </p>
            <p className="mt-1 text-sm text-terraza-soft">
              your first review lands in about 4 hours.
            </p>
            <div className="mt-5 flex justify-center gap-3">
              <Link href={`/levels/${level}`}
                className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy">
                back to level
              </Link>
              <Link href="/dashboard"
                className="rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
                dashboard
              </Link>
            </div>
          </Card>
        ) : items && items.length > 0 ? (
          <>
            <div className="mt-4 mb-6">
              <div className="h-2 overflow-hidden rounded-full bg-terraza-pill">
                <div
                  className="h-full rounded-full bg-terraza-accent transition-all"
                  style={{ width: `${((index + 1) / items.length) * 100}%` }}
                />
              </div>
              <p className="mt-2 text-xs tracking-label text-terraza-soft">
                {index + 1} / {items.length}
              </p>
            </div>
            <ItemCard item={items[index]} />
            <div className="mt-6 flex justify-between">
              <button
                onClick={() => setIndex((i) => Math.max(0, i - 1))}
                disabled={index === 0}
                className="rounded-full bg-terraza-pill px-5 py-2 tracking-cozy disabled:opacity-40"
              >
                ← back
              </button>
              {index < items.length - 1 ? (
                <Button onClick={() => setIndex((i) => i + 1)}>next →</Button>
              ) : (
                <Button onClick={finish} disabled={saving}>
                  {saving ? "guardando…" : "finish lesson"}
                </Button>
              )}
            </div>
          </>
        ) : null}
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

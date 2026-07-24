"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { learn, type Lesson } from "@/lib/learn-api";

export default function LevelPage() {
  const params = useParams();
  const level = Number(params.level);
  const [lessons, setLessons] = useState<Lesson[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!level) return;
    learn.lessons(level).then(setLessons).catch((e) => setError(e.message));
  }, [level]);

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Link href="/levels" className="text-sm text-terraza-soft">← levels</Link>
        <h1 className="mb-6 mt-2 text-2xl lowercase tracking-cozy">level {level}</h1>

        {error && <Card><p className="text-terraza-danger">{error}</p></Card>}
        {!lessons && !error && (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        )}
        {lessons && lessons.length === 0 && (
          <Card>
            <p className="text-center font-empty italic text-terraza-soft">
              no lessons here yet ~
            </p>
          </Card>
        )}
        <div className="flex flex-col gap-3">
          {lessons?.map((l) => (
            <Card key={l.position}>
              <div className="flex items-center gap-4">
                <div className="mr-auto">
                  <p className="lowercase tracking-cozy">{l.title}</p>
                  <p className="text-sm text-terraza-soft">
                    {l.item_count} items · {l.kind.replace("_", " ")}
                  </p>
                </div>
                {l.completed ? (
                  <span className="rounded-full bg-terraza-green px-3 py-1 text-xs">learned</span>
                ) : null}
                <Link
                  href={`/levels/${level}/lessons/${l.position}`}
                  className="rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk"
                >
                  {l.completed ? "review lesson" : "start"}
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </main>
    </Protected>
  );
}

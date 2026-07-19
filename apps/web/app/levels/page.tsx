"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { learn, type Level } from "@/lib/learn-api";

export default function LevelsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="mb-6 text-2xl lowercase tracking-cozy">levels</h1>
        <LevelList />
      </main>
    </Protected>
  );
}

function LevelList() {
  const [levels, setLevels] = useState<Level[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    learn.levels().then(setLevels).catch((e) => setError(e.message));
  }, []);

  if (error) return <Card><p className="text-terraza-danger">{error}</p></Card>;
  if (!levels) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;
  if (levels.length === 0) {
    return (
      <Card>
        <p className="text-center font-empty italic text-terraza-soft">
          no levels yet ~<br />
          <span className="text-sm">an admin needs to import and publish the curriculum</span>
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {levels.map((l) => (
        <Card key={l.id}>
          <div className="flex items-center gap-4">
            <span
              className={`flex h-12 w-12 flex-none items-center justify-center rounded-full text-lg ${
                l.unlocked ? "bg-terraza-accent text-terraza-accentInk" : "bg-terraza-pill text-terraza-soft"
              }`}
            >
              {l.position}
            </span>
            <div className="mr-auto">
              <p className="lowercase tracking-cozy">{l.title}</p>
              <p className="text-sm text-terraza-soft">
                {l.vocab_count} words · {l.grammar_count} grammar
              </p>
            </div>
            {l.unlocked ? (
              <Link
                href={`/levels/${l.position}`}
                className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy"
              >
                open
              </Link>
            ) : (
              <span className="text-sm text-terraza-soft">locked</span>
            )}
          </div>
        </Card>
      ))}
    </div>
  );
}

"use client";

// Unlock roadmap (spec §7): see which practice features are open and which unlock as
// you complete more levels. Lock state never relies on colour alone (a ✓/🔒 marker
// carries it). Loading / empty / error states throughout.

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { features, featureLabel, type FeaturesResult } from "@/lib/features-api";

export default function FeaturesPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-10">
        <Roadmap />
      </main>
    </Protected>
  );
}

function Roadmap() {
  const [data, setData] = useState<FeaturesResult | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    features.list().then(setData).catch(() => setError(true));
  }, []);

  if (error)
    return (
      <Card>
        <p role="alert" className="text-terraza-danger">couldn&apos;t load your unlock roadmap.</p>
      </Card>
    );
  if (data === null)
    return <p className="text-center font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <>
      <h1 className="text-2xl lowercase tracking-cozy">journey</h1>
      <p className="mt-1 mb-6 text-terraza-soft">
        {data.completed_levels === 0
          ? "complete your first level to start unlocking features."
          : `you've completed ${data.completed_levels} level${data.completed_levels === 1 ? "" : "s"}. keep going to unlock more.`}
      </p>

      <ol className="flex flex-col gap-2">
        {data.features.map((f) => (
          <li key={f.feature}>
            <Card className={f.unlocked ? "" : "opacity-70"}>
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="text-lg">{f.unlocked ? "✓" : "🔒"}</span>
                <span className="lowercase tracking-cozy">{featureLabel(f.feature)}</span>
                <span className="ml-auto text-sm text-terraza-soft">
                  {f.unlocked ? (
                    <span className="text-terraza-green">unlocked</span>
                  ) : (
                    <>unlocks at level {f.unlock_level}
                      <span className="ml-1 text-xs">
                        ({f.levels_remaining} to go)
                      </span>
                    </>
                  )}
                </span>
              </div>
            </Card>
          </li>
        ))}
      </ol>
    </>
  );
}

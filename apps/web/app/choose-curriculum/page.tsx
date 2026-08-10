"use client";

// Choose-curriculum step (by request). Last step of onboarding: how grammar and
// vocabulary are paced across each level's lessons. Shown after choose-language
// so a learner has already picked what to learn before deciding how it's
// batched. Reachable later too — it's the same "curriculum" setting the
// settings page exposes — but once a level is started its mode locks in for
// that level (PLANNING §5), so onboarding is the one moment this choice is
// guaranteed to be free.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui";
import { Protected } from "@/components/protected";
import { account, type Settings } from "@/lib/account-api";

const MODES: { value: string; label: string; blurb: string }[] = [
  {
    value: "default_dispersed",
    label: "themed",
    blurb: "grammar woven into four themed vocabulary lessons each level.",
  },
  {
    value: "grammar_batch",
    label: "batched",
    blurb: "four vocabulary lessons, then one lesson just for grammar.",
  },
  {
    value: "fully_dispersed",
    label: "mixed",
    blurb: "grammar and vocabulary shuffled together across all five lessons.",
  },
];

export default function ChooseCurriculumPage() {
  return (
    <Protected>
      <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
        <Chooser />
      </main>
    </Protected>
  );
}

function Chooser() {
  const router = useRouter();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    account.getSettings().then(setSettings).catch(() => setError(true));
  }, []);

  async function choose(mode: string) {
    setBusy(mode);
    try {
      await account.updateSettings({ curriculum_mode: mode });
      router.push("/dashboard");
    } catch {
      setError(true);
      setBusy(null);
    }
  }

  return (
    <>
      <div className="text-center">
        <span className="text-2xl lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">how should lessons be paced?</h1>
        <p className="mt-1 text-sm text-terraza-soft">
          you can change this later in settings, up until you start a level.
        </p>
      </div>

      {error ? (
        <Card>
          <p role="alert" className="text-terraza-danger">couldn&apos;t load your settings.</p>
          <Button className="mt-3" onClick={() => { setError(false); account.getSettings().then(setSettings).catch(() => setError(true)); }}>
            try again
          </Button>
        </Card>
      ) : settings === null ? (
        <p className="text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : (
        <div className="flex flex-col gap-3">
          {MODES.map((m) => {
            const active = settings.curriculum_mode === m.value;
            return (
              <button
                key={m.value}
                onClick={() => choose(m.value)}
                disabled={busy !== null}
                aria-pressed={active}
                className={`rounded-card border p-4 text-left tracking-cozy transition-transform hover:-translate-y-0.5 disabled:opacity-50 ${
                  active ? "border-terraza-accent bg-terraza-green text-terraza-accentInk" : "border-terraza-dash bg-terraza-card"
                }`}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-lg lowercase">{m.label}</span>
                  {active && <span aria-hidden>✓ current</span>}
                  {busy === m.value && <span className="text-sm">…</span>}
                </div>
                <p className={`mt-1 text-sm ${active ? "" : "text-terraza-soft"}`}>{m.blurb}</p>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}

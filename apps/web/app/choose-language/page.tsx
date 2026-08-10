"use client";

// Choose-language step (spec §1, §32; reordered by request). Shown right after
// the onboarding slides, so a learner sees why the method works before picking
// what to learn with it. Continues to choose-curriculum next. It's also
// reachable later, but the header switcher is the usual way to change languages
// after this. Loading / empty / error states throughout.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button, Card } from "@/components/ui";
import { Protected } from "@/components/protected";
import { languages, type Language } from "@/lib/languages-api";

export default function ChooseLanguagePage() {
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
  const [list, setList] = useState<Language[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    languages.list().then(setList).catch(() => setError(true));
  }, []);

  async function choose(code: string) {
    setBusy(code);
    try {
      await languages.setActive(code);
      router.push("/choose-curriculum"); // continue to lesson-pacing choice
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
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">what will you learn?</h1>
        <p className="mt-1 text-sm text-terraza-soft">
          you can switch languages anytime from the header.
        </p>
      </div>

      {error ? (
        <Card>
          <p role="alert" className="text-terraza-danger">couldn&apos;t load languages.</p>
          <Button className="mt-3" onClick={() => { setError(false); languages.list().then(setList).catch(() => setError(true)); }}>
            try again
          </Button>
        </Card>
      ) : list === null ? (
        <p className="text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : list.length === 0 ? (
        <Card><p className="font-empty italic text-terraza-soft">
          no languages are available yet.
        </p></Card>
      ) : (
        <div className="flex flex-col gap-3">
          {list.map((l) => (
            <button key={l.code} onClick={() => choose(l.code)} disabled={busy !== null}
              className="rounded-card border border-terraza-dash bg-terraza-card p-4 text-left tracking-cozy transition-transform hover:-translate-y-0.5 disabled:opacity-50">
              <span className="text-lg lowercase">{l.name}</span>
              {l.native_name && l.native_name !== l.name && (
                <span className="ml-2 text-sm text-terraza-soft">{l.native_name}</span>
              )}
              {busy === l.code && <span className="float-right text-sm text-terraza-soft">…</span>}
            </button>
          ))}
        </div>
      )}
    </>
  );
}

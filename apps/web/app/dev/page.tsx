"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { dev, type DevState } from "@/lib/billing-api";

// The admin dev sandbox. This page is only useful to an account holding the
// dev_panel capability — every action 403s otherwise — so it fails gracefully
// for anyone else: a plain "not available" card rather than a broken screen.

export default function DevPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <DevPanel />
      </main>
    </Protected>
  );
}

function DevPanel() {
  const [state, setState] = useState<DevState | null>(null);
  const [forbidden, setForbidden] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  function note(line: string) {
    setLog((prev) => [line, ...prev].slice(0, 8));
  }

  useEffect(() => {
    dev.state()
      .then(setState)
      .catch((e) => { if (e?.status === 403) setForbidden(true); });
  }, []);

  async function run(label: string, fn: () => Promise<string>) {
    setBusy(true);
    try {
      note(await fn());
    } catch (e) {
      note(`${label} failed: ${e instanceof Error ? e.message : "error"}`);
    } finally {
      setBusy(false);
    }
  }

  if (forbidden) {
    return (
      <Card>
        <p className="text-center font-empty italic text-terraza-soft">
          not available on this account ~
        </p>
        <p className="mt-2 text-center text-sm text-terraza-soft">
          the dev sandbox is for admin accounts.
        </p>
      </Card>
    );
  }

  return (
    <>
      <Link href="/dashboard" className="text-sm text-terraza-soft underline underline-offset-2">
        ← dashboard
      </Link>
      <h1 className="mb-1 mt-2 text-2xl lowercase tracking-cozy">dev sandbox</h1>
      <p className="mb-6 text-terraza-soft">
        troubleshoot practices and reviews without living through real srs
        intervals. everything here only touches your own account.
      </p>

      <Card>
        <h2 className="text-xs tracking-label text-terraza-soft">SRS TIME SCALE</h2>
        <p className="mt-2 text-sm text-terraza-soft">
          {state ? state.srs_scale_description : "un momento ~"}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            disabled={busy}
            onClick={() => run("fast mode", async () => {
              const s = await dev.setMode(true, "fast");
              setState(s);
              return `time scale: ${s.srs_scale_description}`;
            })}
            className="rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk disabled:opacity-50"
          >
            fast (1 week ≈ 30s)
          </button>
          <button
            disabled={busy}
            onClick={() => run("instant mode", async () => {
              const s = await dev.setMode(true, "instant");
              setState(s);
              return `time scale: ${s.srs_scale_description}`;
            })}
            className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            instant
          </button>
          <button
            disabled={busy}
            onClick={() => run("real intervals", async () => {
              const s = await dev.setMode(false, "off");
              setState(s);
              return "time scale: off (real intervals)";
            })}
            className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            turn off
          </button>
        </div>
      </Card>

      <Card className="mt-4">
        <h2 className="text-xs tracking-label text-terraza-soft">SANDBOX ACTIONS</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            disabled={busy}
            onClick={() => run("unlock all", async () => {
              const r = await dev.unlockAll();
              return `unlocked ${r.detail.unlocked} items — every practice now has material`;
            })}
            className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            unlock all items
          </button>
          <button
            disabled={busy}
            onClick={() => run("make reviews due", async () => {
              const r = await dev.makeReviewsDue();
              return `pulled ${r.detail.made_due} reviews to now`;
            })}
            className="rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            make all reviews due now
          </button>
        </div>
        <p className="mt-3 text-sm text-terraza-soft">
          unlock everything, flip on fast time, then start a review — you&apos;ll
          watch an item climb the srs ladder in seconds instead of weeks.
        </p>
      </Card>

      {log.length > 0 && (
        <Card className="mt-4">
          <h2 className="text-xs tracking-label text-terraza-soft">LOG</h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-terraza-soft">
            {log.map((line, i) => (
              <li key={i} className="font-mono">✦ {line}</li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

"use client";

// Vacation / pause card (spec R-25). Two faces: when active, an invitation to
// pause reviews before a trip; when paused, a calm "on a break since…" with a
// resume button. Resuming reports how many items shifted so the effect is
// visible, not silent. Full loading / error handling; nothing relies on colour
// alone (each state has its own words and an icon).

import { useEffect, useState } from "react";
import { Card } from "./ui";
import { vacation, type VacationState } from "@/lib/vacation-api";

function fmtSince(iso: string | null): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "long", day: "numeric",
    });
  } catch {
    return "";
  }
}

export function VacationCard() {
  const [state, setState] = useState<VacationState | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    vacation.state()
      .then((s) => { if (active) setState(s); })
      .catch(() => { if (active) setError("couldn't load vacation status"); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function pause() {
    setBusy(true); setError(null); setNote(null);
    try {
      const s = await vacation.pause();
      setState(s);
    } catch {
      setError("couldn't pause — try again");
    } finally { setBusy(false); }
  }

  async function resume() {
    setBusy(true); setError(null); setNote(null);
    try {
      const r = await vacation.resume();
      setState({ paused: false, since: null, days: 0 });
      setNote(
        r.shifted > 0
          ? `welcome back — ${r.shifted} ${r.shifted === 1 ? "item was" : "items were"} rescheduled so nothing piled up.`
          : "welcome back ✦",
      );
    } catch {
      setError("couldn't resume — try again");
    } finally { setBusy(false); }
  }

  if (loading) {
    return (
      <Card>
        <div className="mb-2 text-xs tracking-label text-terraza-soft">VACATION</div>
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      </Card>
    );
  }

  const paused = state?.paused;

  return (
    <Card>
      <div className="mb-2 text-xs tracking-label text-terraza-soft">VACATION</div>
      {paused ? (
        <>
          <p className="text-lg lowercase tracking-cozy">
            <span aria-hidden="true">🌴 </span>on a break
          </p>
          <p className="mt-1 text-sm text-terraza-soft">
            paused since {fmtSince(state!.since)}
            {state!.days > 0 ? ` · ${state!.days} ${state!.days === 1 ? "day" : "days"}` : ""}.
            reviews are frozen — they won&apos;t pile up.
          </p>
          <button
            onClick={resume} disabled={busy}
            className="mt-4 rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk disabled:opacity-50"
          >
            {busy ? "un momento…" : "i'm back — resume"}
          </button>
        </>
      ) : (
        <>
          <p className="text-sm text-terraza-soft">
            going away? pause your reviews so they don&apos;t stack up while you&apos;re out.
            everything picks up right where it left off.
          </p>
          {note && <p className="mt-3 text-sm text-terraza-green">{note}</p>}
          <button
            onClick={pause} disabled={busy}
            className="mt-4 rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            {busy ? "un momento…" : "pause reviews"}
          </button>
        </>
      )}
      {error && <p role="alert" className="mt-3 text-sm text-terraza-danger">{error}</p>}
    </Card>
  );
}

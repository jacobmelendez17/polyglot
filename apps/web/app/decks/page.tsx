"use client";

// Decks page (slice 43). Shows the full catalog: always-on decks, threshold-gated
// decks (locked ones greyed with "have/need" progress, not colour-alone), and the
// learner's custom decks — plus a see-through "+" ghost card at the end to create
// your own. Always-on decks link to their item list; locked and (for now) custom/
// unlockable decks don't navigate to items yet.

import Link from "next/link";
import { useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { decks, type CatalogDeck } from "@/lib/decks-api";

const ALWAYS_ON = new Set(["vocabulary", "grammar", "intermissions"]);

export default function DecksPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">decks</h1>
        <p className="mb-6 text-terraza-soft">
          browse what you&apos;ve unlocked — and unlock more as your words reach familiar.
        </p>
        <DeckGrid />
      </main>
      <Footer />
    </Protected>
  );
}

function DeckGrid() {
  const [list, setList] = useState<CatalogDeck[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  async function load() {
    setError(null);
    try {
      setList(await decks.catalog());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load your decks.");
    }
  }
  useEffect(() => { load(); }, []);

  if (error)
    return (
      <Card>
        <p role="alert" className="mb-3 text-terraza-danger">{error}</p>
        <button onClick={load} className="rounded-full border border-terraza-dash px-4 py-1.5 text-sm">
          try again
        </button>
      </Card>
    );
  if (!list) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((deck) => <DeckCard key={deck.id} deck={deck} onChanged={load} />)}
        <GhostCard onClick={() => setCreating(true)} />
      </div>

      {creating && (
        <CreateDeckModal
          onClose={() => setCreating(false)}
          onCreated={() => { setCreating(false); load(); }}
        />
      )}
    </>
  );
}

function DeckCard({ deck, onChanged }: { deck: CatalogDeck; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);

  const inner = (
    <Card
      className={`h-full ${
        deck.unlocked
          ? "transition-transform duration-200 hover:-translate-y-1 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
          : "opacity-70"
      }`}
    >
      <div className={`text-3xl ${deck.unlocked ? "text-terraza-accent" : "text-terraza-soft"}`}>
        {deck.unlocked ? deck.glyph : "🔒"}
      </div>
      <p className="mt-3 text-lg lowercase tracking-cozy">{deck.title}</p>
      <p className="mt-1 text-sm text-terraza-soft">{deck.description}</p>

      {deck.unlocked ? (
        <p className="mt-4 text-xs tracking-label text-terraza-accent">
          {typeof deck.count === "number"
            ? `${deck.count} ${deck.count === 1 ? "CARD" : "CARDS"}`
            : "UNLOCKED"}
          {deck.custom ? "" : " →"}
        </p>
      ) : (
        <div className="mt-4">
          <p className="mb-1 text-xs tracking-label text-terraza-soft">
            {deck.have}/{deck.threshold} familiar · {deck.need} to go
          </p>
          <div
            className="h-1.5 overflow-hidden rounded-full bg-terraza-dash"
            role="progressbar"
            aria-valuenow={deck.have}
            aria-valuemin={0}
            aria-valuemax={deck.threshold}
            aria-label={`${deck.title} unlock progress`}
          >
            <div
              className="h-full rounded-full bg-terraza-accent"
              style={{ width: `${Math.min(100, (deck.have / deck.threshold) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {deck.custom && (
        <button
          onClick={async (e) => {
            e.preventDefault();
            if (busy) return;
            setBusy(true);
            try { await decks.deleteCustom(deck.id); onChanged(); }
            catch { setBusy(false); }
          }}
          className="mt-3 text-xs text-terraza-soft underline underline-offset-2 hover:text-terraza-danger"
        >
          {busy ? "removing…" : "remove"}
        </button>
      )}
    </Card>
  );

  // Only the always-on decks have a working item list today.
  if (deck.unlocked && ALWAYS_ON.has(deck.id)) {
    return <Link href={`/decks/${deck.id}`}>{inner}</Link>;
  }
  return inner;
}

function GhostCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-label="create your own deck"
      className="flex h-full min-h-[168px] flex-col items-center justify-center rounded-card border-2 border-dashed border-terraza-dash bg-transparent text-terraza-soft transition-colors hover:border-terraza-accent hover:text-terraza-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink"
    >
      <span aria-hidden="true" className="text-4xl leading-none">＋</span>
      <span className="mt-2 text-sm lowercase tracking-cozy">create your own deck</span>
    </button>
  );
}

function CreateDeckModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try {
      await decks.createCustom(name.trim(), description.trim());
      onCreated();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't create the deck.");
      setBusy(false);
    }
  }

  const field = "w-full rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm";

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/30 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="create a deck"
      onClick={onClose}
    >
      <Card className="w-full max-w-md" >
        <div onClick={(e) => e.stopPropagation()}>
          <h2 className="mb-3 text-lg lowercase tracking-cozy">create your own deck</h2>
          <div className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-xs tracking-label text-terraza-soft">
              name
              <input className={field} value={name} maxLength={80} autoFocus
                onChange={(e) => setName(e.target.value)} placeholder="e.g. kitchen words" />
            </label>
            <label className="flex flex-col gap-1 text-xs tracking-label text-terraza-soft">
              description (optional)
              <textarea className={field} rows={2} value={description} maxLength={500}
                onChange={(e) => setDescription(e.target.value)} />
            </label>
            {err && <p role="alert" className="text-sm text-terraza-danger">{err}</p>}
            <p className="text-xs text-terraza-soft">
              you&apos;ll be able to add items to this deck from item pages soon.
            </p>
            <div className="mt-1 flex items-center gap-2">
              <button onClick={submit} disabled={!name.trim() || busy}
                className="rounded-full bg-terraza-accent px-5 py-2 text-sm text-terraza-accentInk disabled:opacity-50">
                {busy ? "creating…" : "create"}
              </button>
              <button onClick={onClose} disabled={busy}
                className="rounded-full border border-terraza-dash px-4 py-2 text-sm">cancel</button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

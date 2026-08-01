"use client";

// Reader (spec §7): read a text, tap a word to translate it, and highlight a span
// to leave a note (annotate / dissect). The body is tokenized so the rendered text
// content matches the server's body exactly — that's what lets a selection's
// character offsets line up with the offsets the server validates against. Words
// are focusable buttons (keyboard translate); nothing relies on colour alone.

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { reading, type Annotation, type Lookup, type ReadingText } from "@/lib/reading-api";

type Status = "loading" | "ok" | "notfound" | "error";

interface Token { text: string; isWord: boolean; offset: number }

function tokenize(body: string): Token[] {
  const parts = body.match(/\s+|\S+/g) ?? [];
  const out: Token[] = [];
  let offset = 0;
  for (const p of parts) {
    out.push({ text: p, isWord: !/^\s+$/.test(p), offset });
    offset += p.length;
  }
  return out;
}

function selectionOffsets(container: HTMLElement) {
  const sel = window.getSelection();
  if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return null;
  const range = sel.getRangeAt(0);
  if (!container.contains(range.commonAncestorContainer)) return null;
  const pre = range.cloneRange();
  pre.selectNodeContents(container);
  pre.setEnd(range.startContainer, range.startOffset);
  const start = pre.toString().length;
  const quote = range.toString();
  return { start, end: start + quote.length, quote };
}

export default function ReaderPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Reader />
      </main>
    </Protected>
  );
}

function Reader() {
  const { id } = useParams<{ id: string }>();
  const [text, setText] = useState<ReadingText | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [notes, setNotes] = useState<Annotation[]>([]);
  const [lookup, setLookup] = useState<{ x: number; y: number; data: Lookup } | null>(null);
  const [pending, setPending] = useState<{ start: number; end: number; quote: string } | null>(null);
  const [noteText, setNoteText] = useState("");
  const bodyRef = useRef<HTMLDivElement>(null);

  async function loadNotes() {
    try { setNotes(await reading.annotations(id)); } catch { /* keep prior */ }
  }
  useEffect(() => {
    if (!id) return;
    setStatus("loading");
    reading.get(id)
      .then((t) => { setText(t); setStatus("ok"); loadNotes(); })
      .catch((e) => setStatus((e as { status?: number })?.status === 404 ? "notfound" : "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function translate(word: string, x: number, y: number) {
    try {
      const data = await reading.lookup(word);
      setLookup({ x, y, data });
    } catch { setLookup(null); }
  }

  function onMouseUp() {
    if (!bodyRef.current) return;
    const sel = selectionOffsets(bodyRef.current);
    if (sel && sel.quote.trim()) { setPending(sel); setLookup(null); }
  }

  async function saveNote() {
    if (!pending) return;
    try {
      await reading.addAnnotation(id, pending.start, pending.end, noteText);
      setPending(null); setNoteText("");
      window.getSelection()?.removeAllRanges();
      loadNotes();
    } catch { /* leave the panel open to retry */ }
  }

  async function removeNote(annId: string) {
    await reading.deleteAnnotation(annId);
    loadNotes();
  }

  if (status === "loading") return <Card><p className="font-empty italic text-terraza-soft">un momento ~</p></Card>;
  if (status === "notfound")
    return (
      <Card>
        <p className="font-empty italic text-terraza-soft">this text isn&apos;t available.</p>
        <Link href="/reading" className="mt-3 inline-block text-sm text-terraza-accent">← back to reading</Link>
      </Card>
    );
  if (status === "error" || !text)
    return <Card><p role="alert" className="text-terraza-danger">couldn&apos;t load this text.</p></Card>;

  if (text.source_type === "external") {
    return (
      <Card>
        <Link href="/reading" className="text-sm text-terraza-accent">← reading</Link>
        <h1 className="mt-2 text-xl lowercase tracking-cozy">{text.title}</h1>
        <p className="mt-2 text-terraza-soft">{text.summary}</p>
        <a href={text.external_url} target="_blank" rel="noopener noreferrer"
          className="mt-4 inline-block rounded-full bg-terraza-accent px-5 py-2 tracking-cozy text-terraza-accentInk">
          open the reading ↗
        </a>
      </Card>
    );
  }

  const tokens = tokenize(text.body);

  return (
    <div className="relative">
      <Link href="/reading" className="text-sm text-terraza-accent">← reading</Link>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <h1 className="text-xl lowercase tracking-cozy">{text.title}</h1>
        {text.author && <span className="text-sm text-terraza-soft">{text.author}</span>}
      </div>

      <p className="mt-1 text-xs text-terraza-soft">
        tap a word for its meaning · highlight a phrase to leave a note
      </p>

      <Card className="mt-3">
        <div ref={bodyRef} onMouseUp={onMouseUp} lang="es"
          className="whitespace-pre-wrap text-lg leading-relaxed">
          {tokens.map((tok, i) =>
            tok.isWord ? (
              <span key={i} role="button" tabIndex={0}
                onClick={(e) => translate(tok.text, e.clientX, e.clientY)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    const r = (e.target as HTMLElement).getBoundingClientRect();
                    translate(tok.text, r.left, r.bottom);
                  }
                }}
                className="cursor-pointer rounded hover:bg-terraza-pill focus-visible:bg-terraza-pill focus-visible:outline-none">
                {tok.text}
              </span>
            ) : (
              <span key={i}>{tok.text}</span>
            ),
          )}
        </div>
      </Card>

      {/* translate popover */}
      {lookup && (
        <div style={{ position: "fixed", left: Math.min(lookup.x, window.innerWidth - 220), top: lookup.y + 8 }}
          className="z-20 w-52 rounded-card border border-terraza-dash bg-terraza-bg p-3 shadow-lg">
          <button onClick={() => setLookup(null)} aria-label="close"
            className="float-right text-terraza-soft">×</button>
          <p className="lowercase tracking-cozy" lang="es">{lookup.data.word}</p>
          {lookup.data.found ? (
            <>
              <p className="text-sm text-terraza-ink">{lookup.data.translation}</p>
              {lookup.data.part_of_speech && (
                <p className="text-xs text-terraza-soft">{lookup.data.part_of_speech}</p>
              )}
            </>
          ) : (
            <p className="text-sm text-terraza-soft">not in your vocabulary yet.</p>
          )}
        </div>
      )}

      {/* annotation composer */}
      {pending && (
        <Card className="mt-3 border-terraza-accent">
          <p className="text-xs tracking-label text-terraza-soft">HIGHLIGHTED</p>
          <p className="mt-1 italic text-terraza-soft" lang="es">“{pending.quote}”</p>
          <textarea value={noteText} onChange={(e) => setNoteText(e.target.value)}
            rows={2} maxLength={2000} placeholder="your note (grammar, meaning, a question…)"
            className="mt-2 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2" />
          <div className="mt-2 flex gap-2">
            <Button onClick={saveNote}>save note</Button>
            <button onClick={() => { setPending(null); setNoteText(""); window.getSelection()?.removeAllRanges(); }}
              className="rounded-full px-4 py-2 text-sm text-terraza-soft hover:bg-terraza-pill">cancel</button>
          </div>
        </Card>
      )}

      {/* notes list */}
      <h2 className="mb-2 mt-6 text-xs tracking-label text-terraza-soft">YOUR NOTES · {notes.length}</h2>
      {notes.length === 0 ? (
        <p className="font-empty italic text-terraza-soft">no notes yet — highlight a phrase above to add one.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {notes.map((n) => (
            <Card key={n.id}>
              <p className="italic text-terraza-soft" lang="es">“{n.quote}”</p>
              {n.note && <p className="mt-1 text-sm">{n.note}</p>}
              <button onClick={() => removeNote(n.id)}
                className="mt-1 text-xs text-terraza-danger underline">delete</button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

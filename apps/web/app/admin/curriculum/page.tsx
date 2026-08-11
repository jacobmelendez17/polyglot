"use client";

// In-app curriculum editor (slice 39): add / edit / delete / restore vocabulary
// and grammar, and move items into any level or batch. All controls are native
// buttons and selects (keyboard-accessible; §29) — drag-to-move is a later polish.

import { useCallback, useEffect, useMemo, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import {
  createItem,
  deleteItem,
  getStoredToken,
  listEditorItems,
  moveItem,
  restoreItem,
  updateItem,
  type EditorItem,
  type Kind,
} from "@/lib/editor-api";

const LEVELS = Array.from({ length: 20 }, (_, i) => i + 1);
const BATCHES = [1, 2, 3, 4];
const POS = ["", "noun", "verb", "adjective", "adverb", "preposition", "conjunction",
  "pronoun", "interjection", "phrase", "article", "numeral"];

function EditorInner() {
  const { user } = useAuth();
  const canEdit = user?.capabilities.includes("content_edit");
  const [kind, setKind] = useState<Kind>("vocabulary");
  const [level, setLevel] = useState<number | "">("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [items, setItems] = useState<EditorItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const token = getStoredToken();

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const r = await listEditorItems(token, kind, {
        level: level === "" ? undefined : level,
        includeArchived,
      });
      setItems(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load items.");
      setItems(null);
    } finally {
      setLoading(false);
    }
  }, [token, kind, level, includeArchived]);

  useEffect(() => {
    load();
  }, [load]);

  const flash = (msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(null), 2500);
  };

  if (user && !canEdit) {
    return (
      <Card>
        <p className="text-sm text-terraza-soft">
          you need the content-editor role to edit curriculum.
        </p>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex rounded-full border border-terraza-dash p-1" role="tablist" aria-label="content kind">
          {(["vocabulary", "grammar"] as Kind[]).map((k) => (
            <button
              key={k}
              role="tab"
              aria-selected={kind === k}
              onClick={() => { setKind(k); setEditingId(null); setAdding(false); }}
              className={`rounded-full px-4 py-1 text-sm ${kind === k ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft"}`}
            >
              {k}
            </button>
          ))}
        </div>

        <label className="text-sm text-terraza-soft">
          level{" "}
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value === "" ? "" : Number(e.target.value))}
            className="rounded-[10px] border border-terraza-dash bg-terraza-bg px-2 py-1"
          >
            <option value="">all</option>
            {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>

        <label className="flex items-center gap-2 text-sm text-terraza-soft">
          <input type="checkbox" checked={includeArchived}
            onChange={(e) => setIncludeArchived(e.target.checked)} />
          show archived
        </label>

        <button
          onClick={() => { setAdding((a) => !a); setEditingId(null); }}
          className="ml-auto rounded-full bg-terraza-accent px-4 py-1.5 text-sm text-terraza-accentInk"
        >
          {adding ? "close" : `+ add ${kind === "vocabulary" ? "word" : "grammar"}`}
        </button>
      </div>

      {toast && (
        <div role="status" className="rounded-[12px] bg-terraza-accent/15 px-4 py-2 text-sm text-terraza-ink">
          {toast}
        </div>
      )}

      {adding && token && (
        <ItemForm
          kind={kind}
          onCancel={() => setAdding(false)}
          onSubmit={async (body) => {
            await createItem(token, kind, body);
            setAdding(false);
            flash("added.");
            load();
          }}
        />
      )}

      {loading && <Card><p className="text-sm text-terraza-soft">loading…</p></Card>}

      {!loading && error && (
        <Card>
          <p className="mb-3 text-sm text-terraza-ink">{error}</p>
          <button onClick={load} className="rounded-full border border-terraza-dash px-4 py-1.5 text-sm">
            try again
          </button>
        </Card>
      )}

      {!loading && !error && items && items.length === 0 && (
        <Card>
          <p className="text-sm text-terraza-soft">
            no {kind} {level === "" ? "yet" : `in level ${level}`}. use “+ add”, or import a CSV from the admin page.
          </p>
        </Card>
      )}

      {!loading && !error && items && items.length > 0 && (
        <Card>
          <ul className="divide-y divide-terraza-dash">
            {items.map((it) => (
              <li key={it.id} className="py-3">
                {editingId === it.id && token ? (
                  <ItemForm
                    kind={kind}
                    initial={it}
                    onCancel={() => setEditingId(null)}
                    onSubmit={async (body) => {
                      await updateItem(token, kind, it.id, body);
                      setEditingId(null);
                      flash("saved.");
                      load();
                    }}
                  />
                ) : (
                  <Row
                    item={it}
                    onEdit={() => { setEditingId(it.id); setAdding(false); }}
                    onMove={async (level2, batch2) => {
                      if (!token) return;
                      await moveItem(token, kind, it.id, { level: level2, batch: batch2 });
                      flash("moved.");
                      load();
                    }}
                    onDelete={async () => {
                      if (!token) return;
                      await deleteItem(token, kind, it.id);
                      flash("archived.");
                      load();
                    }}
                    onRestore={async () => {
                      if (!token) return;
                      await restoreItem(token, kind, it.id);
                      flash("restored.");
                      load();
                    }}
                  />
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function Row({
  item, onEdit, onMove, onDelete, onRestore,
}: {
  item: EditorItem;
  onEdit: () => void;
  onMove: (level: number, batch?: number) => Promise<void>;
  onDelete: () => Promise<void>;
  onRestore: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const run = (fn: () => Promise<void>) => async () => {
    setBusy(true);
    try { await fn(); } catch (e) {
      alert(e instanceof Error ? e.message : "Action failed.");
    } finally { setBusy(false); }
  };

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="min-w-[160px] flex-1">
        <div className="flex items-center gap-2">
          <span className="text-terraza-ink">{item.term}</span>
          {item.article && item.article !== "none" && (
            <span className="rounded bg-terraza-dash/50 px-1.5 text-xs text-terraza-soft">{item.article}</span>
          )}
          {item.archived && (
            <span className="rounded bg-terraza-dash px-1.5 text-xs text-terraza-soft">archived</span>
          )}
        </div>
        <div className="text-sm text-terraza-soft">
          {item.translation || <em>no translation</em>}
          {item.part_of_speech ? ` · ${item.part_of_speech}` : ""}
        </div>
      </div>

      {/* move: level (+ batch for vocab) */}
      <div className="flex items-center gap-1 text-sm text-terraza-soft">
        <span className="sr-only">move {item.term} to level</span>
        L
        <select
          aria-label={`level for ${item.term}`}
          value={item.level}
          disabled={busy || item.archived}
          onChange={(e) => run(() => onMove(Number(e.target.value), item.batch))()}
          className="rounded-[8px] border border-terraza-dash bg-terraza-bg px-1.5 py-1"
        >
          {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        {item.kind === "vocabulary" && (
          <>
            B
            <select
              aria-label={`batch for ${item.term}`}
              value={item.batch ?? 1}
              disabled={busy || item.archived}
              onChange={(e) => run(() => onMove(item.level, Number(e.target.value)))()}
              className="rounded-[8px] border border-terraza-dash bg-terraza-bg px-1.5 py-1"
            >
              {BATCHES.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        {!item.archived ? (
          <>
            <button onClick={onEdit} disabled={busy}
              className="rounded-full border border-terraza-dash px-3 py-1 text-sm">edit</button>
            <button onClick={run(onDelete)} disabled={busy}
              className="rounded-full border border-terraza-dash px-3 py-1 text-sm text-terraza-ink">archive</button>
          </>
        ) : (
          <button onClick={run(onRestore)} disabled={busy}
            className="rounded-full bg-terraza-accent px-3 py-1 text-sm text-terraza-accentInk">restore</button>
        )}
      </div>
    </div>
  );
}

function ItemForm({
  kind, initial, onSubmit, onCancel,
}: {
  kind: Kind;
  initial?: EditorItem;
  onSubmit: (body: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
}) {
  const isEdit = !!initial;
  const [term, setTerm] = useState(initial?.term ?? "");
  const [translation, setTranslation] = useState(initial?.translation ?? "");
  const [pos, setPos] = useState(initial?.part_of_speech ?? "");
  const [meaning, setMeaning] = useState(initial?.meaning ?? "");
  const [level, setLevel] = useState<number>(initial?.level ?? 1);
  const [batch, setBatch] = useState<number>(initial?.batch ?? 1);
  const [article, setArticle] = useState(initial?.article ?? "none");
  const [structure, setStructure] = useState(initial?.structure_pattern ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const canSave = term.trim().length > 0;

  const submit = async () => {
    setBusy(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = { term: term.trim(), translation, part_of_speech: pos, meaning };
      if (!isEdit) body.level = level;
      if (kind === "vocabulary") {
        if (!isEdit) body.batch = batch;
        body.article = pos === "noun" ? article : "none";
      } else {
        body.structure_pattern = structure;
      }
      await onSubmit(body);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't save.");
    } finally {
      setBusy(false);
    }
  };

  const field = "rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm";

  return (
    <div className="rounded-[12px] border border-terraza-dash bg-terraza-bg/50 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-xs text-terraza-soft">
          {kind === "vocabulary" ? "word" : "grammar point"}
          <input className={field} value={term} onChange={(e) => setTerm(e.target.value)} autoFocus />
        </label>
        <label className="flex flex-col gap-1 text-xs text-terraza-soft">
          translation
          <input className={field} value={translation} onChange={(e) => setTranslation(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-xs text-terraza-soft">
          part of speech
          <select className={field} value={pos} onChange={(e) => setPos(e.target.value)}>
            {POS.map((p) => <option key={p} value={p}>{p || "—"}</option>)}
          </select>
        </label>
        {kind === "vocabulary" ? (
          <label className="flex flex-col gap-1 text-xs text-terraza-soft">
            article {pos !== "noun" && <span className="text-terraza-soft/70">(nouns only)</span>}
            <select className={field} value={article} disabled={pos !== "noun"}
              onChange={(e) => setArticle(e.target.value)}>
              {["none", "el", "la", "los", "las", "un", "una"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
        ) : (
          <label className="flex flex-col gap-1 text-xs text-terraza-soft">
            structure pattern
            <input className={field} value={structure} onChange={(e) => setStructure(e.target.value)} />
          </label>
        )}
        {!isEdit && (
          <label className="flex flex-col gap-1 text-xs text-terraza-soft">
            level
            <select className={field} value={level} onChange={(e) => setLevel(Number(e.target.value))}>
              {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
        )}
        {!isEdit && kind === "vocabulary" && (
          <label className="flex flex-col gap-1 text-xs text-terraza-soft">
            batch
            <select className={field} value={batch} onChange={(e) => setBatch(Number(e.target.value))}>
              {BATCHES.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </label>
        )}
        <label className="flex flex-col gap-1 text-xs text-terraza-soft sm:col-span-2">
          meaning / notes
          <textarea className={field} rows={2} value={meaning} onChange={(e) => setMeaning(e.target.value)} />
        </label>
      </div>

      {err && <p className="mt-2 text-sm text-terraza-ink">{err}</p>}

      <div className="mt-3 flex items-center gap-2">
        <button onClick={submit} disabled={!canSave || busy}
          className="rounded-full bg-terraza-accent px-5 py-1.5 text-sm text-terraza-accentInk disabled:opacity-50">
          {busy ? "saving…" : isEdit ? "save" : "add"}
        </button>
        <button onClick={onCancel} disabled={busy}
          className="rounded-full border border-terraza-dash px-4 py-1.5 text-sm">cancel</button>
      </div>
    </div>
  );
}

export default function CurriculumEditorPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-6 text-2xl lowercase tracking-cozy">curriculum editor</h1>
        <EditorInner />
      </main>
    </Protected>
  );
}

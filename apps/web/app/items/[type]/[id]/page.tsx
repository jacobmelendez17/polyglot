"use client";

// Item detail page — redesigned (slice 44).
// Layout, top to bottom:
//   hero (no card): big centered term + translation, scroll-away → sticky sub-header
//   pronunciation box  |  synonyms & variants
//   meaning (dictionary) · curriculum notes (admin) · your notes (editable, ≤250w)
//   context phrases (tabbed, WaniKani-style)
//   examples (sentence + translation + audio)
//   your progress (SRS + time to review)  |  practice stages
//   item stats (meaning / reading / combined accuracy, unlock + retire dates)

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import { LeechPill, SrsPill } from "@/components/progress-bits";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import {
  items, type ExampleSentence, type HistoryEntry, type ItemDetail, type UserSynonym,
} from "@/lib/items-api";
import {
  countWords, itemNotes, MAX_NOTE_WORDS, shortDate, timeUntilReview,
} from "@/lib/item-extras";

const MAX_PRACTICE_STAGE = 5;

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <h2 className="mb-3 text-base tracking-label text-terraza-soft">{String(children).toUpperCase()}</h2>;
}
function CardLabel({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-2 text-sm tracking-label text-terraza-soft">{String(children).toUpperCase()}</h3>;
}

export default function ItemPage() {
  return (
    <Protected>
      <Header />
      <ItemView />
    </Protected>
  );
}

function ItemView() {
  const params = useParams();
  const type = String(params.type);
  const id = String(params.id);

  const [item, setItem] = useState<ItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [heroVisible, setHeroVisible] = useState(true);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setItem(null); setError(null);
    items.detail(type, id)
      .then((d) => { if (!cancelled) setItem(d); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [type, id]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => setHeroVisible(entry.isIntersecting),
      { rootMargin: "-8px 0px 0px 0px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [item]);

  if (error) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <Card>
          <p className="text-terraza-danger" role="alert">{error}</p>
          <Link href="/levels" className="mt-4 inline-block underline underline-offset-2">back to levels</Link>
        </Card>
      </main>
    );
  }
  if (!item) {
    return <p className="mt-10 text-center font-empty italic text-terraza-soft">un momento ~</p>;
  }

  const article = item.article && item.article !== "none" ? item.article : null;
  const statusName = item.progress.learned ? item.progress.srs_stage_name : "not started";

  return (
    <>
      {/* sticky sub-header once the hero scrolls away */}
      <div
        className={`sticky top-0 z-30 border-b border-terraza-dash bg-terraza-bg/95 backdrop-blur transition-opacity duration-200 motion-reduce:transition-none ${
          heroVisible ? "pointer-events-none opacity-0" : "opacity-100"
        }`}
        aria-hidden={heroVisible}
      >
        <div className="mx-auto flex max-w-4xl items-center gap-3 px-4 py-2">
          <span className="text-lg lowercase tracking-cozy text-terraza-ink">
            {article && <span className="text-terraza-soft">{article} </span>}{item.term}
          </span>
          <span className="text-sm text-terraza-accent">{item.translation}</span>
          <div className="ml-auto"><SrsPill stage={item.progress.srs_stage} name={statusName} /></div>
        </div>
      </div>

      <main className="mx-auto max-w-4xl px-4 py-8">
        <Link href={`/levels/${item.level}/progress`} className="text-sm text-terraza-soft underline underline-offset-2">
          ← level {item.level} progress
        </Link>

        {/* hero (no card) */}
        <header className="mt-6 flex flex-col items-center text-center">
          <div className="flex items-center gap-3">
            <h1 className="text-5xl lowercase tracking-cozy text-terraza-ink">
              {article && <span className="text-terraza-soft">{article} </span>}{item.term}
            </h1>
            <AudioButton audio={item.audio} label={`hear ${item.term}`} />
          </div>
          <p className="mt-3 text-2xl text-terraza-accent">{item.translation}</p>
          <div className="mt-4 flex items-center gap-2">
            <SrsPill stage={item.progress.srs_stage} name={statusName} />
            {item.progress.leech_state !== "none" && <LeechPill state={item.progress.leech_state} />}
          </div>
        </header>

        <div ref={sentinelRef} className="h-px" />

        <div className="mt-8 flex flex-col gap-8">
          {/* pronunciation | synonyms & variants */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
            <PronunciationBox item={item} />
            <SynonymsCard type={type} id={id} item={item} onChange={setItem} />
          </div>

          <MeaningCard item={item} />
          <CurriculumNotesCard item={item} />
          <NotesCard type={type} id={id} />
          <ContextCard item={item} />
          <ExamplesSection examples={item.examples} />

          {/* progress | practice */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <ProgressCard item={item} />
            <PracticeCard item={item} />
          </div>

          <StatsSection type={type} id={id} item={item} />
        </div>
      </main>
    </>
  );
}

// ---- pronunciation --------------------------------------------------------

function PronunciationBox({ item }: { item: ItemDetail }) {
  const has = item.pronunciation || item.ipa || item.audio;
  return (
    <Card className="h-full">
      <CardLabel>pronunciation</CardLabel>
      {has ? (
        <div className="flex flex-col gap-2">
          {item.pronunciation && <p className="text-lg tracking-cozy text-terraza-ink">{item.pronunciation}</p>}
          {item.ipa && <p className="text-terraza-soft">/{item.ipa}/</p>}
          <div className="mt-1"><AudioButton audio={item.audio} label={`hear ${item.term}`} /></div>
        </div>
      ) : (
        <p className="font-empty italic text-terraza-soft">no pronunciation yet ~</p>
      )}
    </Card>
  );
}

// ---- synonyms & variants --------------------------------------------------

function SynonymsCard({
  type, id, item, onChange,
}: { type: string; id: string; item: ItemDetail; onChange: (d: ItemDetail) => void }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const variants = [
    ...(item.variations ?? []),
    ...(item.castilian_variant ? [`${item.castilian_variant} (Spain)`] : []),
    ...(item.latam_variant ? [`${item.latam_variant} (LatAm)`] : []),
  ];

  async function add() {
    const s = value.trim();
    if (!s) return;
    setBusy(true); setErr(null);
    try {
      const res = await items.addSynonym(type, id, s);
      onChange({ ...item, user_synonyms: [...item.user_synonyms, { id: res.id, synonym: res.synonym }] });
      setValue("");
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't add that."); }
    finally { setBusy(false); }
  }
  async function remove(syn: UserSynonym) {
    try {
      await items.removeSynonym(syn.id);
      onChange({ ...item, user_synonyms: item.user_synonyms.filter((s) => s.id !== syn.id) });
    } catch { /* keep it; the list refreshes on reload */ }
  }

  return (
    <Card className="h-full">
      <CardLabel>synonyms &amp; variants</CardLabel>
      <div className="flex flex-col gap-3">
        <ChipRow label="synonyms" chips={item.synonyms} empty="none listed" />
        <ChipRow label="variants" chips={variants} empty="none listed" />

        <div>
          <p className="mb-1 text-xs tracking-label text-terraza-soft">YOUR SYNONYMS</p>
          {item.user_synonyms.length === 0 ? (
            <p className="text-sm text-terraza-soft">add ways you&apos;d accept — counted only while &ldquo;accept my synonyms&rdquo; is on in settings.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {item.user_synonyms.map((s) => (
                <span key={s.id} className="inline-flex items-center gap-1 rounded-full bg-terraza-pill px-2.5 py-1 text-sm">
                  {s.synonym}
                  <button onClick={() => remove(s)} aria-label={`remove ${s.synonym}`}
                    className="text-terraza-soft hover:text-terraza-danger">×</button>
                </span>
              ))}
            </div>
          )}
          <div className="mt-2 flex gap-2">
            <input value={value} onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") add(); }}
              placeholder="another way to say it…" maxLength={60}
              className="w-full rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm" />
            <button onClick={add} disabled={!value.trim() || busy}
              className="rounded-full bg-terraza-accent px-4 py-2 text-sm text-terraza-accentInk disabled:opacity-50">
              {busy ? "…" : "add"}
            </button>
          </div>
          {err && <p role="alert" className="mt-1 text-sm text-terraza-danger">{err}</p>}
        </div>
      </div>
    </Card>
  );
}

function ChipRow({ label, chips, empty }: { label: string; chips: string[]; empty: string }) {
  return (
    <div>
      <p className="mb-1 text-xs tracking-label text-terraza-soft">{label.toUpperCase()}</p>
      {chips.length === 0 ? (
        <p className="text-sm text-terraza-soft">{empty}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {chips.map((c, i) => (
            <span key={`${c}-${i}`} className="rounded-full bg-terraza-pill px-2.5 py-1 text-sm">{c}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- meaning / curriculum notes ------------------------------------------

function MeaningCard({ item }: { item: ItemDetail }) {
  return (
    <Card>
      <CardLabel>meaning</CardLabel>
      {item.meaning ? (
        <p className="leading-relaxed text-terraza-ink">{item.meaning}</p>
      ) : (
        <p className="font-empty italic text-terraza-soft">no definition yet ~</p>
      )}
    </Card>
  );
}

function CurriculumNotesCard({ item }: { item: ItemDetail }) {
  // Admin-authored notes to be aware of. For grammar this is the explanation /
  // structure; vocabulary gets a dedicated field in a later slice.
  const notes = item.explanation || item.structure || "";
  return (
    <Card>
      <CardLabel>curriculum notes</CardLabel>
      {notes ? (
        <p className="leading-relaxed text-terraza-ink">{notes}</p>
      ) : (
        <p className="font-empty italic text-terraza-soft">no curriculum notes for this item ~</p>
      )}
    </Card>
  );
}

// ---- your notes -----------------------------------------------------------

function NotesCard({ type, id }: { type: string; id: string }) {
  const [body, setBody] = useState("");
  const [saved, setSaved] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    itemNotes.get(type, id)
      .then((n) => { if (!cancelled) { setBody(n.body); setSaved(n.body); setLoaded(true); } })
      .catch(() => { if (!cancelled) setLoaded(true); });
    return () => { cancelled = true; };
  }, [type, id]);

  const words = countWords(body);
  const over = words > MAX_NOTE_WORDS;
  const dirty = body !== saved;

  async function save() {
    if (over) return;
    setBusy(true); setErr(null);
    try {
      const n = await itemNotes.save(type, id, body);
      setBody(n.body); setSaved(n.body);
    } catch (e) { setErr(e instanceof Error ? e.message : "Couldn't save your note."); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      <CardLabel>your notes</CardLabel>
      {!loaded ? (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      ) : (
        <>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            placeholder="jot down anything that helps you remember this one…"
            className="w-full rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm"
          />
          <div className="mt-2 flex items-center gap-3">
            <span className={`text-xs ${over ? "text-terraza-danger" : "text-terraza-soft"}`}>
              {words}/{MAX_NOTE_WORDS} words
            </span>
            {err && <span role="alert" className="text-xs text-terraza-danger">{err}</span>}
            <div className="ml-auto flex gap-2">
              <button onClick={() => setBody("")} disabled={busy || body === ""}
                className="rounded-full border border-terraza-dash px-4 py-1.5 text-sm disabled:opacity-50">
                clear
              </button>
              <button onClick={save} disabled={busy || over || !dirty}
                className="rounded-full bg-terraza-accent px-5 py-1.5 text-sm text-terraza-accentInk disabled:opacity-50">
                {busy ? "saving…" : "save"}
              </button>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}

// ---- context phrases (tabbed) --------------------------------------------

interface ContextTab { label: string; rows: { es: string; en: string }[] }

function normalizeContext(raw: unknown[] | null | undefined): ContextTab[] {
  if (!Array.isArray(raw)) return [];
  const pick = (o: Record<string, unknown>, keys: string[]) => {
    for (const k of keys) if (typeof o[k] === "string" && o[k]) return o[k] as string;
    return "";
  };
  const tabs: ContextTab[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const o = entry as Record<string, unknown>;
    const label = pick(o, ["label", "title", "form", "tense", "name", "group"]) || `group ${tabs.length + 1}`;
    const listRaw = (o.phrases ?? o.examples ?? o.items ?? o.uses) as unknown;
    const rows: { es: string; en: string }[] = [];
    if (Array.isArray(listRaw)) {
      for (const p of listRaw) {
        if (typeof p === "string") { rows.push({ es: p, en: "" }); continue; }
        if (p && typeof p === "object") {
          const po = p as Record<string, unknown>;
          rows.push({
            es: pick(po, ["es", "text_es", "spanish", "text", "phrase"]),
            en: pick(po, ["en", "text_en", "english", "translation", "gloss"]),
          });
        }
      }
    }
    if (rows.length) tabs.push({ label, rows });
  }
  return tabs;
}

function ContextCard({ item }: { item: ItemDetail }) {
  const tabs = useMemo(() => normalizeContext(item.context), [item.context]);
  const [active, setActive] = useState(0);
  if (tabs.length === 0) {
    return (
      <Card>
        <CardLabel>context phrases</CardLabel>
        <p className="font-empty italic text-terraza-soft">no context phrases yet ~</p>
      </Card>
    );
  }
  const current = tabs[Math.min(active, tabs.length - 1)];
  return (
    <Card>
      <CardLabel>context phrases</CardLabel>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,10rem)_1fr]">
        <ul className="flex gap-2 overflow-x-auto sm:flex-col sm:overflow-visible" role="tablist" aria-label="context groups">
          {tabs.map((t, i) => (
            <li key={t.label + i} className="shrink-0">
              <button role="tab" aria-selected={active === i} onClick={() => setActive(i)}
                className={`w-full whitespace-nowrap rounded-[10px] px-3 py-2 text-left text-sm tracking-cozy ${
                  active === i ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft hover:bg-terraza-pill"
                }`}>
                {t.label}
              </button>
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-2 border-t border-terraza-dash pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:pt-0">
          {current.rows.map((r, i) => (
            <li key={i}>
              <p className="text-terraza-ink">{r.es}</p>
              {r.en && <p className="text-sm text-terraza-soft">{r.en}</p>}
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}

// ---- examples -------------------------------------------------------------

function ExamplesSection({ examples }: { examples: ExampleSentence[] }) {
  return (
    <section>
      <SectionLabel>examples</SectionLabel>
      {examples.length === 0 ? (
        <Card><p className="font-empty italic text-terraza-soft">no example sentences yet ~</p></Card>
      ) : (
        <div className="flex flex-col gap-3">
          {examples.map((ex) => (
            <Card key={ex.id}>
              <div className="flex items-start gap-3">
                <div className="min-w-0">
                  <p className="text-terraza-ink">{ex.text_es}</p>
                  {ex.text_en && <p className="mt-1 text-sm text-terraza-soft">{ex.text_en}</p>}
                </div>
                {ex.audio && <div className="ml-auto"><AudioButton audio={ex.audio} label="hear sentence" /></div>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

// ---- your progress --------------------------------------------------------

function ProgressCard({ item }: { item: ItemDetail }) {
  const p = item.progress;
  return (
    <Card className="h-full">
      <CardLabel>your progress</CardLabel>
      {p.learned ? (
        <div className="flex flex-col gap-2">
          <SrsPill stage={p.srs_stage} name={p.srs_stage_name} />
          <p className="text-sm text-terraza-soft">{timeUntilReview(p.next_review_at)}</p>
          {p.perfect && <p className="text-sm text-terraza-accent">✦ perfect — every category finished</p>}
        </div>
      ) : (
        <p className="font-empty italic text-terraza-soft">you have not learned this one yet ~</p>
      )}
    </Card>
  );
}

// ---- practice stages ------------------------------------------------------

function PracticeCard({ item }: { item: ItemDetail }) {
  const pr = item.practice;
  return (
    <Card className="h-full">
      <CardLabel>practice stages</CardLabel>
      <div className="flex flex-col gap-2">
        {pr.stages.map((st) => (
          <div key={st.category} className="flex items-center gap-3 text-sm">
            <span className="w-20 tracking-cozy">{st.label}</span>
            <span className="flex gap-1" aria-hidden="true">
              {Array.from({ length: MAX_PRACTICE_STAGE }).map((_, i) => (
                <span key={i}
                  className={`inline-block h-3 w-3 rounded-full border ${
                    i < st.stage ? "border-terraza-accent bg-terraza-accent" : "border-terraza-dash"
                  }`} />
              ))}
            </span>
            <span className="ml-auto text-terraza-soft">
              {st.complete ? "done" : st.on_cooldown ? "resting" : st.stage > 0 ? `stage ${st.stage}` : "not started"}
            </span>
            <span className="sr-only">
              {st.label}: {st.stage} of {MAX_PRACTICE_STAGE}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-3 text-sm text-terraza-soft">
        {pr.categories_complete} of {pr.categories_total} categories finished
        {pr.srs_fluent ? "" : " · fluent in reviews still needed"}
      </p>
      <p className="mt-1 text-xs text-terraza-soft">one stage per category per day — practice is spaced too.</p>
    </Card>
  );
}

// ---- item stats -----------------------------------------------------------

function bucketStats(entries: HistoryEntry[]) {
  const mk = () => ({ total: 0, correct: 0 });
  const meaning = mk(), reading = mk(), combined = mk();
  for (const e of entries) {
    const b = e.direction === "es_to_en" ? meaning : reading;
    b.total += 1; combined.total += 1;
    if (e.final_correct) { b.correct += 1; combined.correct += 1; }
  }
  return { meaning, reading, combined };
}
const pct = (b: { total: number; correct: number }) =>
  b.total === 0 ? "—" : `${Math.round((b.correct / b.total) * 100)}%`;

function StatsSection({ type, id, item }: { type: string; id: string; item: ItemDetail }) {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const load = useCallback(async () => {
    try {
      const page = await items.history(type, id, 100, 0);
      setEntries(page.items);
    } catch { setEntries([]); }
  }, [type, id]);
  useEffect(() => { load(); }, [load]);

  const stats = useMemo(() => bucketStats(entries ?? []), [entries]);
  const p = item.progress;

  return (
    <section>
      <SectionLabel>item stats</SectionLabel>
      <Card>
        {entries === null ? (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3 text-center">
              <StatCell label="meaning" value={pct(stats.meaning)} sub={`${stats.meaning.correct}/${stats.meaning.total}`} />
              <StatCell label="reading" value={pct(stats.reading)} sub={`${stats.reading.correct}/${stats.reading.total}`} />
              <StatCell label="combined" value={pct(stats.combined)} sub={`${stats.combined.correct}/${stats.combined.total}`} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 border-t border-terraza-dash pt-4 text-sm">
              <div>
                <p className="text-xs tracking-label text-terraza-soft">UNLOCK DATE</p>
                <p>{shortDate(p.unlocked_at)}</p>
              </div>
              <div>
                <p className="text-xs tracking-label text-terraza-soft">RETIRING DATE</p>
                <p>{p.fluent_at ? shortDate(p.fluent_at) : "not yet"}</p>
              </div>
            </div>
            {stats.combined.total === 0 && (
              <p className="mt-3 text-sm text-terraza-soft">no reviews yet — stats appear once you start reviewing.</p>
            )}
          </>
        )}
      </Card>
    </section>
  );
}

function StatCell({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div>
      <p className="text-3xl tracking-cozy text-terraza-ink">{value}</p>
      <p className="text-xs tracking-label text-terraza-soft">{label.toUpperCase()}</p>
      <p className="text-xs text-terraza-soft">{sub}</p>
    </div>
  );
}

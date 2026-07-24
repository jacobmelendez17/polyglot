"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import {
  AccuracyBar, LeechPill, PerfectBadge, PracticeStageRail, SrsPill,
} from "@/components/progress-bits";
import { Protected } from "@/components/protected";
import { Button, Card, Input } from "@/components/ui";
import {
  items, relativeTime,
  type HistoryEntry, type ItemDetail, type UserSynonym,
} from "@/lib/items-api";

const HISTORY_PAGE = 10;

export default function ItemPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <ItemView />
      </main>
    </Protected>
  );
}

function ItemView() {
  const params = useParams();
  const type = String(params.type);
  const id = String(params.id);

  const [item, setItem] = useState<ItemDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setItem(null);
    setError(null);
    items.detail(type, id)
      .then((d) => { if (!cancelled) setItem(d); })
      .catch((e) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [type, id]);

  if (error) {
    return (
      <Card>
        <p className="text-terraza-danger" role="alert">{error}</p>
        <Link href="/levels" className="mt-4 inline-block underline underline-offset-2">
          back to levels
        </Link>
      </Card>
    );
  }
  if (!item) {
    return <p className="mt-10 text-center font-empty italic text-terraza-soft">un momento ~</p>;
  }

  const isVocab = item.item_type === "vocabulary";

  return (
    <>
      <Link
        href={`/levels/${item.level}/progress`}
        className="text-sm text-terraza-soft underline underline-offset-2"
      >
        ← level {item.level} progress
      </Link>

      {/* ---- the word itself ---- */}
      <Card className="mt-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl lowercase tracking-cozy">
            {item.article && <span className="text-terraza-soft">{item.article} </span>}
            {item.term}
          </h1>
          <AudioButton audio={item.audio} label={`hear ${item.term}`} />
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <SrsPill
              stage={item.progress.srs_stage}
              name={item.progress.learned ? item.progress.srs_stage_name : "not started"}
            />
            <PerfectBadge
              perfect={item.progress.perfect}
              ready={item.practice.categories_complete === item.practice.categories_total}
            />
            <LeechPill state={item.progress.leech_state} />
          </div>
        </div>

        <p className="mt-2 text-xl text-terraza-soft">{item.translation || "—"}</p>

        <dl className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          {item.part_of_speech && <Fact label="PART OF SPEECH" value={item.part_of_speech} />}
          {isVocab && item.pronunciation && (
            <Fact label="PRONUNCIATION" value={item.pronunciation} />
          )}
          {isVocab && item.ipa && <Fact label="IPA" value={item.ipa} />}
          {isVocab && item.gender && <Fact label="GENDER" value={item.gender} />}
          {!isVocab && item.structure && <Fact label="STRUCTURE" value={item.structure} />}
          <Fact label="LEVEL" value={`level ${item.level}`} />
        </dl>

        {item.meaning && <p className="mt-5">{item.meaning}</p>}
        {!isVocab && item.explanation && (
          <p className="mt-3 text-terraza-soft">{item.explanation}</p>
        )}

        {item.synonyms.length > 0 && (
          <p className="mt-4 text-sm text-terraza-soft">
            also means: {item.synonyms.join(", ")}
          </p>
        )}
        {isVocab && item.castilian_variant && (
          <p className="mt-1 text-sm text-terraza-soft">
            in spain: {item.castilian_variant}
          </p>
        )}
      </Card>

      {/* ---- example sentences ---- */}
      <section className="mt-4">
        <h2 className="mb-2 text-xs tracking-label text-terraza-soft">EXAMPLES</h2>
        <Card>
          {item.examples.length === 0 ? (
            <p className="font-empty italic text-terraza-soft">
              no example sentences yet ~
            </p>
          ) : (
            <ul className="flex flex-col gap-4">
              {item.examples.map((ex) => (
                <li key={ex.id} className="flex items-start gap-3">
                  <AudioButton audio={ex.audio} label={`hear: ${ex.text_es}`} />
                  <div>
                    <p className="tracking-cozy">{ex.text_es}</p>
                    {ex.text_en && (
                      <p className="text-sm text-terraza-soft">{ex.text_en}</p>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {/* ---- progress ---- */}
      <section className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <h2 className="mb-2 text-xs tracking-label text-terraza-soft">YOUR PROGRESS</h2>
          <Card>
            {!item.progress.learned ? (
              <p className="font-empty italic text-terraza-soft">
                you have not learned this one yet ~
              </p>
            ) : (
              <>
                <AccuracyBar
                  correct={item.progress.answers_correct}
                  total={item.progress.answers_total}
                />
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                  <Fact
                    label="NEXT REVIEW"
                    value={
                      item.progress.next_review_at
                        ? relativeTime(item.progress.next_review_at)
                        : "out of the queue"
                    }
                  />
                  <Fact label="REVIEWS" value={String(item.progress.total_reviews)} />
                  <Fact label="MISTAKES" value={String(item.progress.mistakes)} />
                  <Fact
                    label="LEARNED"
                    value={relativeTime(item.progress.lesson_completed_at)}
                  />
                </dl>
              </>
            )}
          </Card>
        </div>

        <div>
          <h2 className="mb-2 text-xs tracking-label text-terraza-soft">PRACTICE STAGES</h2>
          <Card>
            <PracticeStageRail stages={item.practice.stages} />
            <p className="mt-4 text-sm text-terraza-soft">
              {item.progress.perfect
                ? "perfect — every category finished and fluent in reviews."
                : `${item.practice.categories_complete} of ${item.practice.categories_total} categories finished` +
                  (item.practice.srs_fluent ? "" : " · fluent in reviews still needed")}
            </p>
            <p className="mt-1 text-xs text-terraza-soft">
              one stage per category per day — practice is spaced too.
            </p>
          </Card>
        </div>
      </section>

      <SynonymEditor
        type={type}
        id={id}
        initial={item.user_synonyms}
      />

      <HistoryPanel type={type} id={id} />
    </>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs tracking-label text-terraza-soft">{label}</dt>
      <dd className="mt-0.5 lowercase tracking-cozy">{value}</dd>
    </div>
  );
}

// --- your synonyms --------------------------------------------------------

function SynonymEditor({
  type, id, initial,
}: { type: string; id: string; initial: UserSynonym[] }) {
  const [list, setList] = useState<UserSynonym[]>(initial);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => { setList(initial); }, [initial]);

  async function add() {
    const trimmed = value.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await items.addSynonym(type, id, trimmed);
      if (created.created) {
        setList((l) => [...l, { id: created.id, synonym: created.synonym }]);
      } else {
        setNotice("you already added that one.");
      }
      setValue("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add that synonym.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(synonymId: string) {
    const previous = list;
    setList((l) => l.filter((s) => s.id !== synonymId));   // optimistic
    try {
      await items.removeSynonym(synonymId);
    } catch (e) {
      setList(previous);
      setError(e instanceof Error ? e.message : "Could not remove that synonym.");
    }
  }

  return (
    <section className="mt-4">
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">YOUR SYNONYMS</h2>
      <Card>
        <p className="text-sm text-terraza-soft">
          add answers you would accept for yourself. they count as correct only
          while &ldquo;accept my synonyms&rdquo; is on in settings.
        </p>

        <div className="mt-4 flex gap-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
            placeholder="another way to say it…"
            maxLength={60}
            aria-label="New synonym"
            disabled={busy}
          />
          <Button onClick={add} disabled={!value.trim() || busy}>
            {busy ? "adding…" : "add"}
          </Button>
        </div>

        {error && (
          <p role="alert" className="mt-3 text-sm text-terraza-danger">{error}</p>
        )}
        {notice && <p className="mt-3 text-sm text-terraza-soft">{notice}</p>}

        {list.length === 0 ? (
          <p className="mt-4 font-empty italic text-terraza-soft">
            no synonyms of your own yet ~
          </p>
        ) : (
          <ul className="mt-4 flex flex-wrap gap-2">
            {list.map((s) => (
              <li key={s.id}>
                <span className="inline-flex items-center gap-2 rounded-full bg-terraza-pill px-3 py-1 text-sm">
                  {s.synonym}
                  <button
                    onClick={() => remove(s.id)}
                    aria-label={`Remove synonym ${s.synonym}`}
                    className="text-terraza-soft hover:text-terraza-ink"
                  >
                    ×
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </section>
  );
}

// --- review history -------------------------------------------------------

function HistoryPanel({ type, id }: { type: string; id: string }) {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (offset: number) => {
    setLoading(true);
    setError(null);
    try {
      const page = await items.history(type, id, HISTORY_PAGE, offset);
      setTotal(page.total);
      setEntries((prev) => (offset === 0 ? page.items : [...(prev ?? []), ...page.items]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load your history.");
    } finally {
      setLoading(false);
    }
  }, [type, id]);

  useEffect(() => { load(0); }, [load]);

  return (
    <section className="mt-4 mb-10">
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">REVIEW HISTORY</h2>
      <Card>
        {error && <p role="alert" className="text-terraza-danger">{error}</p>}
        {!entries && !error && (
          <p className="font-empty italic text-terraza-soft">un momento ~</p>
        )}
        {entries && entries.length === 0 && (
          <p className="font-empty italic text-terraza-soft">
            nothing here yet — this item has not come up in a review ~
          </p>
        )}
        {entries && entries.length > 0 && (
          <ul className="flex flex-col divide-y divide-terraza-dash">
            {entries.map((e) => (
              <li key={e.id} className="flex items-center gap-3 py-2 text-sm">
                <span aria-hidden="true">{e.final_correct ? "✓" : "✕"}</span>
                <span className="sr-only">
                  {e.final_correct ? "correct" : "incorrect"}
                </span>
                <span className="tracking-cozy">{e.submitted_answer || "—"}</span>
                <span className="text-xs text-terraza-soft">
                  {e.direction === "es_to_en" ? "es→en" : "en→es"}
                </span>
                {e.undo_used && (
                  <span className="rounded-full bg-terraza-pill px-2 py-0.5 text-xs">
                    undone
                  </span>
                )}
                {e.typo_forgiven && (
                  <span className="rounded-full bg-terraza-pill px-2 py-0.5 text-xs">
                    typo
                  </span>
                )}
                <span className="ml-auto text-xs text-terraza-soft">
                  {relativeTime(e.answered_at)}
                </span>
              </li>
            ))}
          </ul>
        )}

        {entries && entries.length < total && (
          <button
            onClick={() => load(entries.length)}
            disabled={loading}
            className="mt-4 rounded-full bg-terraza-pill px-5 py-2 text-sm tracking-cozy disabled:opacity-50"
          >
            {loading ? "loading…" : `show more (${total - entries.length} left)`}
          </button>
        )}
      </Card>
    </section>
  );
}

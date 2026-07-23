"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { AudioButton } from "@/components/audio-button";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { CATEGORY_LABELS, items, type ItemProgress } from "@/lib/learn-api";

const LEECH_META: Record<string, { label: string; bg: string }> = {
  critical: { label: "critical", bg: "bg-terraza-danger text-white" },
  leech: { label: "leech", bg: "bg-terraza-pink" },
  watch: { label: "watch", bg: "bg-terraza-gold" },
};

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const diffMs = new Date(iso).getTime() - Date.now();
  const abs = Math.abs(diffMs);
  const future = diffMs > 0;
  const hours = abs / 36e5;
  let amount: string;
  if (hours < 1) amount = `${Math.max(1, Math.round(abs / 6e4))} min`;
  else if (hours < 48) amount = `${Math.round(hours)} h`;
  else amount = `${Math.round(hours / 24)} d`;
  return future ? `in ${amount}` : `${amount} ago`;
}

export default function ItemDetailPage() {
  const params = useParams();
  const type = String(params.type);
  const id = String(params.id);
  const [item, setItem] = useState<ItemProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!type || !id) return;
    items.progress(type, id).then(setItem).catch((e) => setError(e.message));
  }, [type, id]);

  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Link href="/items" className="text-sm text-terraza-soft">← your items</Link>

        {error && <Card className="mt-4"><p className="text-terraza-danger">{error}</p></Card>}
        {!item && !error && (
          <p className="mt-8 font-empty italic text-terraza-soft">un momento ~</p>
        )}

        {item && (
          <>
            <Card className="mt-4 text-center">
              <span className="text-xs tracking-label text-terraza-soft">
                {(item.part_of_speech || type).toUpperCase()} {item.level ? `· LEVEL ${item.level}` : ""}
              </span>
              <div className="mt-3 flex items-center justify-center gap-3">
                <p className="text-3xl lowercase tracking-cozy">{item.term}</p>
                <AudioButton audio={item.audio} label={`hear ${item.term}`} />
              </div>
              <p className="mt-2 text-lg text-terraza-accent">{item.translation}</p>
              {item.perfect_at && (
                <p className="mt-3 tracking-cozy">✦ perfect — fully mastered ✦</p>
              )}
            </Card>

            {/* ---- SRS status ---- */}
            <Card className="mt-4">
              <div className="mb-3 text-xs tracking-label text-terraza-soft">SPACED REPETITION</div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-terraza-pill px-3 py-1 text-sm tracking-cozy">
                  {item.srs_stage_name}
                </span>
                {LEECH_META[item.leech_state] && (
                  <span className={`rounded-full px-3 py-1 text-xs tracking-label ${LEECH_META[item.leech_state].bg}`}>
                    {LEECH_META[item.leech_state].label.toUpperCase()}
                  </span>
                )}
                <span className="text-sm text-terraza-soft">
                  {item.next_review_at ? `next review ${relativeTime(item.next_review_at)}` : "not in the review queue"}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3 text-center">
                <div>
                  <p className="text-xl lowercase tracking-cozy">{item.total_reviews}</p>
                  <p className="text-[10px] tracking-label text-terraza-soft">REVIEWS</p>
                </div>
                <div>
                  <p className="text-xl lowercase tracking-cozy">{item.accuracy ?? "—"}{item.accuracy !== null ? "%" : ""}</p>
                  <p className="text-[10px] tracking-label text-terraza-soft">ACCURACY</p>
                </div>
                <div>
                  <p className="text-xl lowercase tracking-cozy">{item.total_incorrect}</p>
                  <p className="text-[10px] tracking-label text-terraza-soft">MISSED</p>
                </div>
              </div>
            </Card>

            {/* ---- practice stages ---- */}
            <Card className="mt-4">
              <div className="mb-3 text-xs tracking-label text-terraza-soft">PRACTICE STAGES</div>
              <div className="flex flex-col gap-3">
                {item.practice_stages.map((p) => (
                  <div key={p.category} className={!p.live ? "opacity-50" : ""}>
                    <div className="flex items-baseline justify-between">
                      <span className="lowercase tracking-cozy">{CATEGORY_LABELS[p.category] ?? p.category}</span>
                      <span className="text-xs text-terraza-soft">
                        {!p.live ? "coming soon"
                          : p.stage >= p.max_stage ? "cinco ✦"
                          : p.stage_name ? `${p.stage_name} (${p.stage}/${p.max_stage})`
                          : "not started"}
                      </span>
                    </div>
                    <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-terraza-pill">
                      <div className="h-full rounded-full bg-terraza-accent transition-all"
                           style={{ width: `${(p.stage / p.max_stage) * 100}%` }} />
                    </div>
                    {p.live && p.next_stage_at && (
                      <p className="mt-1 text-[11px] text-terraza-soft">
                        next stage available {relativeTime(p.next_stage_at)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </Card>

            {/* ---- history ---- */}
            <Card className="mt-4">
              <div className="mb-3 text-xs tracking-label text-terraza-soft">HISTORY</div>
              {item.history.length === 0 ? (
                <p className="font-empty italic text-terraza-soft">no reviews yet ~</p>
              ) : (
                <div className="flex flex-col gap-2">
                  {item.history.map((h, i) => (
                    <div key={i} className="flex items-center gap-3 border-b border-terraza-dash pb-2 last:border-0 last:pb-0">
                      <span className={`h-2 w-2 shrink-0 rounded-full ${h.correct ? "bg-terraza-green" : "bg-terraza-danger"}`} />
                      <span className="text-sm">
                        {h.direction === "es_to_en" ? "español → english" : "english → español"}
                      </span>
                      {h.undo_used && (
                        <span className="rounded-full bg-terraza-gold px-2 py-0.5 text-[10px] tracking-label">UNDO</span>
                      )}
                      {h.srs_stage_after !== null && h.srs_stage_before !== null && (
                        <span className="ml-auto text-xs text-terraza-soft">
                          stage {h.srs_stage_before} → {h.srs_stage_after}
                        </span>
                      )}
                      <span className={`text-xs text-terraza-soft ${h.srs_stage_after !== null ? "" : "ml-auto"}`}>
                        {h.answered_at ? new Date(h.answered_at).toLocaleDateString() : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          </>
        )}
      </main>
    </Protected>
  );
}

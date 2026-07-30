"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { feedback, type FeedbackList, type FeedbackTicket } from "@/lib/feedback-api";

// Admin feedback inbox (spec §22, §30). Filterable by unanswered / answered /
// pinned. Gated at the API on feedback_manage; this page also fails gracefully
// with a "not available" card for anyone who reaches it without the capability.

type Filter = "all" | "unanswered" | "answered" | "pinned";

export default function AdminFeedbackPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Inbox />
      </main>
    </Protected>
  );
}

function Inbox() {
  const [data, setData] = useState<FeedbackList | null>(null);
  const [filter, setFilter] = useState<Filter>("unanswered");
  const [forbidden, setForbidden] = useState(false);

  const load = useCallback(() => {
    const state = filter === "unanswered" || filter === "answered" ? filter : undefined;
    const pinned = filter === "pinned" ? true : undefined;
    feedback.list(state, pinned)
      .then(setData)
      .catch((e) => { if (e?.status === 403) setForbidden(true); });
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  if (forbidden) {
    return (
      <Card>
        <p className="text-center font-empty italic text-terraza-soft">
          not available on this account ~
        </p>
        <p className="mt-2 text-center text-sm text-terraza-soft">
          the feedback inbox is for admins and moderators.
        </p>
      </Card>
    );
  }

  const filters: { key: Filter; label: string; badge?: number }[] = [
    { key: "unanswered", label: "unanswered", badge: data?.counts.unanswered },
    { key: "answered", label: "answered", badge: data?.counts.answered },
    { key: "pinned", label: "pinned", badge: data?.counts.pinned },
    { key: "all", label: "all" },
  ];

  return (
    <>
      <h1 className="mb-1 text-2xl lowercase tracking-cozy">feedback</h1>
      <p className="mb-5 text-terraza-soft">what people are telling us.</p>

      <div className="mb-5 flex flex-wrap gap-2">
        {filters.map((f) => (
          <button key={f.key} onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={`rounded-full px-4 py-1.5 text-sm tracking-cozy ${
              filter === f.key ? "bg-terraza-accent text-terraza-accentInk" : "bg-terraza-pill"
            }`}>
            {f.label}
            {f.badge ? <span className="ml-2 opacity-70">{f.badge}</span> : null}
          </button>
        ))}
      </div>

      {!data ? (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      ) : data.tickets.length === 0 ? (
        <Card><p className="text-center font-empty italic text-terraza-soft">nothing here ~</p></Card>
      ) : (
        <ul className="flex flex-col gap-3">
          {data.tickets.map((t) => (
            <TicketCard key={t.id} ticket={t} onChange={load} />
          ))}
        </ul>
      )}
    </>
  );
}

function TicketCard({ ticket, onChange }: { ticket: FeedbackTicket; onChange: () => void }) {
  const [response, setResponse] = useState(ticket.admin_response || "");
  const [busy, setBusy] = useState(false);
  const [replying, setReplying] = useState(false);

  async function respond() {
    setBusy(true);
    try { await feedback.respond(ticket.id, response); onChange(); setReplying(false); }
    finally { setBusy(false); }
  }
  async function togglePin() {
    setBusy(true);
    try { await feedback.pin(ticket.id, !ticket.pinned); onChange(); }
    finally { setBusy(false); }
  }

  return (
    <li>
      <Card>
        <div className="flex items-baseline gap-2">
          <span className="rounded-full bg-terraza-pill px-2 py-0.5 text-[10px] tracking-label">
            {ticket.category.toUpperCase()}
          </span>
          {ticket.state === "answered" && (
            <span className="rounded-full bg-terraza-green px-2 py-0.5 text-[10px] tracking-label">
              ANSWERED
            </span>
          )}
          {ticket.pinned && <span aria-label="pinned">📌</span>}
          <span className="ml-auto text-xs text-terraza-soft">{ticket.from_email}</span>
        </div>

        <p className="mt-2 whitespace-pre-wrap leading-relaxed">{ticket.body}</p>

        <p className="mt-2 text-xs text-terraza-soft">
          {ticket.route && <>on <code>{ticket.route}</code> · </>}
          {ticket.browser && <span title={ticket.browser}>browser noted · </span>}
          {ticket.email_sent ? "emailed to owner" : "not emailed"}
        </p>

        {ticket.admin_response && !replying && (
          <div className="mt-3 rounded-card bg-terraza-pill px-3 py-2 text-sm">
            <span className="text-xs tracking-label text-terraza-soft">YOUR REPLY</span>
            <p className="mt-1 whitespace-pre-wrap">{ticket.admin_response}</p>
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
          <button onClick={() => setReplying((r) => !r)} disabled={busy}
            className="underline underline-offset-2">
            {ticket.admin_response ? "edit reply" : "reply"}
          </button>
          <button onClick={togglePin} disabled={busy} className="underline underline-offset-2">
            {ticket.pinned ? "unpin" : "pin"}
          </button>
        </div>

        {replying && (
          <div className="mt-3 flex flex-col gap-2">
            <textarea value={response} onChange={(e) => setResponse(e.target.value)}
              rows={3} maxLength={5000}
              className="w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink"
              placeholder="write a reply…" />
            <button onClick={respond} disabled={busy || !response.trim()}
              className="self-start rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk disabled:opacity-50">
              {busy ? "un momento…" : "save reply"}
            </button>
          </div>
        )}
      </Card>
    </li>
  );
}

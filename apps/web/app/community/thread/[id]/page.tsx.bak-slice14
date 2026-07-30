"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, FormError } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { forums, type ThreadDetail } from "@/lib/forums-api";

// A thread: the original post, its replies, a composer, and — for moderators —
// hide/delete controls. Anyone can report; the report button quietly confirms
// rather than announcing to the room that a post was flagged.

export default function ThreadPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <ThreadView />
      </main>
      <Footer />
    </Protected>
  );
}

function ThreadView() {
  const id = String(useParams().id);
  const { me } = useAuth();
  const isMod = me?.capabilities?.includes("forum_moderate") ?? false;

  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [postingOpen, setPostingOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    forums.thread(id).then(setThread).catch((e) => setError(e.message));
  }, [id]);

  useEffect(() => {
    load();
    forums.postingState().then((s) => setPostingOpen(s.posting_enabled)).catch(() => {});
  }, [load]);

  if (error) return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  if (!thread) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <>
      <Link
        href={thread.category ? `/community/${thread.category.slug}` : "/community"}
        className="text-sm text-terraza-soft underline underline-offset-2"
      >
        ← {thread.category?.title ?? "community"}
      </Link>

      <article className="mt-3">
        <div className="flex items-baseline gap-2">
          <h1 className="mr-auto text-2xl lowercase tracking-cozy">{thread.title}</h1>
          {thread.hidden && (
            <span className="rounded-full bg-terraza-gold px-2 py-0.5 text-[10px] tracking-label">
              HIDDEN
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-terraza-soft">by {thread.author}</p>

        <Card className="mt-4">
          <Body text={thread.body} />
          <PostActions
            targetType="thread" targetId={thread.id} isMod={isMod}
            hidden={thread.hidden} onChange={load}
          />
        </Card>
      </article>

      <section className="mt-6">
        <h2 className="mb-3 text-xs tracking-label text-terraza-soft">
          {thread.reply_total} {thread.reply_total === 1 ? "REPLY" : "REPLIES"}
        </h2>

        {thread.replies.length === 0 ? (
          <p className="font-empty italic text-terraza-soft">no replies yet ~</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {thread.replies.map((r) => (
              <li key={r.id}>
                <Card>
                  <div className="mb-1 flex items-baseline gap-2">
                    <span className="text-sm tracking-cozy">{r.author}</span>
                    {r.hidden && (
                      <span className="rounded-full bg-terraza-gold px-2 py-0.5 text-[10px] tracking-label">
                        HIDDEN
                      </span>
                    )}
                  </div>
                  <Body text={r.body} />
                  <PostActions
                    targetType="reply" targetId={r.id} isMod={isMod}
                    hidden={r.hidden} onChange={load}
                  />
                </Card>
              </li>
            ))}
          </ul>
        )}

        {postingOpen && !thread.locked && (
          <ReplyComposer threadId={thread.id} onDone={load} />
        )}
        {thread.locked && (
          <p className="mt-4 text-sm text-terraza-soft">this thread is locked.</p>
        )}
      </section>
    </>
  );
}

function Body({ text }: { text: string }) {
  // Rendered as plain text paragraphs — never innerHTML. The server sanitizes
  // on the way in; this is the second layer.
  return (
    <div className="flex flex-col gap-2 leading-relaxed">
      {text.split("\n\n").map((para, i) => <p key={i}>{para}</p>)}
    </div>
  );
}

function PostActions({
  targetType, targetId, isMod, hidden, onChange,
}: {
  targetType: "thread" | "reply"; targetId: string; isMod: boolean;
  hidden: boolean; onChange: () => void;
}) {
  const [reported, setReported] = useState(false);
  const [busy, setBusy] = useState(false);

  async function report() {
    setBusy(true);
    try {
      await forums.report(targetType, targetId, "abuse");
      setReported(true);
    } catch { /* keep quiet — a failed report shouldn't derail reading */ }
    finally { setBusy(false); }
  }

  async function moderate(action: "hide" | "unhide" | "delete") {
    setBusy(true);
    try {
      await forums.moderate(targetType, targetId, action);
      onChange();
    } finally { setBusy(false); }
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-terraza-soft">
      {reported ? (
        <span>reported — thank you ✦</span>
      ) : (
        <button onClick={report} disabled={busy} className="underline underline-offset-2">
          report
        </button>
      )}
      {isMod && (
        <>
          <span aria-hidden="true">·</span>
          <button
            onClick={() => moderate(hidden ? "unhide" : "hide")}
            disabled={busy}
            className="underline underline-offset-2"
          >
            {hidden ? "unhide" : "hide"}
          </button>
          <button
            onClick={() => moderate("delete")}
            disabled={busy}
            className="text-terraza-danger underline underline-offset-2"
          >
            delete
          </button>
        </>
      )}
    </div>
  );
}

function ReplyComposer({ threadId, onDone }: { threadId: string; onDone: () => void }) {
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forums.createReply(threadId, body);
      setBody("");
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not post your reply.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mt-5">
      <form onSubmit={submit} className="flex flex-col gap-3" noValidate>
        <label htmlFor="reply" className="text-xs tracking-label text-terraza-soft">
          ADD A REPLY
        </label>
        <textarea
          id="reply" value={body} onChange={(e) => setBody(e.target.value)}
          maxLength={10000} rows={4} required
          className="w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink"
          placeholder="share what you know…"
        />
        <FormError message={error} />
        <Button type="submit" disabled={submitting || !body}>
          {submitting ? "un momento…" : "post reply"}
        </Button>
      </form>
    </Card>
  );
}

"use client";

// A shared journal entry with its feedback thread (spec §7). Read the entry, leave
// feedback, and — if you moderate — hide a comment or the whole entry. The body is
// rendered as plain-text paragraphs (never innerHTML). Loading / error / empty
// states throughout.

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { communityJournals, type CommunityEntry } from "@/lib/community-journal-api";

function Paragraphs({ text }: { text: string }) {
  return (
    <>
      {text.split(/\n{2,}/).map((p, i) => (
        <p key={i} className="mb-3 whitespace-pre-wrap leading-relaxed" lang="es">{p}</p>
      ))}
    </>
  );
}

export default function CommunityEntryPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Entry />
      </main>
    </Protected>
  );
}

function Entry() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const isMod = ["moderator", "admin", "owner"].includes(user?.role ?? "");

  const [entry, setEntry] = useState<CommunityEntry | null>(null);
  const [status, setStatus] = useState<"loading" | "ok" | "notfound" | "error">("loading");
  const [draft, setDraft] = useState("");
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState<string | null>(null);

  async function load() {
    setStatus("loading");
    try {
      setEntry(await communityJournals.entry(id));
      setStatus("ok");
    } catch (e) {
      setStatus((e as { status?: number })?.status === 404 ? "notfound" : "error");
    }
  }
  useEffect(() => { if (id) load(); }, [id]);

  async function submit() {
    if (!draft.trim()) return;
    setPosting(true); setPostError(null);
    try {
      await communityJournals.postFeedback(id, draft);
      setDraft("");
      await load();
    } catch (e) {
      setPostError((e as { message?: string })?.message ?? "couldn't post — try again.");
    } finally { setPosting(false); }
  }

  async function hideFeedback(fid: string) {
    await communityJournals.hideFeedback(fid, true, "hidden by moderator");
    load();
  }
  async function hideEntry() {
    await communityJournals.hideEntry(id, true, "hidden by moderator");
    load();
  }

  if (status === "loading") return <Card><p className="font-empty italic text-terraza-soft">un momento ~</p></Card>;
  if (status === "notfound")
    return (
      <Card>
        <p className="font-empty italic text-terraza-soft">this entry isn&apos;t available.</p>
        <Link href="/community/journals" className="mt-3 inline-block text-sm text-terraza-accent">← back to journals</Link>
      </Card>
    );
  if (status === "error" || !entry)
    return (
      <Card>
        <p role="alert" className="text-terraza-danger">couldn&apos;t load this entry.</p>
        <Button className="mt-3" onClick={load}>try again</Button>
      </Card>
    );

  return (
    <div>
      <Link href="/community/journals" className="text-sm text-terraza-accent">← journals</Link>

      <Card className="mt-3">
        <div className="flex items-baseline justify-between gap-2">
          <h1 className="text-xl lowercase tracking-cozy">{entry.title || "untitled"}</h1>
          <span className="shrink-0 text-sm text-terraza-soft">{entry.author}</span>
        </div>
        <div className="mt-4"><Paragraphs text={entry.body} /></div>
        {isMod && !entry.is_owner && (
          <button onClick={hideEntry}
            className="mt-2 text-xs text-terraza-danger underline">hide this entry (mod)</button>
        )}
      </Card>

      <h2 className="mb-2 mt-6 text-xs tracking-label text-terraza-soft">
        FEEDBACK · {entry.feedback.length}
      </h2>
      {entry.feedback.length === 0 ? (
        <p className="mb-4 font-empty italic text-terraza-soft">no feedback yet — be the first.</p>
      ) : (
        <div className="mb-4 flex flex-col gap-2">
          {entry.feedback.map((f) => (
            <Card key={f.id} className={f.hidden ? "opacity-60" : ""}>
              <div className="flex items-baseline justify-between">
                <span className="text-sm tracking-cozy">{f.author}</span>
                {f.hidden && <span className="text-xs text-terraza-danger">hidden</span>}
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm">{f.body}</p>
              {isMod && !f.hidden && (
                <button onClick={() => hideFeedback(f.id)}
                  className="mt-1 text-xs text-terraza-danger underline">hide (mod)</button>
              )}
            </Card>
          ))}
        </div>
      )}

      <Card>
        <label htmlFor="fb" className="text-xs tracking-label text-terraza-soft">LEAVE FEEDBACK</label>
        <textarea id="fb" value={draft} onChange={(e) => setDraft(e.target.value)}
          rows={3} maxLength={3000} placeholder="be kind and specific — what worked, what to try next…"
          className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2" />
        {postError && <p role="alert" className="mt-1 text-sm text-terraza-danger">{postError}</p>}
        <div className="mt-2 flex justify-end">
          <Button onClick={submit} disabled={posting || !draft.trim()}>
            {posting ? "posting…" : "post feedback"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

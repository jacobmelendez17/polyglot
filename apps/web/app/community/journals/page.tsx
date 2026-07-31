"use client";

// Community journals (spec §7). Two sections: the community feed of shared entries,
// and "your journal" where you share or unshare your own entries. Sharing is
// explicit and reversible; a private entry never appears in the feed. A small tab
// bar links to forums so navigation works regardless of other nav. Loading, empty,
// and error states throughout; nothing relies on colour alone (a shared entry is
// labelled "shared", not just tinted).

import Link from "next/link";
import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { communityJournals, type FeedItem, type MyEntry } from "@/lib/community-journal-api";

function Tabs() {
  return (
    <div className="mb-6 flex gap-2 text-sm">
      <Link href="/community" className="rounded-full px-4 py-1.5 text-terraza-soft hover:bg-terraza-pill">forums</Link>
      <span className="rounded-full bg-terraza-pill px-4 py-1.5 tracking-cozy">journals</span>
    </div>
  );
}

export default function CommunityJournalsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <h1 className="text-2xl lowercase tracking-cozy">community journals</h1>
        <p className="mt-1 mb-4 text-terraza-soft">
          share an entry to get feedback from other learners — or read theirs and help out.
          your journal stays private until you choose to share it.
        </p>
        <Tabs />
        <YourEntries />
        <Feed />
      </main>
    </Protected>
  );
}

function YourEntries() {
  const [entries, setEntries] = useState<MyEntry[] | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try { setEntries(await communityJournals.mine()); }
    catch { setError(true); }
  }
  useEffect(() => { load(); }, []);

  async function toggle(e: MyEntry) {
    setBusy(e.id);
    try {
      if (e.shared) await communityJournals.unshare(e.id);
      else await communityJournals.share(e.id);
      await load();
    } finally { setBusy(null); }
  }

  return (
    <section className="mb-8">
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">YOUR JOURNAL</h2>
      {error ? (
        <p role="alert" className="text-sm text-terraza-danger">couldn&apos;t load your entries.</p>
      ) : entries === null ? (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      ) : entries.length === 0 ? (
        <Card><p className="font-empty italic text-terraza-soft">
          no entries yet — write one in your <Link href="/journal" className="underline">journal</Link> first.
        </p></Card>
      ) : (
        <div className="flex flex-col gap-2">
          {entries.map((e) => (
            <Card key={e.id} className="flex items-center gap-3">
              <div className="min-w-0 flex-1">
                <p className="truncate lowercase tracking-cozy">{e.title || "untitled"}</p>
                <p className="truncate text-sm text-terraza-soft">{e.excerpt || "—"}</p>
                <p className="mt-1 text-xs">
                  {e.shared
                    ? <span className="text-terraza-green">● shared{e.feedback_count ? ` · ${e.feedback_count} comment${e.feedback_count === 1 ? "" : "s"}` : ""}</span>
                    : <span className="text-terraza-soft">○ private</span>}
                </p>
              </div>
              <button onClick={() => toggle(e)} disabled={busy === e.id}
                className={`shrink-0 rounded-full px-4 py-1.5 text-sm tracking-cozy disabled:opacity-50 ${
                  e.shared ? "bg-terraza-pill" : "bg-terraza-accent text-terraza-accentInk"
                }`}>
                {busy === e.id ? "…" : e.shared ? "unshare" : "share"}
              </button>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function Feed() {
  const [feed, setFeed] = useState<FeedItem[] | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    communityJournals.feed().then(setFeed).catch(() => setError(true));
  }, []);

  return (
    <section>
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">FROM THE COMMUNITY</h2>
      {error ? (
        <p role="alert" className="text-sm text-terraza-danger">couldn&apos;t load the feed.</p>
      ) : feed === null ? (
        <p className="font-empty italic text-terraza-soft">un momento ~</p>
      ) : feed.length === 0 ? (
        <Card><p className="font-empty italic text-terraza-soft">
          nothing shared yet — be the first to share an entry.
        </p></Card>
      ) : (
        <div className="flex flex-col gap-2">
          {feed.map((item) => (
            <Link key={item.id} href={`/community/journals/${item.id}`}>
              <Card className="transition-transform hover:-translate-y-0.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate lowercase tracking-cozy">{item.title || "untitled"}</p>
                  <span className="shrink-0 text-xs text-terraza-soft">{item.author}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-terraza-soft">{item.excerpt || "—"}</p>
                <p className="mt-2 text-xs text-terraza-accent">
                  {item.feedback_count} comment{item.feedback_count === 1 ? "" : "s"} · read & reply →
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}

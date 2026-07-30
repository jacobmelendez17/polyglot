"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, FormError, Input, Label } from "@/components/ui";
import { forums, type ThreadList } from "@/lib/forums-api";

export default function CategoryPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-8">
        <CategoryView />
      </main>
      <Footer />
    </Protected>
  );
}

function CategoryView() {
  const slug = String(useParams().slug);
  const [data, setData] = useState<ThreadList | null>(null);
  const [postingOpen, setPostingOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [composing, setComposing] = useState(false);

  const load = useCallback(() => {
    forums.threads(slug).then(setData).catch((e) => setError(e.message));
  }, [slug]);

  useEffect(() => {
    load();
    forums.postingState().then((s) => setPostingOpen(s.posting_enabled)).catch(() => {});
  }, [load]);

  if (error) return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  if (!data) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <>
      <Link href="/community" className="text-sm text-terraza-soft underline underline-offset-2">
        ← community
      </Link>
      <div className="mb-5 mt-2 flex flex-wrap items-baseline gap-3">
        <h1 className="text-2xl lowercase tracking-cozy">{data.category.title}</h1>
        {postingOpen && !data.category.locked && (
          <button
            onClick={() => setComposing((c) => !c)}
            className="ml-auto rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk"
          >
            {composing ? "cancel" : "new thread"}
          </button>
        )}
      </div>
      <p className="mb-6 text-terraza-soft">{data.category.description}</p>

      {composing && (
        <NewThread slug={slug} onDone={() => { setComposing(false); load(); }} />
      )}

      {data.threads.length === 0 ? (
        <Card>
          <p className="text-center font-empty italic text-terraza-soft">
            no threads here yet ~
          </p>
          {postingOpen && (
            <p className="mt-2 text-center text-sm text-terraza-soft">
              be the first to start one.
            </p>
          )}
        </Card>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.threads.map((t) => (
            <li key={t.id}>
              <Link
                href={`/community/thread/${t.id}`}
                className="block rounded-card border border-terraza-dash bg-terraza-card p-4 transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
              >
                <div className="flex items-baseline gap-2">
                  {t.pinned && <span aria-label="pinned" title="pinned">📌</span>}
                  <span className="mr-auto lowercase tracking-cozy">{t.title}</span>
                  <span className="text-xs text-terraza-soft">
                    {t.reply_count} {t.reply_count === 1 ? "reply" : "replies"}
                  </span>
                </div>
                <p className="mt-1 text-sm text-terraza-soft">by {t.author}</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function NewThread({ slug, onDone }: { slug: string; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await forums.createThread(slug, title, body);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not post your thread.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="mb-5">
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <div>
          <Label htmlFor="title">title</Label>
          <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)}
                 maxLength={160} placeholder="a short, clear question" required />
        </div>
        <div>
          <Label htmlFor="body">your post</Label>
          <textarea
            id="body" value={body} onChange={(e) => setBody(e.target.value)}
            maxLength={10000} rows={5} required
            className="w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink"
            placeholder="give as much detail as you can…"
          />
        </div>
        <FormError message={error} />
        <Button type="submit" disabled={submitting || !title || !body}>
          {submitting ? "un momento…" : "post thread"}
        </Button>
      </form>
    </Card>
  );
}

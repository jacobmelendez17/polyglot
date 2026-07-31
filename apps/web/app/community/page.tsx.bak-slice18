"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { forums, type ForumCategory } from "@/lib/forums-api";

// Community home (spec §18). A grid of categories, browsable by anyone. A quiet
// banner notes when posting is still closed — the forums are readable before
// they're writable, so this sets expectations rather than hiding the feature.

export default function CommunityPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="mb-1 text-2xl lowercase tracking-cozy">community</h1>
        <p className="mb-6 text-terraza-soft">
          ask questions, help others, and swap what&apos;s working. be kind — everyone
          here is learning.
        </p>
        <Categories />
      </main>
      <Footer />
    </Protected>
  );
}

function Categories() {
  const [cats, setCats] = useState<ForumCategory[] | null>(null);
  const [postingOpen, setPostingOpen] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    forums.categories().then(setCats).catch((e) => setError(e.message));
    forums.postingState()
      .then((s) => setPostingOpen(s.posting_enabled))
      .catch(() => setPostingOpen(false));
  }, []);

  if (error) return <Card><p role="alert" className="text-terraza-danger">{error}</p></Card>;
  if (!cats) return <p className="font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <>
      {postingOpen === false && (
        <div className="mb-5 rounded-card border border-terraza-dash bg-terraza-pill px-4 py-3 text-sm text-terraza-soft">
          the forums are open to read while we get them ready. posting opens soon ✦
        </div>
      )}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {cats.map((cat) => (
          <Link key={cat.slug} href={`/community/${cat.slug}`}>
            <Card className="h-full transition-transform duration-200 hover:-translate-y-1 motion-reduce:transition-none motion-reduce:hover:translate-y-0">
              <div className="flex items-baseline gap-2">
                <p className="mr-auto text-lg lowercase tracking-cozy">{cat.title}</p>
                <span className="text-xs tracking-label text-terraza-soft">
                  {cat.thread_count} {cat.thread_count === 1 ? "THREAD" : "THREADS"}
                </span>
              </div>
              <p className="mt-2 text-sm text-terraza-soft">{cat.description}</p>
            </Card>
          </Link>
        ))}
      </div>
    </>
  );
}

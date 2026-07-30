"use client";

import Link from "next/link";
import { useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card, FormError } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { feedback, type FeedbackCategory } from "@/lib/feedback-api";

// Support page (spec §21 footer, §30). A fuller version of the feedback form for
// people who arrive here deliberately to ask for help or send a suggestion.
// Same backend as the floating button.

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: "question", label: "a question" },
  { value: "bug", label: "a bug" },
  { value: "feature", label: "a suggestion" },
  { value: "other", label: "something else" },
];

export default function SupportPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl lowercase tracking-cozy">support</h1>
        <p className="mt-3 text-terraza-soft">
          polyglot is in beta and built by one person — your notes genuinely shape
          what gets built next. tell me what&apos;s working, what isn&apos;t, or what you wish
          existed.
        </p>
        <div className="mt-8">
          <SupportForm />
        </div>
        <p className="mt-8 text-sm text-terraza-soft">
          looking for common questions first? see the{" "}
          <Link href="/faq" className="underline underline-offset-2">faq</Link>.
        </p>
      </main>
      <Footer />
    </Protected>
  );
}

function SupportForm() {
  const { user } = useAuth();
  const [category, setCategory] = useState<FeedbackCategory>("question");
  const [body, setBody] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    setError(null);
    try {
      const browser = typeof navigator !== "undefined" ? navigator.userAgent : "";
      await feedback.submit(category, body, "/support", browser);
      setState("sent");
      setBody("");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Could not send. Try again.");
    }
  }

  if (state === "sent") {
    return (
      <Card>
        <div className="py-6 text-center">
          <p className="text-lg lowercase tracking-cozy">thank you ✦</p>
          <p className="mt-2 text-sm text-terraza-soft">
            i&apos;ll read it{user?.email ? ` and may reply to ${user.email}` : ""}.
          </p>
          <button onClick={() => setState("idle")}
            className="mt-5 rounded-full bg-terraza-pill px-6 py-2 tracking-cozy">
            send another
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <div>
          <span className="text-xs tracking-label text-terraza-soft">THIS IS…</span>
          <div className="mt-2 flex flex-wrap gap-2">
            {CATEGORIES.map((c) => (
              <button key={c.value} type="button" onClick={() => setCategory(c.value)}
                aria-pressed={category === c.value}
                className={`rounded-full px-3 py-1.5 text-sm tracking-cozy ${
                  category === c.value ? "bg-terraza-accent text-terraza-accentInk" : "bg-terraza-pill"
                }`}>
                {c.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label htmlFor="msg" className="text-xs tracking-label text-terraza-soft">MESSAGE</label>
          <textarea id="msg" value={body} onChange={(e) => setBody(e.target.value)}
            rows={6} maxLength={5000} required
            placeholder="tell me what's on your mind…"
            className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink" />
        </div>
        <FormError message={error} />
        <Button type="submit" disabled={state === "sending" || !body.trim()}>
          {state === "sending" ? "un momento…" : "send"}
        </Button>
      </form>
    </Card>
  );
}

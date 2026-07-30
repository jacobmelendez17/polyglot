"use client";

// The feedback button that lives on every page (spec §30). It captures the
// current route and the browser's user-agent automatically, so a bug report
// carries the context needed to reproduce it without asking the user to
// describe where they were. Renders nothing when signed out — a ticket needs an
// author — and respects reduced-motion.

import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { feedback, type FeedbackCategory } from "@/lib/feedback-api";

const CATEGORIES: { value: FeedbackCategory; label: string }[] = [
  { value: "bug", label: "something's broken" },
  { value: "feature", label: "an idea" },
  { value: "question", label: "a question" },
  { value: "other", label: "something else" },
];

export function FeedbackButton() {
  const { user } = useAuth();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [body, setBody] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [error, setError] = useState<string | null>(null);

  if (!user) return null;   // a ticket needs an author

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    setError(null);
    try {
      const browser = typeof navigator !== "undefined" ? navigator.userAgent : "";
      await feedback.submit(category, body, pathname || "", browser);
      setState("sent");
      setBody("");
    } catch (err) {
      setState("error");
      setError(err instanceof Error ? err.message : "Could not send. Try again.");
    }
  }

  function close() {
    setOpen(false);
    setTimeout(() => setState("idle"), 200);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Send feedback"
        className="fixed bottom-5 right-5 z-40 rounded-full bg-terraza-accent px-4 py-3 text-sm tracking-cozy text-terraza-accentInk shadow-lg transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink motion-reduce:transition-none motion-reduce:hover:translate-y-0"
      >
        feedback
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Send feedback"
          className="fixed inset-0 z-50 flex items-end justify-end p-4 sm:items-center sm:justify-center"
        >
          <div
            className="absolute inset-0 bg-black/20"
            onClick={close}
            aria-hidden="true"
          />
          <div className="relative w-full max-w-md rounded-card border border-terraza-dash bg-terraza-card p-5 shadow-xl">
            {state === "sent" ? (
              <div className="py-6 text-center">
                <p className="text-lg lowercase tracking-cozy">thank you ✦</p>
                <p className="mt-2 text-sm text-terraza-soft">
                  we read every note. this helps make polyglot better.
                </p>
                <button
                  onClick={close}
                  className="mt-5 rounded-full bg-terraza-pill px-6 py-2 tracking-cozy"
                >
                  close
                </button>
              </div>
            ) : (
              <form onSubmit={send} className="flex flex-col gap-4" noValidate>
                <div className="flex items-baseline">
                  <h2 className="mr-auto text-lg lowercase tracking-cozy">send feedback</h2>
                  <button type="button" onClick={close}
                    className="text-sm text-terraza-soft" aria-label="Close">✕</button>
                </div>

                <div>
                  <label className="text-xs tracking-label text-terraza-soft">THIS IS…</label>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {CATEGORIES.map((c) => (
                      <button
                        key={c.value} type="button"
                        onClick={() => setCategory(c.value)}
                        aria-pressed={category === c.value}
                        className={`rounded-full px-3 py-1.5 text-sm tracking-cozy ${
                          category === c.value
                            ? "bg-terraza-accent text-terraza-accentInk"
                            : "bg-terraza-pill"
                        }`}
                      >
                        {c.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="fb-body" className="text-xs tracking-label text-terraza-soft">
                    DETAILS
                  </label>
                  <textarea
                    id="fb-body" value={body} onChange={(e) => setBody(e.target.value)}
                    rows={4} maxLength={5000} required
                    placeholder="what happened, or what would you like to see?"
                    className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-terraza-ink"
                  />
                  <p className="mt-1 text-xs text-terraza-soft">
                    we&apos;ll include the page you&apos;re on ({pathname}) to help us look into it.
                  </p>
                </div>

                {error && <p role="alert" className="text-sm text-terraza-danger">{error}</p>}

                <button
                  type="submit"
                  disabled={state === "sending" || !body.trim()}
                  className="rounded-full bg-terraza-accent px-5 py-2.5 tracking-cozy text-terraza-accentInk disabled:opacity-50"
                >
                  {state === "sending" ? "un momento…" : "send"}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}

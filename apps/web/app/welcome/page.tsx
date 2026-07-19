"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Protected } from "@/components/protected";
import { Button } from "@/components/ui";

// Onboarding slides (PLANNING §Phase 4, pulled forward). Five slides introduce
// the method. The two "gag" slides are gentle interactive jokes with accessible
// alternatives (a plain Continue button always advances).

const SLIDES = [
  {
    key: "welcome",
    title: "bienvenido a polyglot",
    body: "a cozy path to real spanish — from your first \"hola\" to holding a conversation.",
    art: "map",
  },
  {
    key: "srs",
    title: "learn it, then keep it",
    body: "each word comes back right before you'd forget it. that's how it moves from \"just learned\" to \"never forget.\"",
    art: "trail",
  },
  {
    key: "skills",
    title: "more than flashcards",
    body: "vocabulary, grammar, listening, writing, and speaking — woven into one journey, not five apps.",
    art: "skills",
  },
  {
    key: "notebook",
    title: "no notebook required",
    body: "tempted to write everything down? you don't need to. we track it all for you. (go on, try to take notes.)",
    art: "notebook",
    gag: true,
  },
  {
    key: "ready",
    title: "you're ready",
    body: "start with your first lesson. a few minutes a day is all it takes.",
    art: "ready",
  },
];

export default function WelcomePage() {
  return (
    <Protected>
      <Onboarding />
    </Protected>
  );
}

function Onboarding() {
  const router = useRouter();
  const [i, setI] = useState(0);
  const slide = SLIDES[i];
  const last = i === SLIDES.length - 1;

  function finish() {
    // Remember they've seen it so we don't show it again.
    try { window.localStorage.setItem("polyglot.onboarded", "1"); } catch { /* ignore */ }
    router.push("/dashboard");
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-8 p-6">
      {/* progress dots */}
      <div className="flex justify-center gap-2">
        {SLIDES.map((s, idx) => (
          <div key={s.key}
            className={`h-2 rounded-full transition-all ${
              idx === i ? "w-8 bg-terraza-accent" : "w-2 bg-terraza-pill"
            }`} />
        ))}
      </div>

      <SlideArt art={slide.art} />

      <div className="text-center">
        <h1 className="text-3xl lowercase tracking-cozy">{slide.title}</h1>
        <p className="mx-auto mt-4 max-w-md text-terraza-soft">{slide.body}</p>
        {slide.gag && <NotebookGag />}
      </div>

      <div className="flex items-center justify-between">
        <button
          onClick={() => (i === 0 ? finish() : setI(i - 1))}
          className="rounded-full px-5 py-2 text-sm text-terraza-soft hover:bg-terraza-pill"
        >
          {i === 0 ? "skip" : "← back"}
        </button>
        <Button onClick={() => (last ? finish() : setI(i + 1))}>
          {last ? "empezar →" : "next →"}
        </Button>
      </div>
    </main>
  );
}

function NotebookGag() {
  const [notes, setNotes] = useState("");
  // As you type "notes", they gently fade — the gag. Fully skippable; the
  // Continue button never depends on this.
  return (
    <div className="mt-5">
      <input
        value={notes}
        onChange={(e) => setNotes(e.target.value.slice(0, 40))}
        placeholder="try taking a note…"
        className="w-full rounded-[14px] border border-terraza-dash bg-terraza-bg px-4 py-3 text-center tracking-cozy transition-opacity"
        style={{ opacity: Math.max(0.15, 1 - notes.length / 30) }}
        aria-label="A playful notes field that fades as you type"
      />
      {notes.length > 12 && (
        <p className="mt-2 text-sm font-empty italic text-terraza-soft">
          see? it&apos;s already slipping away. let us remember for you ~
        </p>
      )}
    </div>
  );
}

function SlideArt({ art }: { art: string }) {
  // Simple inline SVG art per slide, Terraza palette. Decorative.
  const common = "mx-auto";
  if (art === "map") {
    return (
      <svg className={common} width="200" height="140" viewBox="0 0 200 140" aria-hidden="true">
        <rect width="200" height="140" rx="16" fill="var(--lg-green)" opacity="0.4" />
        <path d="M70 20 Q60 50 80 70 Q70 100 90 125 L110 120 Q95 95 105 70 Q120 45 100 22 Z"
              fill="var(--lg-accent)" opacity="0.7" />
        <circle cx="95" cy="55" r="5" fill="var(--lg-pink)" />
        <circle cx="88" cy="90" r="5" fill="var(--lg-gold)" />
      </svg>
    );
  }
  if (art === "trail") {
    return (
      <svg className={common} width="220" height="120" viewBox="0 0 220 120" aria-hidden="true">
        <path d="M10 100 Q60 20 110 60 T210 30" fill="none" stroke="var(--lg-dash)"
              strokeWidth="3" strokeDasharray="6 6" />
        {[[10,100],[70,52],[130,58],[210,30]].map(([x,y],idx) => (
          <circle key={idx} cx={x} cy={y} r="9"
                  fill={idx === 3 ? "var(--lg-accent)" : "var(--lg-pink)"} />
        ))}
      </svg>
    );
  }
  if (art === "skills") {
    return (
      <svg className={common} width="200" height="120" viewBox="0 0 200 120" aria-hidden="true">
        {["var(--lg-pink)","var(--lg-gold)","var(--lg-accent)","var(--lg-green)"].map((c,idx) => (
          <rect key={idx} x={20 + idx*45} y={40 - (idx%2)*15} width="34" height="60"
                rx="8" fill={c} opacity="0.8" />
        ))}
      </svg>
    );
  }
  if (art === "notebook") {
    return (
      <svg className={common} width="160" height="120" viewBox="0 0 160 120" aria-hidden="true">
        <rect x="40" y="20" width="80" height="90" rx="6" fill="#fff" stroke="var(--lg-dash)" strokeWidth="2" />
        {[40,55,70,85].map((y) => (
          <line key={y} x1="52" y1={y} x2="108" y2={y} stroke="var(--lg-dash)" strokeWidth="2" />
        ))}
      </svg>
    );
  }
  return (
    <svg className={common} width="140" height="120" viewBox="0 0 140 120" aria-hidden="true">
      <circle cx="70" cy="60" r="45" fill="var(--lg-accent)" opacity="0.8" />
      <text x="70" y="75" textAnchor="middle" fontSize="40" fill="var(--lg-accentInk)">✦</text>
    </svg>
  );
}

"use client";

import Link from "next/link";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";

// FAQ + About (spec §21). Static content for now — the questions people actually
// ask in beta will refine it. Kept plain-text so there's nothing to sanitize.

const FAQS: { q: string; a: string }[] = [
  {
    q: "what is polyglot?",
    a: "a spaced-repetition path to latin american (mexican) spanish. you learn vocabulary and grammar in small batches, then the app brings each item back right before you'd forget it — so it moves from \"just learned\" to \"never forget\".",
  },
  {
    q: "is it free?",
    a: "level 1 is free for everyone, forever. during the beta, everything is free. later, a subscription ($7/month or $60/year) unlocks every level, all practice types, and the full curriculum.",
  },
  {
    q: "how do reviews work?",
    a: "each item has one srs stage that climbs as you get it right and slips when you don't. you answer both directions — spanish→english and english→spanish — and an item only levels up when you get both right.",
  },
  {
    q: "what if i get something wrong on a technicality?",
    a: "there's an \"i was right\" undo during reviews. it accepts your answer without penalty — no lost xp or srs progress — for typos, near-synonyms, or a technically-correct alternative.",
  },
  {
    q: "what languages are supported?",
    a: "spanish today, with tagalog on the roadmap. the app was built multilingual from day one, so adding a language is a curriculum import, not a rebuild.",
  },
  {
    q: "how is my data handled?",
    a: "your journal entries are private. voice recordings, when speaking practice ships, are processed for comparison and never stored. we don't run ads or sell data.",
  },
];

export default function FaqPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-2xl px-4 py-10">
        <h1 className="text-3xl lowercase tracking-cozy">about & faq</h1>
        <p className="mt-3 text-terraza-soft">
          the short version of how polyglot works and why it exists.
        </p>

        <div className="mt-8 flex flex-col gap-3">
          {FAQS.map((item) => (
            <Card key={item.q}>
              <h2 className="lowercase tracking-cozy">{item.q}</h2>
              <p className="mt-2 text-sm leading-relaxed text-terraza-soft">{item.a}</p>
            </Card>
          ))}
        </div>

        <p className="mt-8 text-sm text-terraza-soft">
          didn&apos;t find your answer? head to{" "}
          <Link href="/support" className="underline underline-offset-2">support</Link>{" "}
          and ask.
        </p>
      </main>
      <Footer />
    </Protected>
  );
}

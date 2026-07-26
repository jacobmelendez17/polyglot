"use client";

// A small, reusable paywall notice. Shown in place of gated content — a locked
// level, a paid practice type — rather than as a blocking modal, so the learner
// always sees why something is locked and where to unlock it. Never the only
// thing on screen: level 1 stays fully usable behind it.

import Link from "next/link";
import { Card } from "@/components/ui";

export function PaywallNotice({
  title = "this is a subscriber feature",
  reason = "level 1 is free. a subscription unlocks every level, all practice types, and the full curriculum.",
}: { title?: string; reason?: string }) {
  return (
    <Card className="border-terraza-accent">
      <div className="flex flex-col items-center gap-3 py-4 text-center">
        <span className="text-2xl text-terraza-accent" aria-hidden="true">✦</span>
        <p className="lowercase tracking-cozy">{title}</p>
        <p className="max-w-sm text-sm text-terraza-soft">{reason}</p>
        <Link
          href="/pricing"
          className="mt-1 rounded-full bg-terraza-accent px-6 py-2 tracking-cozy text-terraza-accentInk"
        >
          see plans →
        </Link>
        <p className="text-xs text-terraza-soft">everything is free during beta.</p>
      </div>
    </Card>
  );
}

"use client";

// Shown when a 402 paywall response comes back (a gated level/feature). It explains
// the free boundary and links to pricing — never a dead end. Reusable anywhere a
// gated action might return { error: { code: "paywall" } }.
import Link from "next/link";
import { Button, Card } from "@/components/ui";

export function PaywallNotice({ freeMaxLevel = 1 }: { freeMaxLevel?: number }) {
  return (
    <Card className="text-center">
      <p className="text-lg lowercase tracking-cozy">this is a paid level 🔒</p>
      <p className="mt-2 text-terraza-soft">
        the first {freeMaxLevel === 1 ? "level is" : `${freeMaxLevel} levels are`} free. unlock the
        rest of the journey with a plan — level 1 stays free forever.
      </p>
      <Link href="/pricing">
        <Button className="mt-4">see plans</Button>
      </Link>
    </Card>
  );
}

// Helper: does an API error object represent the paywall?
export function isPaywall(err: unknown): boolean {
  return (err as { code?: string })?.code === "paywall"
    || (err as { error?: { code?: string } })?.error?.code === "paywall";
}

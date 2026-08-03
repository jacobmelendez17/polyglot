"use client";

// Testing hub (spec §7): choose one of the three maps. Each links to its runner.

import Link from "next/link";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { TEST_MAPS } from "@/lib/testing-api";

export default function TestsHubPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-2xl lowercase tracking-cozy">testing</h1>
        <p className="mt-1 mb-6 text-terraza-soft">
          listen, read, and choose the right answer. three maps, three flavors of challenge.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {TEST_MAPS.map((m) => (
            <Link key={m.id} href={`/tests/${m.id}`}>
              <Card className="h-full transition-transform hover:-translate-y-1">
                <p className="text-lg lowercase tracking-cozy">{m.title}</p>
                <p className="mt-2 text-sm text-terraza-soft">{m.blurb}</p>
                <p className="mt-4 text-xs tracking-label text-terraza-accent">START →</p>
              </Card>
            </Link>
          ))}
        </div>
      </main>
    </Protected>
  );
}

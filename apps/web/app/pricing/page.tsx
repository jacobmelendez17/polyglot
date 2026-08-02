"use client";

// Pricing (spec §19). Level 1 is free for everyone; the paid plans unlock the rest.
// Beta users are free today, so a subscriber sees "you're all set" rather than a
// buy button. Loading / error states throughout.

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { billing, priceText, type Entitlements, type Plan } from "@/lib/billing-api";

export default function PricingPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-3xl px-4 py-10">
        <Pricing />
      </main>
    </Protected>
  );
}

function Pricing() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [ent, setEnt] = useState<Entitlements | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([billing.plans(), billing.entitlements()])
      .then(([p, e]) => { setPlans(p); setEnt(e); })
      .catch(() => setError(true));
  }, []);

  async function subscribe(plan: string) {
    setBusy(plan);
    try {
      const { url } = await billing.checkout(plan);
      window.location.href = url; // hosted checkout (or the local fake page)
    } catch {
      setError(true);
      setBusy(null);
    }
  }

  return (
    <>
      <div className="text-center">
        <h1 className="text-3xl lowercase tracking-cozy">pricing</h1>
        <p className="mt-2 text-terraza-soft">
          level 1 is free for everyone. the rest of the journey unlocks with a plan.
        </p>
      </div>

      {error ? (
        <p role="alert" className="mt-6 text-center text-terraza-danger">couldn&apos;t load pricing — try again.</p>
      ) : plans === null || ent === null ? (
        <p className="mt-6 text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : ent.entitled ? (
        <Card className="mt-8 text-center">
          <p className="text-lg lowercase tracking-cozy">you&apos;re all set ✦</p>
          <p className="mt-1 text-terraza-soft">
            {ent.tier === "free_beta"
              ? "as a beta member you have full access — thank you for helping build this."
              : ent.tier === "lifetime"
                ? "you have lifetime access."
                : `your ${ent.tier} plan is ${ent.status}.`}
          </p>
        </Card>
      ) : (
        <>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Card className="text-center">
              <p className="text-xs tracking-label text-terraza-soft">FREE</p>
              <p className="mt-2 text-3xl tracking-cozy">$0</p>
              <p className="mt-2 text-sm text-terraza-soft">level 1 + basic practice</p>
            </Card>
            {plans.map((p) => (
              <Card key={p.plan} className="text-center">
                <p className="text-xs tracking-label text-terraza-accent">{p.plan.toUpperCase()}</p>
                <p className="mt-2 text-3xl tracking-cozy">{priceText(p.amount, p.currency)}</p>
                <p className="mt-1 text-sm text-terraza-soft">per {p.interval} · full access</p>
                <Button className="mt-4 w-full" onClick={() => subscribe(p.plan)} disabled={busy !== null}>
                  {busy === p.plan ? "…" : "subscribe"}
                </Button>
              </Card>
            ))}
          </div>
          <p className="mt-4 text-center text-xs text-terraza-soft">
            cancel anytime · secure checkout
          </p>
        </>
      )}
    </>
  );
}

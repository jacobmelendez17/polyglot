"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { subscription, type Entitlement } from "@/lib/billing-api";

// The pricing page (spec §19). Free for beta, then $7/mo or $60/yr. Level 1 is
// always free; a subscription unlocks the rest. What a viewer sees depends on
// where they already stand — an active subscriber gets a "manage billing"
// button, not another buy button.

const PLANS = [
  {
    interval: "month" as const,
    price: "$7",
    cadence: "/ month",
    blurb: "everything, billed monthly. cancel anytime.",
  },
  {
    interval: "year" as const,
    price: "$60",
    cadence: "/ year",
    blurb: "two months free versus monthly. best value.",
    featured: true,
  },
];

export default function PricingPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-4xl px-4 py-10">
        <Pricing />
      </main>
      <Footer />
    </Protected>
  );
}

function Pricing() {
  const [ent, setEnt] = useState<Entitlement | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    subscription.get().then(setEnt).catch((e) => setError(e.message));
  }, []);

  async function subscribe(interval: "month" | "year") {
    setBusy(interval);
    setError(null);
    try {
      const { url } = await subscription.checkout(interval);
      window.location.href = url;   // to Stripe (or the local dev checkout)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start checkout.");
      setBusy(null);
    }
  }

  async function manage() {
    setBusy("portal");
    try {
      const { url } = await subscription.portal();
      window.location.href = url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open billing.");
      setBusy(null);
    }
  }

  return (
    <>
      <div className="text-center">
        <h1 className="text-3xl lowercase tracking-cozy">pricing</h1>
        <p className="mt-3 text-terraza-soft">
          level 1 is free for everyone. a subscription opens every level, all
          practice types, and the full curriculum.
        </p>
      </div>

      {ent?.full_access && (
        <Card className="mx-auto mt-8 max-w-md">
          <p className="text-center tracking-cozy">
            you have full access ✦
          </p>
          <p className="mt-2 text-center text-sm text-terraza-soft">
            {ent.status === "lifetime"
              ? "lifetime access — thank you for helping build this."
              : ent.status === "beta"
              ? "beta access — thank you for testing."
              : ent.cancel_at_period_end
              ? "your subscription is set to cancel at the end of the period."
              : "your subscription is active."}
          </p>
          {ent.status.startsWith("paid") && (
            <button
              onClick={manage}
              disabled={busy === "portal"}
              className="mt-4 block w-full rounded-full bg-terraza-pill px-5 py-2 text-center tracking-cozy disabled:opacity-50"
            >
              {busy === "portal" ? "un momento…" : "manage billing"}
            </button>
          )}
        </Card>
      )}

      {error && (
        <p role="alert" className="mt-6 text-center text-terraza-danger">{error}</p>
      )}

      {!ent?.full_access && (
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
          {PLANS.map((plan) => (
            <Card
              key={plan.interval}
              className={plan.featured ? "border-terraza-accent" : ""}
            >
              {plan.featured && (
                <p className="mb-2 text-xs tracking-label text-terraza-accent">
                  BEST VALUE
                </p>
              )}
              <p className="text-3xl lowercase tracking-cozy">
                {plan.price}
                <span className="ml-1 text-base text-terraza-soft">{plan.cadence}</span>
              </p>
              <p className="mt-2 text-sm text-terraza-soft">{plan.blurb}</p>
              <button
                onClick={() => subscribe(plan.interval)}
                disabled={busy !== null}
                className="mt-5 block w-full rounded-full bg-terraza-accent px-5 py-2.5 text-center tracking-cozy text-terraza-accentInk disabled:opacity-50"
              >
                {busy === plan.interval ? "un momento…" : "subscribe"}
              </button>
            </Card>
          ))}
        </div>
      )}

      <p className="mt-8 text-center text-sm text-terraza-soft">
        during beta everything is free.{" "}
        <Link href="/dashboard" className="underline underline-offset-2">
          back to dashboard
        </Link>
      </p>
    </>
  );
}

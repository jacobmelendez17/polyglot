"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Card, TextLink } from "@/components/ui";
import { account } from "@/lib/account-api";

// Lands here from the email link. Confirms the token on mount and reports the
// outcome — verified, already verified, or an invalid/expired link.

type State = "checking" | "verified" | "already" | "error" | "no-token";

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<Shell><Checking /></Shell>}>
      <Verify />
    </Suspense>
  );
}

function Verify() {
  const token = useSearchParams().get("token");
  const [state, setState] = useState<State>(token ? "checking" : "no-token");

  useEffect(() => {
    if (!token) return;
    let live = true;
    account.verifyEmail(token)
      .then((r) => { if (live) setState(r.already_verified ? "already" : "verified"); })
      .catch(() => { if (live) setState("error"); });
    return () => { live = false; };
  }, [token]);

  return (
    <Shell>
      {state === "checking" && <Checking />}
      {state === "verified" && (
        <Message
          title="email confirmed ✦"
          body="thanks — your email is verified. you're all set."
        />
      )}
      {state === "already" && (
        <Message
          title="already confirmed"
          body="this email was already verified. nothing more to do."
        />
      )}
      {state === "no-token" && (
        <Message
          title="nothing to confirm"
          body="this page confirms an email from the link we sent you. check your inbox for it."
        />
      )}
      {state === "error" && (
        <Message
          title="that link didn't work"
          body="it may have expired or already been used. you can request a fresh one from settings."
        />
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
      <div className="text-center">
        <span className="text-2xl lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">confirm email</h1>
      </div>
      {children}
      <p className="text-center text-sm text-terraza-soft">
        <TextLink href="/dashboard">→ go to dashboard</TextLink>
      </p>
    </main>
  );
}

function Checking() {
  return (
    <Card>
      <p className="text-center font-empty italic text-terraza-soft">
        confirming your email ~
      </p>
    </Card>
  );
}

function Message({ title, body }: { title: string; body: string }) {
  return (
    <Card>
      <p className="text-center tracking-cozy">{title}</p>
      <p className="mt-3 text-center text-sm text-terraza-soft">{body}</p>
      <Link
        href="/dashboard"
        className="mt-5 block rounded-full bg-terraza-accent px-5 py-2 text-center tracking-cozy text-terraza-accentInk"
      >
        continue
      </Link>
    </Card>
  );
}

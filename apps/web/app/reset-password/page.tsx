"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, Card, FormError, Input, Label, TextLink } from "@/components/ui";
import { account } from "@/lib/account-api";

// One page, two modes. With no ?token it's the "email me a link" form; with a
// token from the email it's the "set a new password" form. The request form
// always reports success — the API doesn't reveal whether the address exists,
// and neither does this page.

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<Shell><p className="text-center font-empty italic text-terraza-soft">un momento ~</p></Shell>}>
      <ResetFlow />
    </Suspense>
  );
}

function ResetFlow() {
  const token = useSearchParams().get("token");
  return token ? <SetNewPassword token={token} /> : <RequestLink />;
}

function Shell({ children, title = "reset password" }: { children: React.ReactNode; title?: string }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
      <div className="text-center">
        <span className="text-2xl lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">{title}</h1>
      </div>
      {children}
      <p className="text-center text-sm text-terraza-soft">
        <TextLink href="/login">← back to sign in</TextLink>
      </p>
    </main>
  );
}

function RequestLink() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await account.forgotPassword(email);
    } catch {
      // Deliberately ignored: a failure here would leak that the address is or
      // isn't registered. Always show the same confirmation.
    } finally {
      setSent(true);
      setSubmitting(false);
    }
  }

  if (sent) {
    return (
      <Shell>
        <Card>
          <p className="text-center tracking-cozy">check your inbox ✦</p>
          <p className="mt-3 text-center text-sm text-terraza-soft">
            if an account exists for that address, a reset link is on its way.
            it&apos;s good for one hour.
          </p>
        </Card>
      </Shell>
    );
  }

  return (
    <Shell>
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <p className="text-sm text-terraza-soft">
            enter your email and we&apos;ll send you a link to set a new password.
          </p>
          <div>
            <Label htmlFor="email">email</Label>
            <Input
              id="email" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <Button type="submit" disabled={submitting || !email}>
            {submitting ? "un momento…" : "send reset link"}
          </Button>
        </form>
      </Card>
    </Shell>
  );
}

function SetNewPassword({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Those passwords don't match.");
      return;
    }
    setSubmitting(true);
    try {
      await account.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "That link is invalid or expired.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Shell title="all set">
        <Card>
          <p className="text-center tracking-cozy">password updated ✦</p>
          <p className="mt-3 text-center text-sm text-terraza-soft">
            you can sign in with your new password now.
          </p>
          <Link
            href="/login"
            className="mt-5 block rounded-full bg-terraza-accent px-5 py-2 text-center tracking-cozy text-terraza-accentInk"
          >
            sign in
          </Link>
        </Card>
      </Shell>
    );
  }

  return (
    <Shell title="set a new password">
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <div>
            <Label htmlFor="password">new password</Label>
            <Input
              id="password" type="password" autoComplete="new-password" required
              value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="at least 8 characters"
            />
          </div>
          <div>
            <Label htmlFor="confirm">confirm password</Label>
            <Input
              id="confirm" type="password" autoComplete="new-password" required
              value={confirm} onChange={(e) => setConfirm(e.target.value)}
              placeholder="type it again"
            />
          </div>
          <FormError message={error} />
          <Button type="submit" disabled={submitting}>
            {submitting ? "un momento…" : "set password"}
          </Button>
        </form>
      </Card>
    </Shell>
  );
}

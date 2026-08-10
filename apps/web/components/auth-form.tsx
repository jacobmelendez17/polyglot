"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button, Card, FormError, Input, Label, TextLink } from "./ui";
import { checkPassword } from "@/lib/password";
import { PasswordChecklist } from "./password-checklist";
import { OAuthButtons } from "./oauth-buttons";

type Mode = "login" | "signup";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const { login, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (isSignup) {
      if (name.trim().length === 0) {
        setError("Please enter your name.");
        return;
      }
      if (!Object.values(checkPassword(password)).every(Boolean)) {
        setError("Your password doesn't meet all the requirements below yet.");
        return;
      }
      if (password !== confirm) {
        setError("Passwords don't match.");
        return;
      }
    }

    setSubmitting(true);
    try {
      if (isSignup) {
        await signup(email, name.trim(), password);
        router.push("/welcome");   // onboarding slides, then language + curriculum pacing
      } else {
        const me = await login(email, password);
        // New/reset accounts see onboarding on sign-in; everyone else goes home.
        router.push(me && me.onboarding_completed === false ? "/welcome" : "/dashboard");
      }
    } catch (err) {
      if (err instanceof ApiClientError) setError(err.message);
      else setError("Something went wrong. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
      <div className="text-center">
        <span className="text-2xl lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <p className="mt-1 text-sm text-terraza-soft">
          {isSignup ? "create your account to begin" : "sign in to keep learning"}
        </p>
      </div>

      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          {isSignup && (
            <div>
              <Label htmlFor="name">name</Label>
              <Input
                id="name" type="text" autoComplete="name" required
                value={name} onChange={(e) => setName(e.target.value)}
                placeholder="what should we call you?"
              />
            </div>
          )}
          <div>
            <Label htmlFor="email">email</Label>
            <Input
              id="email" type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
            />
          </div>
          <div>
            <Label htmlFor="password">password</Label>
            <Input
              id="password" type="password" required
              autoComplete={isSignup ? "new-password" : "current-password"}
              value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder={isSignup ? "at least 8 characters" : "your password"}
            />
          </div>
          {isSignup && <PasswordChecklist password={password} />}
          {isSignup && (
            <div>
              <Label htmlFor="confirm">confirm password</Label>
              <Input
                id="confirm" type="password" autoComplete="new-password" required
                value={confirm} onChange={(e) => setConfirm(e.target.value)}
                placeholder="type it again"
              />
            </div>
          )}

          <FormError message={error} />

          <Button type="submit" disabled={submitting}>
            {submitting ? "un momento…" : isSignup ? "create account" : "sign in"}
          </Button>
        </form>
        <OAuthButtons />
      </Card>

      <div className="flex flex-col items-center gap-2 text-center text-sm text-terraza-soft">
        <p>
          {isSignup ? (
            <>already have an account? <TextLink href="/login">sign in</TextLink></>
          ) : (
            <>new here? <TextLink href="/signup">create an account</TextLink></>
          )}
        </p>
        {!isSignup && (
          <p>
            <TextLink href="/reset-password">forgot your password?</TextLink>
          </p>
        )}
        <p>
          <TextLink href="/">← back to landing page</TextLink>
        </p>
      </div>
    </main>
  );
}

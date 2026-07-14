"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiClientError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Button, Card, FormError, Input, Label, TextLink } from "./ui";

type Mode = "login" | "signup";

export function AuthForm({ mode }: { mode: Mode }) {
  const router = useRouter();
  const { login, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isSignup = mode === "signup";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (isSignup && password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (isSignup) await signup(email, password);
      else await login(email, password);
      router.push("/dashboard");
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
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">
          {isSignup ? "empieza tu viaje" : "bienvenido de nuevo"}
        </h1>
        <p className="mt-1 text-sm text-terraza-soft">
          {isSignup ? "create your account to begin" : "sign in to keep learning"}
        </p>
      </div>

      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
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

          <FormError message={error} />

          <Button type="submit" disabled={submitting}>
            {submitting ? "un momento…" : isSignup ? "create account" : "sign in"}
          </Button>
        </form>
      </Card>

      <p className="text-center text-sm text-terraza-soft">
        {isSignup ? (
          <>already have an account? <TextLink href="/login">sign in</TextLink></>
        ) : (
          <>new here? <TextLink href="/signup">create an account</TextLink></>
        )}
      </p>
    </main>
  );
}

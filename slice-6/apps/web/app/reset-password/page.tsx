"use client";

import { Card, TextLink } from "@/components/ui";

/**
 * Placeholder. The real flow (email token -> set new password) lands with the
 * email service; this page exists so the login link goes somewhere honest
 * rather than 404ing.
 */
export default function ResetPasswordPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-6">
      <div className="text-center">
        <span className="text-2xl lowercase tracking-cozy">
          polyglot <span className="text-terraza-accent">✦</span>
        </span>
        <h1 className="mt-4 text-2xl lowercase tracking-cozy">reset password</h1>
      </div>
      <Card>
        <p className="text-center font-empty italic text-terraza-soft">
          not ready yet ~
        </p>
        <p className="mt-3 text-center text-sm text-terraza-soft">
          password resets arrive with email support in a coming update. for now, if you&apos;re
          locked out, reach out and we&apos;ll sort it.
        </p>
      </Card>
      <p className="text-center text-sm text-terraza-soft">
        <TextLink href="/login">← back to sign in</TextLink>
      </p>
    </main>
  );
}

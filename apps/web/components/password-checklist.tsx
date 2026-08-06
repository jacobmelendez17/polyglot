"use client";

// Live password requirements (§25). Shows each rule with a ✓ (met) or · (not yet) —
// never colour alone. Purely presentational; the server re-validates on submit.
import { checkPassword, PASSWORD_RULES } from "@/lib/password";

export function PasswordChecklist({ password }: { password: string }) {
  const state = checkPassword(password);
  return (
    <ul className="mt-2 flex flex-col gap-1" aria-label="password requirements">
      {PASSWORD_RULES.map((r) => {
        const ok = state[r.key];
        return (
          <li key={r.key} className={`flex items-center gap-2 text-xs ${ok ? "text-terraza-green" : "text-terraza-soft"}`}>
            <span aria-hidden className="w-3">{ok ? "✓" : "·"}</span>
            <span>{r.label}</span>
            <span className="sr-only">{ok ? "met" : "not met"}</span>
          </li>
        );
      })}
    </ul>
  );
}

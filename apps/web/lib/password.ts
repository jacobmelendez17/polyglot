// Password policy (mirrors app/domain/password.py). Used for the live requirements
// checklist and to block submit before the request. The server re-validates — this
// is UX, not the security boundary.

export const MIN_LENGTH = 8;
const SPECIAL = new Set("!@#$%^&*()-_=+[]{};:'\",.<>/?\\|`~".split(""));

export interface PasswordRule {
  key: string;
  label: string;
  test: (p: string) => boolean;
}

export const PASSWORD_RULES: PasswordRule[] = [
  { key: "length", label: `at least ${MIN_LENGTH} characters`, test: (p) => p.length >= MIN_LENGTH },
  { key: "uppercase", label: "an uppercase letter", test: (p) => /[A-Z]/.test(p) },
  { key: "lowercase", label: "a lowercase letter", test: (p) => /[a-z]/.test(p) },
  { key: "digit", label: "a number", test: (p) => /[0-9]/.test(p) },
  { key: "special", label: "a special character", test: (p) => p.split("").some((c) => SPECIAL.has(c)) },
];

export function checkPassword(password: string): Record<string, boolean> {
  return Object.fromEntries(PASSWORD_RULES.map((r) => [r.key, r.test(password)]));
}

export function passwordIsValid(password: string): boolean {
  return PASSWORD_RULES.every((r) => r.test(password));
}

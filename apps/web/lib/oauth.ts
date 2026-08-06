// Social sign-in helpers. Buttons always render (so the option is visible), but a
// provider only navigates once the backend reports it configured; otherwise the form
// shows a friendly "coming soon" note. No provider is faked.
import { request } from "./http";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export interface OAuthProvider {
  key: "google" | "discord" | "github";
  label: string;
}

export const OAUTH_PROVIDERS: OAuthProvider[] = [
  { key: "google", label: "Google" },
  { key: "discord", label: "Discord" },
  { key: "github", label: "GitHub" },
];

export async function fetchOAuthProviders(): Promise<Record<string, boolean>> {
  try {
    const r = await request<{ providers: Record<string, boolean> }>("/api/v1/auth/oauth/providers");
    return r.providers ?? {};
  } catch {
    return {}; // treat as none configured
  }
}

export function oauthStartUrl(provider: string): string {
  return `${API_BASE}/api/v1/auth/oauth/${provider}/start`;
}

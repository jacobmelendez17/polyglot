"use client";

// Social sign-in buttons (§20). The three options always render, so the choice is
// visible; a provider only navigates once the backend reports it configured — until
// then a click shows an honest "coming soon" note. No login is faked.
import { useEffect, useState } from "react";
import { fetchOAuthProviders, oauthStartUrl, OAUTH_PROVIDERS } from "@/lib/oauth";

function Icon({ provider }: { provider: string }) {
  const common = { width: 18, height: 18, "aria-hidden": true } as const;
  if (provider === "google")
    return (
      <svg {...common} viewBox="0 0 24 24"><path fill="#4285F4" d="M23 12.3c0-.8-.1-1.6-.2-2.3H12v4.5h6.2a5.3 5.3 0 0 1-2.3 3.5v2.9h3.7c2.2-2 3.4-5 3.4-8.6z"/><path fill="#34A853" d="M12 24c3.1 0 5.7-1 7.6-2.8l-3.7-2.9c-1 .7-2.3 1.1-3.9 1.1-3 0-5.5-2-6.4-4.7H1.8v3A12 12 0 0 0 12 24z"/><path fill="#FBBC05" d="M5.6 14.7a7.2 7.2 0 0 1 0-4.6v-3H1.8a12 12 0 0 0 0 10.6l3.8-3z"/><path fill="#EA4335" d="M12 4.8c1.7 0 3.2.6 4.4 1.7l3.3-3.3A12 12 0 0 0 1.8 6.5l3.8 3C6.5 6.8 9 4.8 12 4.8z"/></svg>
    );
  if (provider === "discord")
    return (
      <svg {...common} viewBox="0 0 24 24"><path fill="#5865F2" d="M20 4.6A19 19 0 0 0 15.3 3l-.3.5a17 17 0 0 1 4.2 1.4A16 16 0 0 0 4.8 4.9 17 17 0 0 1 9 3.5L8.7 3A19 19 0 0 0 4 4.6C1.3 8.6.6 12.5 1 16.4A19 19 0 0 0 6.7 19l.9-1.2c-.6-.2-1.2-.5-1.7-.9l.4-.3a13.6 13.6 0 0 0 11.4 0l.4.3c-.5.4-1.1.7-1.7.9L17.3 19a19 19 0 0 0 5.7-2.6c.4-4.5-.6-8.4-3-11.8zM8.5 14c-.9 0-1.7-.9-1.7-1.9s.8-1.9 1.7-1.9 1.7.9 1.7 1.9-.8 1.9-1.7 1.9zm7 0c-.9 0-1.7-.9-1.7-1.9s.8-1.9 1.7-1.9 1.7.9 1.7 1.9-.8 1.9-1.7 1.9z"/></svg>
    );
  // github
  return (
    <svg {...common} viewBox="0 0 24 24"><path fill="currentColor" d="M12 1a11 11 0 0 0-3.5 21.4c.6.1.8-.2.8-.5v-2c-3 .6-3.7-1.3-3.7-1.3-.5-1.3-1.2-1.6-1.2-1.6-1-.7 0-.7 0-.7 1.1.1 1.7 1.2 1.7 1.2 1 1.7 2.6 1.2 3.2.9.1-.7.4-1.2.7-1.5-2.4-.3-5-1.2-5-5.4 0-1.2.4-2.2 1.1-3-.1-.3-.5-1.4.1-2.9 0 0 .9-.3 3 1.1a10.4 10.4 0 0 1 5.5 0c2.1-1.4 3-1.1 3-1.1.6 1.5.2 2.6.1 2.9.7.8 1.1 1.8 1.1 3 0 4.2-2.6 5.1-5 5.4.4.3.8 1 .8 2v3c0 .3.2.6.8.5A11 11 0 0 0 12 1z"/></svg>
  );
}

export function OAuthButtons() {
  const [providers, setProviders] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => { fetchOAuthProviders().then(setProviders); }, []);

  function onClick(key: string, label: string) {
    if (providers[key]) {
      window.location.href = oauthStartUrl(key);
    } else {
      setNotice(`${label} sign-in is coming soon.`);
    }
  }

  return (
    <div className="mt-5">
      <div className="flex items-center gap-3 text-xs text-terraza-soft">
        <span className="h-px flex-1 bg-terraza-dash" />
        or continue with
        <span className="h-px flex-1 bg-terraza-dash" />
      </div>
      <div className="mt-4 flex flex-col gap-2">
        {OAUTH_PROVIDERS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => onClick(p.key, p.label)}
            className="flex items-center justify-center gap-3 rounded-full border border-terraza-dash bg-terraza-card px-4 py-2.5 text-sm tracking-cozy text-terraza-ink transition-transform hover:-translate-y-0.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-terraza-ink"
          >
            <Icon provider={p.key} />
            continue with {p.label}
          </button>
        ))}
      </div>
      {notice && (
        <p role="status" className="mt-3 text-center text-xs text-terraza-soft">{notice}</p>
      )}
    </div>
  );
}

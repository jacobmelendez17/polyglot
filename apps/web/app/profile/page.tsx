"use client";

// Profile (spec §20): edit display name, bio, and timezone; view read-only stats
// (xp, rank, streak). Draft edits save on submit, not per keystroke. Loading /
// error states throughout.

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Button, Card } from "@/components/ui";
import { account, type Profile } from "@/lib/account-api";

export default function ProfilePage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-8">
        <ProfileForm />
      </main>
    </Protected>
  );
}

function ProfileForm() {
  const [p, setP] = useState<Profile | null>(null);
  const [error, setError] = useState(false);
  const [name, setName] = useState("");
  const [bio, setBio] = useState("");
  const [tz, setTz] = useState("");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    account.getProfile().then((d) => {
      setP(d); setName(d.display_name); setBio(d.bio); setTz(d.timezone);
    }).catch(() => setError(true));
  }, []);

  async function save() {
    setBusy(true); setSaved(false);
    try {
      const d = await account.updateProfile({ display_name: name, bio, timezone: tz });
      setP(d); setSaved(true); setTimeout(() => setSaved(false), 1500);
    } catch { setError(true); } finally { setBusy(false); }
  }

  if (error)
    return <Card><p role="alert" className="text-terraza-danger">couldn&apos;t load your profile.</p></Card>;
  if (!p)
    return <p className="text-center font-empty italic text-terraza-soft">un momento ~</p>;

  const dirty = name !== p.display_name || bio !== p.bio || tz !== p.timezone;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl lowercase tracking-cozy">profile</h1>

      <Card>
        <div className="grid grid-cols-3 gap-3 text-center">
          <Stat label="xp" value={p.xp_total} />
          <Stat label="rank" value={p.rank_level} />
          <Stat label="streak" value={p.streak_current} />
        </div>
        <p className="mt-3 text-center text-xs text-terraza-soft">
          {p.email} · {p.role}{p.immersion_unlocked ? " · immersion unlocked" : ""}
        </p>
      </Card>

      <Card>
        <label className="block">
          <span className="text-sm tracking-cozy">display name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120}
            className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2" />
        </label>
        <label className="mt-3 block">
          <span className="text-sm tracking-cozy">bio</span>
          <textarea value={bio} onChange={(e) => setBio(e.target.value)} maxLength={500} rows={3}
            className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2" />
        </label>
        <label className="mt-3 block">
          <span className="text-sm tracking-cozy">timezone</span>
          <input value={tz} onChange={(e) => setTz(e.target.value)} maxLength={64}
            className="mt-1 w-full rounded-card border border-terraza-dash bg-terraza-bg px-3 py-2" />
        </label>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={save} disabled={!dirty || busy}>{busy ? "saving…" : "save"}</Button>
          {saved && <span aria-live="polite" className="text-sm text-terraza-green">saved ✓</span>}
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-2xl tracking-cozy">{value}</p>
      <p className="text-xs tracking-label text-terraza-soft">{label.toUpperCase()}</p>
    </div>
  );
}

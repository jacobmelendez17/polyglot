"use client";

// Profile (spec §20) with tabs: profile (edit name/bio/timezone + read-only
// stats), achievements, and a "+add friends" icon. Achievements and friends
// aren't built yet (§18 community is future work), so those tabs show honest
// "coming soon" states rather than fabricated data.

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { account, type Profile } from "@/lib/account-api";

type Tab = "profile" | "achievements" | "friends";

export default function ProfilePage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-xl px-4 py-8">
        <ProfileTabs />
      </main>
    </Protected>
  );
}

function ProfileTabs() {
  const [tab, setTab] = useState<Tab>("profile");

  const tabBtn = (t: Tab, label: string) => (
    <button
      role="tab"
      aria-selected={tab === t}
      onClick={() => setTab(t)}
      className={`rounded-full px-4 py-1.5 text-sm tracking-cozy transition-colors ${
        tab === t ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft hover:bg-terraza-pill"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col gap-6">
      <div role="tablist" aria-label="profile sections" className="flex items-center gap-1">
        {tabBtn("profile", "profile")}
        {tabBtn("achievements", "achievements")}
        <button
          role="tab"
          aria-selected={tab === "friends"}
          aria-label="add friends"
          title="add friends"
          onClick={() => setTab("friends")}
          className={`ml-auto flex items-center gap-1 rounded-full px-3 py-1.5 text-sm tracking-cozy transition-colors ${
            tab === "friends" ? "bg-terraza-accent text-terraza-accentInk" : "text-terraza-soft hover:bg-terraza-pill"
          }`}
        >
          <span aria-hidden="true">＋</span>
          <span className="hidden sm:inline">add friends</span>
        </button>
      </div>

      {tab === "profile" && <ProfilePanel />}
      {tab === "achievements" && <AchievementsPanel />}
      {tab === "friends" && <FriendsPanel />}
    </div>
  );
}

function ProfilePanel() {
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
  const field = "w-full rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm";

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <div className="grid grid-cols-3 gap-3 text-center">
          <Stat label="xp" value={p.xp_total} />
          <Stat label="rank" value={p.rank_level} />
          <Stat label="streak" value={p.streak_current} />
        </div>
        <p className="mt-3 text-center text-xs text-terraza-soft">
          {p.email} · {p.role}
          {p.immersion_unlocked ? " · immersion unlocked" : ""}
        </p>
      </Card>

      <Card>
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-xs tracking-label text-terraza-soft">
            display name
            <input className={field} value={name} maxLength={120}
              onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-xs tracking-label text-terraza-soft">
            bio
            <textarea className={field} rows={3} value={bio} maxLength={500}
              onChange={(e) => setBio(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-xs tracking-label text-terraza-soft">
            timezone
            <input className={field} value={tz} maxLength={64}
              onChange={(e) => setTz(e.target.value)} placeholder="e.g. America/Phoenix" />
          </label>
          <div className="flex items-center gap-3">
            <button
              onClick={save}
              disabled={!dirty || busy}
              className="rounded-full bg-terraza-accent px-5 py-2 text-sm tracking-cozy text-terraza-accentInk disabled:opacity-50"
            >
              {busy ? "saving…" : "save"}
            </button>
            {saved && <span aria-live="polite" className="text-sm text-terraza-green">saved ✓</span>}
          </div>
        </div>
      </Card>
    </div>
  );
}

function AchievementsPanel() {
  return (
    <Card>
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">ACHIEVEMENTS</h2>
      <p className="text-center font-empty italic text-terraza-soft">
        no achievements yet ~
      </p>
      <p className="mt-2 text-center text-sm text-terraza-soft">
        badges for streaks, levels, and perfect items are on the way.
      </p>
    </Card>
  );
}

function FriendsPanel() {
  return (
    <Card>
      <h2 className="mb-2 text-xs tracking-label text-terraza-soft">FRIENDS</h2>
      <div className="flex gap-2">
        <input
          disabled
          placeholder="add by username (coming soon)"
          aria-label="add a friend by username"
          className="w-full rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-2 text-sm opacity-60"
        />
        <button disabled className="rounded-full bg-terraza-accent px-4 py-2 text-sm text-terraza-accentInk opacity-50">
          add
        </button>
      </div>
      <p className="mt-3 text-center text-sm text-terraza-soft">
        friends and community features are coming soon — you&apos;ll be able to compare journals and
        progress.
      </p>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-2xl tracking-cozy text-terraza-ink">{value}</p>
      <p className="text-xs tracking-label text-terraza-soft">{label.toUpperCase()}</p>
    </div>
  );
}

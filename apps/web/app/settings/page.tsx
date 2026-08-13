"use client";

// Settings (spec §16) with a left sidebar of categories: lessons, reviews,
// appearance, curriculum, intermissions, danger zone. Each field auto-saves on
// change with an inline "saved ✓" and per-field error recovery. Every setting the
// old single-column page surfaced is preserved — the "answering" toggles now live
// under reviews, and immersion under appearance. Danger zone has a real log-out
// and an honest (not-yet-wired) delete-account placeholder.

import { useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { useAuth } from "@/lib/auth-context";
import { account, type Settings } from "@/lib/account-api";
import { COLOR_THEMES } from "@/lib/appearance";

const CATEGORIES = [
  { key: "lessons", label: "lessons" },
  { key: "reviews", label: "reviews" },
  { key: "appearance", label: "appearance" },
  { key: "curriculum", label: "curriculum" },
  { key: "intermissions", label: "intermissions" },
  { key: "danger", label: "danger zone" },
] as const;
type Category = (typeof CATEGORIES)[number]["key"];

export default function SettingsPage() {
  return (
    <Protected>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <AccountSettings />
      </main>
    </Protected>
  );
}

function AccountSettings() {
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<Record<string, string>>({});
  const [cat, setCat] = useState<Category>("lessons");

  useEffect(() => {
    account.getSettings().then(setS).catch(() => setError(true));
  }, []);

  async function save(field: keyof Settings, value: unknown) {
    if (!s) return;
    const prev = s;
    setS({ ...s, [field]: value } as Settings);        // optimistic
    setFieldError((e) => ({ ...e, [field]: "" }));
    try {
      const next = await account.updateSettings({ [field]: value });
      setS(next);
      setSaved(field as string);
      setTimeout(() => setSaved((c) => (c === field ? null : c)), 1500);
    } catch (err) {
      setS(prev);                                       // revert on failure
      const fe =
        (err as { field_errors?: Record<string, string> })?.field_errors ??
        (err as { error?: { field_errors?: Record<string, string> } })?.error?.field_errors;
      if (fe) setFieldError((e) => ({ ...e, ...fe }));
    }
  }

  if (error)
    return <Card><p role="alert" className="text-terraza-danger">couldn&apos;t load settings.</p></Card>;
  if (!s)
    return <p className="text-center font-empty italic text-terraza-soft">un momento ~</p>;

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl lowercase tracking-cozy">settings</h1>

      <div className="flex flex-col gap-6 md:flex-row">
        {/* sidebar */}
        <nav aria-label="settings sections" className="md:w-48 md:shrink-0">
          <ul className="flex gap-1 overflow-x-auto pb-1 md:flex-col md:overflow-visible md:pb-0">
            {CATEGORIES.map((c) => {
              const active = cat === c.key;
              const danger = c.key === "danger";
              return (
                <li key={c.key} className="shrink-0">
                  <button
                    aria-current={active ? "page" : undefined}
                    onClick={() => setCat(c.key)}
                    className={`w-full whitespace-nowrap rounded-full px-4 py-2 text-left text-sm tracking-cozy transition-colors ${
                      active
                        ? danger
                          ? "bg-terraza-danger/15 text-terraza-danger"
                          : "bg-terraza-pill text-terraza-ink"
                        : `${danger ? "text-terraza-danger/80" : "text-terraza-soft"} hover:bg-terraza-pill/60`
                    }`}
                  >
                    {c.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* active panel */}
        <div className="min-w-0 flex-1">
          {cat === "lessons" && (
            <Section title="lessons">
              <Num label="batch size" value={s.lesson_batch_size} min={1} max={50}
                err={fieldError.lesson_batch_size} saved={saved === "lesson_batch_size"}
                onChange={(v) => save("lesson_batch_size", v)} />
            </Section>
          )}

          {cat === "reviews" && (
            <Section title="reviews">
              <Select label="order" value={s.review_order} err={fieldError.review_order}
                options={["newest_first", "stage_order", "random"]}
                onChange={(v) => save("review_order", v)} saved={saved === "review_order"} />
              <Toggle label="review in batches" value={s.review_batch_enabled}
                onChange={(v) => save("review_batch_enabled", v)} saved={saved === "review_batch_enabled"} />
              <Num label="batch size" value={s.review_batch_size} min={1} max={100}
                err={fieldError.review_batch_size} saved={saved === "review_batch_size"}
                onChange={(v) => save("review_batch_size", v)} />
              <Toggle label="show srs level indicator" value={s.show_srs_indicator}
                onChange={(v) => save("show_srs_indicator", v)} saved={saved === "show_srs_indicator"} />
              <Num label="leech threshold" value={s.leech_threshold} min={0.1} max={5} step={0.1}
                err={fieldError.leech_threshold} saved={saved === "leech_threshold"}
                onChange={(v) => save("leech_threshold", v)} />

              <Divider>answering</Divider>
              <Toggle label="reveal full answer (no info button)" value={s.reveal_full_answer}
                onChange={(v) => save("reveal_full_answer", v)} saved={saved === "reveal_full_answer"} />
              <Toggle label="allow cheating (ignore typos, accept your synonyms)" value={s.allow_cheating}
                onChange={(v) => save("allow_cheating", v)} saved={saved === "allow_cheating"} />
              <Toggle label="accept synonyms i add to items" value={s.accept_user_synonyms}
                onChange={(v) => save("accept_user_synonyms", v)} saved={saved === "accept_user_synonyms"} />
              <Toggle label="allow skipping" value={s.allow_skipping}
                onChange={(v) => save("allow_skipping", v)} saved={saved === "allow_skipping"} />
              <Toggle label="undo / accept override enabled" value={s.undo_enabled}
                onChange={(v) => save("undo_enabled", v)} saved={saved === "undo_enabled"} />
            </Section>
          )}

          {cat === "appearance" && (
            <Section title="appearance">
              <Select label="theme" value={s.theme} err={fieldError.theme}
                options={["light", "dark", "system"]}
                onChange={(v) => save("theme", v)} saved={saved === "theme"} />
              <Select label="font size" value={s.font_size} err={fieldError.font_size}
                options={["sm", "md", "lg", "xl"]}
                onChange={(v) => save("font_size", v)} saved={saved === "font_size"} />
              <Select label="color theme" value={s.color_theme} err={fieldError.color_theme}
                options={[...COLOR_THEMES]}
                onChange={(v) => save("color_theme", v)} saved={saved === "color_theme"} />
              <Toggle label={`immersion mode${s.immersion_unlocked ? "" : " (unlocks at level 10)"}`}
                value={s.immersion_mode} disabled={!s.immersion_unlocked}
                onChange={(v) => save("immersion_mode", v)} saved={saved === "immersion_mode"} />
              {fieldError.immersion_mode && <p className="text-sm text-terraza-danger">{fieldError.immersion_mode}</p>}
            </Section>
          )}

          {cat === "curriculum" && (
            <Section title="curriculum">
              <Select label="mode" value={s.curriculum_mode} err={fieldError.curriculum_mode}
                options={["default_dispersed", "grammar_batch", "fully_dispersed"]}
                onChange={(v) => save("curriculum_mode", v)} saved={saved === "curriculum_mode"} />
              <Toggle label="group related prompts (back-to-back)" value={s.back_to_back}
                onChange={(v) => save("back_to_back", v)} saved={saved === "back_to_back"} />
              <Select label="back-to-back order" value={s.back_to_back_order} err={fieldError.back_to_back_order}
                options={["es_first", "en_first"]}
                onChange={(v) => save("back_to_back_order", v)} saved={saved === "back_to_back_order"} />
              <Select label="dialect" value={s.dialect} err={fieldError.dialect}
                options={["latam_mx", "castilian"]}
                onChange={(v) => save("dialect", v)} saved={saved === "dialect"} />
            </Section>
          )}

          {cat === "intermissions" && (
            <Section title="intermissions">
              <Toggle label="show intermissions" value={s.intermissions_enabled}
                onChange={(v) => save("intermissions_enabled", v)} saved={saved === "intermissions_enabled"} />
              <a href="/decks/intermissions" className="text-sm text-terraza-accent underline underline-offset-2">
                view finished intermissions →
              </a>
            </Section>
          )}

          {cat === "danger" && <DangerZone />}
        </div>
      </div>
    </div>
  );
}

function DangerZone() {
  const { logout } = useAuth();
  const [confirm, setConfirm] = useState(false);
  return (
    <Card>
      <h2 className="mb-3 text-xs tracking-label text-terraza-danger">DANGER ZONE</h2>
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="mr-auto">
            <p className="text-sm tracking-cozy">log out</p>
            <p className="text-xs text-terraza-soft">sign out on this device</p>
          </div>
          <button onClick={() => logout()}
            className="rounded-full border border-terraza-dash px-4 py-1.5 text-sm">
            log out
          </button>
        </div>

        <div className="border-t border-terraza-dash pt-4">
          <div className="flex items-center gap-3">
            <div className="mr-auto">
              <p className="text-sm tracking-cozy text-terraza-danger">delete account</p>
              <p className="text-xs text-terraza-soft">permanently remove your account and data</p>
            </div>
            <button onClick={() => setConfirm((c) => !c)}
              className="rounded-full border border-terraza-danger px-4 py-1.5 text-sm text-terraza-danger">
              delete…
            </button>
          </div>
          {confirm && (
            <div className="mt-3 rounded-[12px] border border-terraza-danger/40 bg-terraza-danger/10 p-3 text-sm">
              <p>
                account deletion isn&apos;t available in-app yet. to delete your account and data now,
                reach out from the{" "}
                <a href="/support" className="underline underline-offset-2">support page</a>.
              </p>
              <button onClick={() => setConfirm(false)}
                className="mt-2 rounded-full border border-terraza-dash px-3 py-1 text-xs">
                close
              </button>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

// ---- shared controls -------------------------------------------------------

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <h2 className="mb-3 text-xs tracking-label text-terraza-soft">{title.toUpperCase()}</h2>
      <div className="flex flex-col gap-3">{children}</div>
    </Card>
  );
}

function Divider({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2 border-t border-terraza-dash pt-3 text-xs tracking-label text-terraza-soft">
      {String(children).toUpperCase()}
    </div>
  );
}

function Row({ label, saved, children }: { label: string; saved?: boolean; children: React.ReactNode }) {
  return (
    <label className="flex items-center gap-3">
      <span className="flex-1 text-sm tracking-cozy">{label}</span>
      {saved && <span aria-live="polite" className="text-xs text-terraza-green">saved ✓</span>}
      {children}
    </label>
  );
}

function Toggle({ label, value, onChange, saved, disabled }: {
  label: string; value: boolean; onChange: (v: boolean) => void; saved?: boolean; disabled?: boolean;
}) {
  return (
    <Row label={label} saved={saved}>
      <button role="switch" aria-checked={value} aria-label={label} disabled={disabled}
        onClick={() => onChange(!value)}
        className={`h-6 w-11 rounded-full transition-colors disabled:opacity-40 ${value ? "bg-terraza-accent" : "bg-terraza-dash"}`}>
        <span className={`block h-5 w-5 translate-y-0.5 rounded-full bg-terraza-card transition-transform ${value ? "translate-x-[22px]" : "translate-x-0.5"}`} />
      </button>
    </Row>
  );
}

function Select({ label, value, options, onChange, saved, err }: {
  label: string; value: string; options: string[];
  onChange: (v: string) => void; saved?: boolean; err?: string;
}) {
  return (
    <div>
      <Row label={label} saved={saved}>
        <select value={value} onChange={(e) => onChange(e.target.value)}
          className="rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-1.5 text-sm">
          {options.map((o) => <option key={o} value={o}>{o.replace(/_/g, " ")}</option>)}
        </select>
      </Row>
      {err && <p className="mt-1 text-sm text-terraza-danger">{err}</p>}
    </div>
  );
}

function Num({ label, value, min, max, step = 1, onChange, saved, err }: {
  label: string; value: number; min: number; max: number; step?: number;
  onChange: (v: number) => void; saved?: boolean; err?: string;
}) {
  return (
    <div>
      <Row label={label} saved={saved}>
        <input type="number" value={value} min={min} max={max} step={step}
          onChange={(e) => onChange(step < 1 ? parseFloat(e.target.value) : parseInt(e.target.value, 10))}
          className="w-24 rounded-[10px] border border-terraza-dash bg-terraza-bg px-3 py-1.5 text-sm" />
      </Row>
      {err && <p className="mt-1 text-sm text-terraza-danger">{err}</p>}
    </div>
  );
}

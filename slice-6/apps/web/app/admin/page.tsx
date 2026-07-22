"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/header";
import { Protected } from "@/components/protected";
import { Card } from "@/components/ui";
import { api, type AdminUser, type ContentItem, type ImportResult } from "@/lib/api";
import { getStoredToken, uploadCsv } from "@/lib/admin-api";
import { useAuth } from "@/lib/auth-context";

const ROLES = ["user", "beta_tester", "moderator", "content_editor", "admin", "owner"];

function AdminInner() {
  const { user } = useAuth();
  const router = useRouter();
  const canManageUsers = user?.capabilities.includes("user_manage");
  const canImport = user?.capabilities.includes("content_import");
  // Bumped whenever an import finishes, so the content list re-fetches.
  const [refreshKey, setRefreshKey] = useState(0);

  // If a signed-in user without admin access lands here, send them home.
  useEffect(() => {
    if (user && !user.capabilities.includes("admin_panel")) router.replace("/dashboard");
  }, [user, router]);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <h1 className="mb-6 text-2xl lowercase tracking-cozy">admin</h1>
        <div className="flex flex-col gap-6">
          {canImport && <ImportSection onImported={() => setRefreshKey((k) => k + 1)} />}
          <ContentSection refreshKey={refreshKey} />
          {canManageUsers && <UsersSection />}
        </div>
      </main>
    </>
  );
}

function ImportSection({ onImported }: { onImported: () => void }) {
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<"vocabulary" | "grammar">("vocabulary");

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const token = getStoredToken();
    if (!token) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await uploadCsv(token, kind, file);
      setResult(r);
      onImported();  // tell the content list to reload
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed.");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  return (
    <Card>
      <div className="mb-3 text-xs tracking-label text-terraza-soft">IMPORT CURRICULUM</div>
      <p className="mb-4 text-sm text-terraza-soft">
        upload a CSV to load {kind} into the database as drafts. nothing publishes automatically —
        you review and publish below.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as "vocabulary" | "grammar")}
          className="rounded-[12px] border border-terraza-dash bg-terraza-bg px-3 py-2"
        >
          <option value="vocabulary">vocabulary</option>
          <option value="grammar">grammar</option>
        </select>
        <label className="cursor-pointer rounded-full bg-terraza-accent px-5 py-2 text-terraza-accentInk">
          {busy ? "importing…" : "choose CSV"}
          <input type="file" accept=".csv" onChange={onFile} disabled={busy} className="hidden" />
        </label>
      </div>

      {error && (
        <p role="alert" className="mt-4 rounded-[12px] border border-terraza-danger/40 bg-terraza-danger/10 px-4 py-2 text-sm text-terraza-danger">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-4 rounded-[14px] border border-terraza-dash bg-terraza-bg p-4">
          <p className="tracking-cozy">
            imported {result.created} new · updated {result.updated}
          </p>
          <p className="mt-1 text-sm text-terraza-soft">
            {result.report.error_count} errors · {result.report.warning_count} warnings
          </p>
          {result.report.issues.filter((i) => i.severity === "error").length > 0 && (
            <div className="mt-3">
              <p className="text-xs tracking-label text-terraza-danger">ERRORS</p>
              <ul className="mt-1 text-sm text-terraza-soft">
                {result.report.issues
                  .filter((i) => i.severity === "error")
                  .slice(0, 10)
                  .map((i, idx) => (
                    <li key={idx}>
                      row {i.row}: {i.message} {i.value && `(${i.value})`}
                    </li>
                  ))}
              </ul>
            </div>
          )}
          <details className="mt-3">
            <summary className="cursor-pointer text-sm text-terraza-soft">
              {result.report.warning_count} warnings (click to view)
            </summary>
            <ul className="mt-2 max-h-48 overflow-auto text-sm text-terraza-soft">
              {result.report.issues
                .filter((i) => i.severity === "warning")
                .slice(0, 60)
                .map((i, idx) => (
                  <li key={idx}>
                    {i.field}: {i.message} {i.value && `(${i.value})`}
                  </li>
                ))}
            </ul>
          </details>
        </div>
      )}
    </Card>
  );
}

function ContentSection({ refreshKey }: { refreshKey: number }) {
  const [tab, setTab] = useState<"vocabulary" | "grammar">("vocabulary");
  const [items, setItems] = useState<ContentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [level, setLevel] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [publishingAll, setPublishingAll] = useState(false);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    setLoading(true);
    try {
      const res = tab === "vocabulary"
        ? await api.listVocabulary(token, level)
        : await api.listGrammar(token, level);
      setItems(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [tab, level]);

  // Reload when the tab/level changes OR after an import (refreshKey bump).
  useEffect(() => { load(); }, [load, refreshKey]);

  async function publish(id: string) {
    const token = getStoredToken();
    if (!token || tab !== "vocabulary") return;
    await api.setVocabStatus(token, id, "published");
    load();
  }

  async function publishAll() {
    const token = getStoredToken();
    if (!token || tab !== "vocabulary") return;
    const drafts = items.filter((i) => i.status !== "published");
    if (drafts.length === 0) return;
    setPublishingAll(true);
    try {
      // Publish sequentially so the server audit-logs each change.
      for (const it of drafts) {
        await api.setVocabStatus(token, it.id, "published");
      }
      await load();
    } finally {
      setPublishingAll(false);
    }
  }

  return (
    <Card>
      <div className="mb-3 flex items-center gap-3">
        <span className="text-xs tracking-label text-terraza-soft">CONTENT</span>
        <div className="ml-auto flex gap-1">
          {(["vocabulary", "grammar"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-full px-3 py-1 text-sm ${
                tab === t ? "bg-terraza-pill" : "text-terraza-soft"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3 flex items-center gap-2 text-sm">
        <span className="text-terraza-soft">level</span>
        <select
          value={level}
          onChange={(e) => setLevel(Number(e.target.value))}
          className="rounded-[10px] border border-terraza-dash bg-terraza-bg px-2 py-1"
        >
          {Array.from({ length: 10 }, (_, i) => i + 1).map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <span className="text-terraza-soft">{total} items</span>
        {tab === "vocabulary" && items.some((i) => i.status !== "published") && (
          <button
            onClick={publishAll}
            disabled={publishingAll}
            className="ml-auto rounded-full bg-terraza-green px-4 py-1 text-sm tracking-cozy disabled:opacity-50"
          >
            {publishingAll ? "publishing…" : "publish all in level"}
          </button>
        )}
      </div>

      {loading ? (
        <p className="py-6 text-center font-empty italic text-terraza-soft">un momento ~</p>
      ) : items.length === 0 ? (
        <p className="py-6 text-center font-empty italic text-terraza-soft">
          nothing here yet ~ import a CSV above
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs tracking-label text-terraza-soft">
                <th className="py-2">term</th>
                <th>translation</th>
                <th>pos</th>
                <th>status</th>
                {tab === "vocabulary" && <th></th>}
              </tr>
            </thead>
            <tbody>
              {items.map((it) => (
                <tr key={it.id} className="border-t border-terraza-dash">
                  <td className="py-2">{it.term}</td>
                  <td className="text-terraza-soft">{it.translation}</td>
                  <td className="text-terraza-soft">{it.part_of_speech || "—"}</td>
                  <td>
                    <span className="rounded-full bg-terraza-pill px-2 py-0.5 text-xs">
                      {it.status}
                    </span>
                  </td>
                  {tab === "vocabulary" && (
                    <td className="text-right">
                      {it.status !== "published" && (
                        <button
                          onClick={() => publish(it.id)}
                          className="rounded-full bg-terraza-green px-3 py-1 text-xs"
                        >
                          publish
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function UsersSection() {
  const [users, setUsers] = useState<AdminUser[]>([]);

  const load = useCallback(async () => {
    const token = getStoredToken();
    if (!token) return;
    setUsers(await api.listUsers(token));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function onRole(id: string, role: string) {
    const token = getStoredToken();
    if (!token) return;
    try {
      await api.changeRole(token, id, role);
      load();
    } catch {
      load();
    }
  }

  return (
    <Card>
      <div className="mb-3 text-xs tracking-label text-terraza-soft">USERS</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs tracking-label text-terraza-soft">
              <th className="py-2">name</th>
              <th>email</th>
              <th>role</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id} className="border-t border-terraza-dash">
                <td className="py-2">{u.name}</td>
                <td className="text-terraza-soft">{u.email}</td>
                <td>
                  <select
                    value={u.role}
                    onChange={(e) => onRole(u.id, e.target.value)}
                    className="rounded-[10px] border border-terraza-dash bg-terraza-bg px-2 py-1"
                  >
                    {ROLES.map((r) => (
                      <option key={r} value={r}>{r}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export default function AdminPage() {
  return (
    <Protected>
      <AdminInner />
    </Protected>
  );
}

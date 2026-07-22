// Admin-specific fetch helpers that need multipart upload (outside the JSON client).
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

import type { ImportResult } from "./api";

export async function uploadCsv(
  token: string,
  kind: "vocabulary" | "grammar",
  file: File,
): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/api/v1/admin/imports/${kind}`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(data?.error?.message ?? "Import failed.");
  }
  return data as ImportResult;
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("polyglot.tokens");
    return raw ? (JSON.parse(raw).access_token as string) : null;
  } catch {
    return null;
  }
}

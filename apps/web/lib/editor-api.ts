// Curriculum-editor API client (slice 39). Uses the JSON admin endpoints added
// to the admin router. Bearer token from localStorage, same as admin-api.ts.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface EditorItem {
  id: string;
  kind: "vocabulary" | "grammar";
  term: string;
  translation: string;
  part_of_speech: string;
  meaning: string;
  level: number;
  batch?: number; // vocabulary only
  structure_pattern?: string; // grammar only
  article?: string;
  gender?: string;
  status: string;
  archived: boolean;
}

export interface EditorList {
  items: EditorItem[];
  total: number;
}

export type Kind = "vocabulary" | "grammar";

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

async function handle<T>(res: Response): Promise<T> {
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg =
      (data && data.error && data.error.message) ||
      (res.status === 422 ? "Please check the values and try again." : "Request failed.");
    throw new Error(msg);
  }
  return data as T;
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

export async function listEditorItems(
  token: string,
  kind: Kind,
  opts: { level?: number; includeArchived?: boolean } = {},
): Promise<EditorList> {
  const p = new URLSearchParams();
  if (opts.level != null) p.set("level", String(opts.level));
  if (opts.includeArchived) p.set("include_archived", "true");
  const qs = p.toString();
  const res = await fetch(
    `${API_URL}/api/v1/admin/content/${kind}/editor${qs ? `?${qs}` : ""}`,
    { headers: authHeaders(token) },
  );
  return handle<EditorList>(res);
}

export async function createItem(
  token: string,
  kind: Kind,
  body: Record<string, unknown>,
): Promise<EditorItem> {
  const res = await fetch(`${API_URL}/api/v1/admin/content/${kind}`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return handle<EditorItem>(res);
}

export async function updateItem(
  token: string,
  kind: Kind,
  id: string,
  body: Record<string, unknown>,
): Promise<EditorItem> {
  const res = await fetch(`${API_URL}/api/v1/admin/content/${kind}/${id}`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return handle<EditorItem>(res);
}

export async function moveItem(
  token: string,
  kind: Kind,
  id: string,
  body: { level: number; batch?: number },
): Promise<EditorItem> {
  const res = await fetch(`${API_URL}/api/v1/admin/content/${kind}/${id}/move`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return handle<EditorItem>(res);
}

export async function deleteItem(token: string, kind: Kind, id: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/admin/content/${kind}/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  await handle<unknown>(res);
}

export async function restoreItem(
  token: string,
  kind: Kind,
  id: string,
): Promise<EditorItem> {
  const res = await fetch(`${API_URL}/api/v1/admin/content/${kind}/${id}/restore`, {
    method: "POST",
    headers: authHeaders(token),
  });
  return handle<EditorItem>(res);
}

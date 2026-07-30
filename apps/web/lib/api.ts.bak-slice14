// Thin client for the Polyglot API. Base URL comes from env so the same build
// works locally and in Docker. All auth calls funnel through here.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Tokens {
  access_token: string;
  refresh_token: string;
}

export interface Me {
  id: string;
  email: string;
  name: string;
  role: string;
  capabilities: string[];
}

export interface ApiError {
  code: string;
  message: string;
}

class ApiClientError extends Error {
  code: string;
  status: number;
  constructor(status: number, error: ApiError) {
    super(error.message);
    this.code = error.code;
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; token?: string } = {},
): Promise<T> {
  const { method = "GET", body, token } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiClientError(0, {
      code: "network_error",
      message: "Cannot reach the server. Is the API running?",
    });
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err: ApiError = data?.error ?? { code: "unknown", message: "Something went wrong." };
    throw new ApiClientError(res.status, err);
  }
  return data as T;
}

export const api = {
  signup: (email: string, name: string, password: string) =>
    request<Tokens>("/api/v1/auth/signup", { method: "POST", body: { email, name, password } }),
  login: (email: string, password: string) =>
    request<Tokens>("/api/v1/auth/login", { method: "POST", body: { email, password } }),
  refresh: (refresh_token: string) =>
    request<Tokens>("/api/v1/auth/refresh", { method: "POST", body: { refresh_token } }),
  logout: (refresh_token: string) =>
    request<void>("/api/v1/auth/logout", { method: "POST", body: { refresh_token } }),
  me: (token: string) => request<Me>("/api/v1/auth/me", { token }),

  // Admin
  listVocabulary: (token: string, level?: number) =>
    request<ContentList>(
      `/api/v1/admin/content/vocabulary${level ? `?level=${level}` : ""}`, { token },
    ),
  listGrammar: (token: string, level?: number) =>
    request<ContentList>(
      `/api/v1/admin/content/grammar${level ? `?level=${level}` : ""}`, { token },
    ),
  setVocabStatus: (token: string, id: string, status: string) =>
    request<{ id: string; status: string }>(
      `/api/v1/admin/content/vocabulary/${id}/status`,
      { method: "PATCH", body: { status }, token },
    ),
  listUsers: (token: string) => request<AdminUser[]>("/api/v1/admin/users", { token }),
  changeRole: (token: string, id: string, role: string) =>
    request<AdminUser>(
      `/api/v1/admin/users/${id}/role`, { method: "PATCH", body: { role }, token },
    ),
};

export interface ContentItem {
  id: string; term: string; translation: string;
  part_of_speech: string; level: number; status: string;
}
export interface ContentList { items: ContentItem[]; total: number; }
export interface AdminUser {
  id: string; email: string; name: string; role: string; status: string;
}
export interface ImportReport {
  kind: string; rows_seen: number; rows_ok: number;
  error_count: number; warning_count: number;
  level_counts: Record<string, number>;
  issues: { severity: string; row: number; field: string; message: string; value: string }[];
}
export interface ImportResult { created: number; updated: number; report: ImportReport; }

export { ApiClientError };

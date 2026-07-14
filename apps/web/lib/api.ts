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
  signup: (email: string, password: string) =>
    request<Tokens>("/api/v1/auth/signup", { method: "POST", body: { email, password } }),
  login: (email: string, password: string) =>
    request<Tokens>("/api/v1/auth/login", { method: "POST", body: { email, password } }),
  refresh: (refresh_token: string) =>
    request<Tokens>("/api/v1/auth/refresh", { method: "POST", body: { refresh_token } }),
  logout: (refresh_token: string) =>
    request<void>("/api/v1/auth/logout", { method: "POST", body: { refresh_token } }),
  me: (token: string) => request<Me>("/api/v1/auth/me", { token }),
};

export { ApiClientError };

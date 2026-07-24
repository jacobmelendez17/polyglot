// Shared authenticated fetch helper.
//
// `learn-api.ts` grew its own copy of this first; rather than add a third one
// for the item endpoints, new clients import from here. Migrating learn-api to
// this helper is a follow-up cleanup — behaviour is identical, so it can happen
// in any later slice without touching call sites.

import { getStoredToken } from "./admin-api";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError("Could not reach the server.", 0, "network_error");
  }

  if (res.status === 204) return undefined as T;

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      data?.detail?.error?.message ?? data?.error?.message ?? "Request failed.",
      res.status,
      data?.detail?.error?.code ?? data?.error?.code ?? "error",
    );
  }
  return data as T;
}

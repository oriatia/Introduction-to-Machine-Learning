import { cookies } from "next/headers";
import { SESSION_COOKIE, type Me } from "./api-types";

const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

/** Server-side call to the API, forwarding the caller's cookies. Never cached. */
export async function apiFetch(path: string): Promise<Response> {
  const cookieHeader = (await cookies()).toString();
  return fetch(`${API_INTERNAL_URL}${path}`, { headers: { cookie: cookieHeader }, cache: "no-store" });
}

export async function getMe(): Promise<Me | null> {
  if (!(await cookies()).has(SESSION_COOKIE)) return null;
  const res = await apiFetch("/api/auth/me");
  if (res.status === 401) return null;
  if (!res.ok) throw new Error(`GET /api/auth/me failed: ${res.status}`);
  return (await res.json()) as Me;
}

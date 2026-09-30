export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; error: string; retryAfter?: number };

/** Browser-side JSON POST to our own origin (/api is proxied to the API). */
export async function postJson<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(path, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, error: "generic" };
  }
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.ok) return { ok: true, status: res.status, data: data as T };
  const error = typeof data?.error === "string" ? data.error : "generic";
  const retryAfter = typeof data?.retry_after === "number" ? data.retry_after : undefined;
  return { ok: false, status: res.status, error, retryAfter };
}

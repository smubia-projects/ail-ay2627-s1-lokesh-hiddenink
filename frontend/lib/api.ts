// Small API client. The backend is a stateless public demo on Cloud Run; no tokens, no accounts.
//
// api() also watches for the shared rate-limit engine's responses:
//  - 429 -> dispatches RATE_LIMIT_EVENT with detail.queries_used (the CTA modal reads it)
//  - 503 -> dispatches DEMO_PAUSED_EVENT with the body's message (kill switch: "demo paused" notice)
// components/RateLimitCTA.tsx listens for both. The thrown ApiError is marked `handled`, so pages
// skip their own error alert for these.
export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000").replace(/\/$/, "");

export const RATE_LIMIT_EVENT = "hiddenink:rate-limit";
export const DEMO_PAUSED_EVENT = "hiddenink:demo-paused";

export class ApiError extends Error {
  status: number;
  handled: boolean;
  constructor(status: number, message: string, handled = false) {
    super(message);
    this.status = status;
    this.handled = handled;
  }
}

/** The message to show for a failed request, or "" when a modal already handled it (429 / 503). */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.handled) return "";
  return e instanceof Error ? e.message : String(e);
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the HiddenInk server. Is the backend running?");
  }
  if (!res.ok) {
    let body: any = null;
    try { body = await res.json(); } catch {}
    const detail = body?.detail;
    if (res.status === 429) {
      window.dispatchEvent(new CustomEvent(RATE_LIMIT_EVENT, { detail: { queriesUsed: Number(detail?.queries_used ?? 0) } }));
      throw new ApiError(429, detail?.message || "Rate limit exceeded.", true);
    }
    if (res.status === 503) {
      const message = (typeof detail === "object" && detail?.message) || "This demo is temporarily paused. Check back soon.";
      window.dispatchEvent(new CustomEvent(DEMO_PAUSED_EVENT, { detail: { message } }));
      throw new ApiError(503, message, true);
    }
    let msg = `Request failed (${res.status})`;
    if (typeof detail === "string") msg = detail;
    else if (Array.isArray(detail)) msg = detail.map((d: any) => d.msg).join("; ");
    else if (detail?.message) msg = detail.message;
    throw new ApiError(res.status, msg);
  }
  return res.json();
}

export function downloadBlob(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function b64ToBlob(b64: string, type: string): Blob {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], { type });
}

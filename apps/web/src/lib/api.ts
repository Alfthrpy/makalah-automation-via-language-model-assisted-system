/** Klien API tipis. Token Clerk dipasang lewat `setTokenGetter` (lihat auth.tsx).
 *  Tidak pernah menyimpan atau mencatat badan permintaan (bisa berisi API key). */

export interface FieldIssue { loc: (string | number)[]; type: string; msg: string; ctx?: Record<string, unknown> }

export class ApiError extends Error {
  status: number; // 0 = jaringan/server tidak terjangkau
  issues: FieldIssue[];
  constructor(status: number, message: string, issues: FieldIssue[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.issues = issues;
  }
}

type TokenGetter = () => Promise<string | null>;
let tokenGetter: TokenGetter = async () => null;
export const setTokenGetter = (fn: TokenGetter) => { tokenGetter = fn; };

const unauthorizedListeners = new Set<() => void>();
export const onUnauthorized = (fn: () => void) => { unauthorizedListeners.add(fn); return () => { unauthorizedListeners.delete(fn); }; };

async function authHeaders(extra?: HeadersInit): Promise<Headers> {
  const h = new Headers(extra);
  let token: string | null = null;
  try { token = await tokenGetter(); } catch { token = null; }
  if (token) h.set("Authorization", `Bearer ${token}`);
  return h;
}

async function toError(res: Response): Promise<ApiError> {
  let detail: unknown = null;
  try { detail = (await res.json() as { detail?: unknown }).detail; } catch { /* badan bukan JSON */ }
  if (Array.isArray(detail)) {
    return new ApiError(res.status, "Ada isian yang belum sesuai.", detail as FieldIssue[]);
  }
  return new ApiError(res.status, typeof detail === "string" && detail ? detail : `Permintaan gagal (${res.status}).`);
}

async function request(path: string, init: RequestInit = {}, announce401 = true): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: await authHeaders(init.headers), credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Server tidak bisa dihubungi.");
  }
  if (!res.ok) {
    if (res.status === 401 && announce401) unauthorizedListeners.forEach((fn) => fn());
    throw await toError(res);
  }
  return res;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await request(path, init);
  return (await res.json()) as T;
}

export const apiPost = <T>(path: string, body: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const apiDelete = <T>(path: string) => api<T>(path, { method: "DELETE" });

/** Unduh .docx lewat fetch + header (tidak mengandalkan cookie), lalu picu simpan lewat tautan sementara. */
export async function downloadJobFile(id: string, fallbackName: string): Promise<void> {
  const res = await request(`/api/jobs/${encodeURIComponent(id)}/download`);
  const blob = await res.blob();
  const m = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = m?.[1] ?? fallbackName;
  a.rel = "noopener";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

/** Logo kampus/sekolah (satu per akun). Unggahan mentah PNG; pratinjau diambil lewat fetch + header (bukan <img src>). */
export async function putLogo(png: Blob): Promise<{ size: number; updated_at?: string | null }> {
  const res = await request("/api/logo", { method: "PUT", headers: { "Content-Type": "image/png" }, body: png });
  return res.json();
}
export async function fetchLogo(): Promise<Blob> {
  return (await request("/api/logo")).blob();
}

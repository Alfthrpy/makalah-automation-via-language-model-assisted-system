// Cloudflare Pages Function: meneruskan /api/* ke backend (Space HF) agar browser tetap hanya bicara ke satu origin
// (tanpa CORS), sama seperti proxy `/api/*` di netlify.toml. Hanya rute /api/* yang memanggil fungsi ini; halaman dan
// aset statis dilayani langsung (gratis, tidak masuk kuota fungsi).
//
// Env opsional (Pages > Settings > Variables): BACKEND_ORIGIN, mis. https://pemilik-nama.hf.space (harus https).
const DEFAULT_BACKEND = "https://petanihandal-stegano-f5-dmcss-api.hf.space";

// Header yang tidak diteruskan: hop-by-hop, dan yang diisi ulang oleh runtime/tujuan.
const DROP = new Set([
  "host", "connection", "keep-alive", "transfer-encoding", "te", "trailer", "upgrade", "content-length",
  "proxy-authorization", "proxy-authenticate", "x-real-ip",
]);

function backendOrigin(env) {
  const raw = ((env && env.BACKEND_ORIGIN) || DEFAULT_BACKEND).trim().replace(/\/+$/, "");
  const u = new URL(raw); // melempar bila tidak valid
  if (u.protocol !== "https:" || u.username || u.password || u.pathname !== "/" ) throw new Error("BACKEND_ORIGIN harus https://host saja");
  return u.origin;
}

const json = (status, detail) =>
  new Response(JSON.stringify({ detail }), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

export async function onRequest({ request, env }) {
  const url = new URL(request.url);
  if (url.pathname !== "/api" && !url.pathname.startsWith("/api/")) return json(404, "Not Found");

  let origin;
  try {
    origin = backendOrigin(env);
  } catch {
    return json(500, "Konfigurasi proxy tidak valid");
  }

  const headers = new Headers();
  for (const [k, v] of request.headers) {
    const lk = k.toLowerCase();
    if (DROP.has(lk) || lk.startsWith("cf-") || lk.startsWith("x-forwarded-")) continue;
    headers.set(k, v);
  }
  headers.set("x-forwarded-proto", "https");

  const hasBody = request.method !== "GET" && request.method !== "HEAD";
  try {
    const upstream = await fetch(origin + url.pathname + url.search, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual", // jangan mengikuti redirect: header Authorization tidak boleh pindah host
    });
    return new Response(upstream.body, upstream); // status, header (termasuk Set-Cookie), dan isi apa adanya
  } catch {
    return json(502, "Backend tidak terjangkau. Coba lagi sebentar.");
  }
}

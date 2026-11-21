// Tes fungsi proxy /api: `node --test deploy/cloudflare/proxy.test.mjs` (Node >= 22; fetch ke backend di-stub).
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { onRequest } from "./functions/api/[[path]].js";

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

function stub(respond) {
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push({ url, init }); return respond(url, init); };
  return calls;
}
const call = (path, init, env) => onRequest({ request: new Request("https://malas.test" + path, init), env: env || {} });

test("meneruskan metode, path, query, isi, dan header penting ke backend", async () => {
  const calls = stub(() => new Response('{"ok":true}', { status: 202, headers: { "content-type": "application/json", "set-cookie": "a=b; Path=/" } }));
  const r = await call("/api/jobs?x=1", {
    method: "POST", body: '{"judul":"x"}',
    headers: { authorization: "Bearer T", cookie: "__session=S", "content-type": "application/json",
               "cf-connecting-ip": "1.2.3.4", "x-forwarded-for": "9.9.9.9", "x-forwarded-host": "evil.test" },
  });
  assert.equal(r.status, 202);
  assert.equal(r.headers.get("set-cookie"), "a=b; Path=/");
  assert.equal(await r.text(), '{"ok":true}');
  const { url, init } = calls[0];
  assert.equal(url, "https://petanihandal-stegano-f5-dmcss-api.hf.space/api/jobs?x=1");
  assert.equal(init.method, "POST");
  assert.equal(init.redirect, "manual");
  assert.ok(init.body);
  const h = init.headers;
  assert.equal(h.get("authorization"), "Bearer T");
  assert.equal(h.get("cookie"), "__session=S");
  assert.equal(h.get("x-forwarded-proto"), "https");
  for (const k of ["cf-connecting-ip", "x-forwarded-for", "x-forwarded-host", "host"]) assert.equal(h.get(k), null, k);
});

test("GET tanpa isi; status error backend diteruskan", async () => {
  const calls = stub(() => new Response('{"detail":"x"}', { status: 401 }));
  const r = await call("/api/me");
  assert.equal(r.status, 401);
  assert.equal(calls[0].init.body, undefined);
  assert.equal(calls[0].init.method, "GET");
});

test("redirect dari backend tidak diikuti (diteruskan apa adanya)", async () => {
  stub(() => new Response(null, { status: 302, headers: { location: "https://evil.test/" } }));
  const r = await call("/api/x", { headers: { authorization: "Bearer T" } });
  assert.equal(r.status, 302);
});

test("selain /api/* ditolak 404 dan tidak memanggil backend", async () => {
  const calls = stub(() => new Response("x"));
  for (const p of ["/", "/apix", "/ketentuan"]) assert.equal((await call(p)).status, 404);
  assert.equal(calls.length, 0);
});

test("BACKEND_ORIGIN harus https tanpa path/kredensial; bila tidak, 500 tanpa memanggil backend", async () => {
  const calls = stub(() => new Response("x"));
  for (const o of ["http://x.test", "https://u:p@x.test", "https://x.test/path", "bukan url"])
    assert.equal((await call("/api/me", {}, { BACKEND_ORIGIN: o })).status, 500, o);
  assert.equal(calls.length, 0);
  const ok = await call("/api/me", {}, { BACKEND_ORIGIN: "https://lain.hf.space/" });
  assert.equal(ok.status, 200);
  assert.equal(calls[0].url, "https://lain.hf.space/api/me");
});

test("backend tidak terjangkau -> 502 JSON", async () => {
  stub(() => { throw new Error("jaringan"); });
  const r = await call("/api/me");
  assert.equal(r.status, 502);
  assert.match((await r.json()).detail, /tidak terjangkau/);
});

#!/usr/bin/env python3
"""Deploy hasil build web ke situs Netlify lewat API (tanpa Netlify CLI, hanya pustaka standar).

    VITE_AUTH_MODE=clerk VITE_CLERK_PUBLISHABLE_KEY=pk_... pnpm --filter web build
    NETLIFY_AUTH_TOKEN=... python3 deploy/netlify/deploy.py --site <site-id> [--dir apps/web/dist]

`netlify.toml` tidak dibaca oleh deploy via API, jadi skrip ini menurunkan `_redirects` dan `_headers` dari berkas itu
(proxy /api/*, fallback SPA, header keamanan/CSP) dan memasukkannya ke deploy. Hanya berkas yang berubah yang diunggah.
Bila situs git-linked ke Netlify, skrip ini tidak diperlukan (Netlify membangun sendiri dari `main`).
"""
import argparse
import hashlib
import json
import os
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.netlify.com/api/v1"


def call(token: str, method: str, path: str, body=None, raw: bytes | None = None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(API + path, method=method, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": ctype, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Netlify API {method} {path} -> {e.code}: {e.read().decode()[:300]}")


def write_edge_files(dist: Path, toml_path: Path) -> None:
    cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    redirects = [f"{r['from']}  {r['to']}  {r['status']}{'!' if r.get('force') else ''}" for r in cfg.get("redirects", [])]
    (dist / "_redirects").write_text("\n".join(redirects) + "\n", encoding="utf-8")
    lines: list[str] = []
    for h in cfg.get("headers", []):
        lines.append(h["for"])
        lines += [f"  {k}: {v}" for k, v in h["values"].items()]
    (dist / "_headers").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, help="ID situs Netlify (Site configuration > Site ID)")
    ap.add_argument("--dir", default=str(root / "apps/web/dist"))
    ap.add_argument("--toml", default=str(root / "netlify.toml"))
    a = ap.parse_args()
    token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    if not token:
        sys.exit("Isi NETLIFY_AUTH_TOKEN (Netlify > User settings > Applications > Personal access tokens).")
    dist = Path(a.dir)
    if not (dist / "index.html").is_file():
        sys.exit(f"{dist}/index.html tidak ada. Jalankan build web dulu.")
    write_edge_files(dist, Path(a.toml))

    files = {"/" + p.relative_to(dist).as_posix(): hashlib.sha1(p.read_bytes()).hexdigest()
             for p in sorted(dist.rglob("*")) if p.is_file()}
    d = call(token, "POST", f"/sites/{a.site}/deploys", {"files": files})
    need = set(d.get("required", []))
    print(f"deploy {d['id']}: {len(files)} berkas, {len(need)} perlu diunggah")
    for rel, sha in files.items():
        if sha in need:
            call(token, "PUT", f"/deploys/{d['id']}/files{rel}", raw=(dist / rel.lstrip("/")).read_bytes(),
                 ctype="application/octet-stream")
    for _ in range(40):
        st = call(token, "GET", f"/deploys/{d['id']}")
        if st.get("state") in ("ready", "error"):
            break
        time.sleep(3)
    print("state:", st.get("state"), "| error:", st.get("error_message"))
    print("URL:", st.get("ssl_url"))
    if st.get("state") != "ready":
        sys.exit(1)


if __name__ == "__main__":
    main()

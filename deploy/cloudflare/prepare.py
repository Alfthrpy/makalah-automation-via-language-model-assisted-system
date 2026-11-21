#!/usr/bin/env python3
"""Menyiapkan folder build web (apps/web/dist) untuk Cloudflare Pages.

    python3 deploy/cloudflare/prepare.py [--dist apps/web/dist] [--out deploy/cloudflare/.stage] [--toml netlify.toml]

Hasil di --out (dist TIDAK diubah):
  - `_headers`    diturunkan dari [[headers]] di netlify.toml (CSP, HSTS, cache aset ber-hash): satu sumber kebenaran.
  - `_redirects`  hanya fallback SPA. Aturan Netlify tidak dibawa: proxy /api/* ditangani Pages Function
                  (functions/api/[[path]].js; `_redirects` Cloudflare tidak bisa proxy ke host luar), pengalihan
                  malas-app.netlify.app khusus Netlify, dan aturan halaman prerender tidak perlu (lihat berikut).
  - Halaman prerender `<rute>/index.html` dipindah ke `<rute>.html`. Cloudflare Pages melayani `<rute>.html` di URL
    `/<rute>` (tanpa garis miring penutup) dan mengalihkan `/<rute>.html` ke `/<rute>`; bentuk direktori akan dialihkan ke
    `/<rute>/`, yang membuat URL berbeda dari canonical dan sitemap.
"""
import argparse
import shutil
import sys
import tomllib
from pathlib import Path

SPA_FALLBACK = "/*  /index.html  200"


def headers_file(cfg: dict) -> str:
    lines: list[str] = []
    for h in cfg.get("headers", []):
        lines.append(h["for"])
        lines += [f"  {k}: {v}" for k, v in h["values"].items()]
    return "\n".join(lines) + "\n"


def flatten_pages(out: Path) -> list[str]:
    """`x/index.html` -> `x.html` untuk semua halaman prerender (bukan index.html di root). Mengembalikan rute."""
    moved: list[str] = []
    for p in sorted(out.rglob("index.html"), key=lambda q: -len(q.parts)):
        if p.parent == out:
            continue
        route = p.parent.relative_to(out).as_posix()
        target = out / f"{route}.html"
        if target.exists():
            raise SystemExit(f"Bentrok: {target} sudah ada")
        p.rename(target)
        if not any(p.parent.iterdir()):
            p.parent.rmdir()
        moved.append("/" + route)
    return moved


def prepare(dist: Path, out: Path, toml_path: Path) -> list[str]:
    if not (dist / "index.html").is_file():
        raise SystemExit(f"{dist}/index.html tidak ada. Jalankan build web dulu.")
    cfg = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(dist, out)
    moved = flatten_pages(out)
    (out / "_redirects").write_text(SPA_FALLBACK + "\n", encoding="utf-8")
    (out / "_headers").write_text(headers_file(cfg), encoding="utf-8")
    return moved


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dist", default=str(root / "apps/web/dist"))
    ap.add_argument("--out", default=str(root / "deploy/cloudflare/.stage"))
    ap.add_argument("--toml", default=str(root / "netlify.toml"))
    a = ap.parse_args()
    moved = prepare(Path(a.dist), Path(a.out), Path(a.toml))
    print(f"siap di {a.out}; {len(moved)} halaman prerender -> <rute>.html")


if __name__ == "__main__":
    sys.exit(main())

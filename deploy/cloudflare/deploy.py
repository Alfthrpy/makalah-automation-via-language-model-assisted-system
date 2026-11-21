#!/usr/bin/env python3
"""Deploy web ke Cloudflare Pages (Direct Upload) lewat wrangler.

    VITE_AUTH_MODE=clerk VITE_CLERK_PUBLISHABLE_KEY=pk_... pnpm --filter web build
    CLOUDFLARE_API_TOKEN=... CLOUDFLARE_ACCOUNT_ID=... python3 deploy/cloudflare/deploy.py --project malas-app [--branch main]

Token API: izin "Cloudflare Pages: Edit" (+ "Zone > DNS: Edit" bila domain dikelola lewat skrip/dashboard).
wrangler dijalankan dari deploy/cloudflare/ agar folder `functions/` (proxy /api) ikut diunggah. Lihat README.md di sini.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import prepare  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="Nama project Cloudflare Pages")
    ap.add_argument("--branch", default="main", help="Cabang produksi project (deploy ke produksi bila sama)")
    ap.add_argument("--dist", default=str(ROOT / "apps/web/dist"))
    a = ap.parse_args()
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        sys.exit("Isi CLOUDFLARE_API_TOKEN (dan CLOUDFLARE_ACCOUNT_ID bila token punya lebih dari satu akun).")
    stage = HERE / ".stage"
    moved = prepare(Path(a.dist), stage, ROOT / "netlify.toml")
    print(f"{len(moved)} halaman prerender disiapkan")
    subprocess.run(["npx", "--yes", "wrangler@4", "pages", "deploy", str(stage), "--project-name", a.project,
                    "--branch", a.branch, "--commit-dirty=true"], cwd=HERE, check=True)


if __name__ == "__main__":
    main()

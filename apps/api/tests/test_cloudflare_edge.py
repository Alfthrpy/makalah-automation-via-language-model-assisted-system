"""Penyiapan folder web untuk Cloudflare Pages (deploy/cloudflare/prepare.py)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("cf_prepare", ROOT / "deploy/cloudflare/prepare.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)

TOML = ROOT / "netlify.toml"
NETLIFY_ONLY_REDIRECTS = (
    "https://malas-app.netlify.app/*  https://malas.alfthrpy.my.id/:splat  301!\n"
    "/ketentuan  /ketentuan/index.html  200\n"
    "/api/*  https://backend.hf.space/api/:splat  200!\n"
    "/*  /index.html  200\n"
)


@pytest.fixture
def dist(tmp_path):
    d = tmp_path / "dist"
    for rel, body in {
        "index.html": "<title>root</title>",
        "ketentuan/index.html": "<title>ketentuan</title>",
        "panduan/index.html": "<title>panduan</title>",
        "panduan/cara-a/index.html": "<title>cara-a</title>",
        "assets/app-abc123.js": "x",
        "sitemap.xml": "<urlset/>",
        "_redirects": NETLIFY_ONLY_REDIRECTS,
    }.items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(body, encoding="utf-8")
    return d


def test_halaman_prerender_dipindah_ke_rute_html_dan_root_tetap(dist, tmp_path):
    out = tmp_path / "stage"
    moved = cf.prepare(dist, out, TOML)
    assert sorted(moved) == ["/ketentuan", "/panduan", "/panduan/cara-a"]
    assert (out / "index.html").read_text() == "<title>root</title>"
    assert (out / "ketentuan.html").read_text() == "<title>ketentuan</title>"
    assert (out / "panduan.html").is_file() and (out / "panduan/cara-a.html").is_file()
    assert not (out / "ketentuan").exists() and not (out / "panduan/index.html").exists()
    assert (out / "assets/app-abc123.js").is_file() and (out / "sitemap.xml").is_file()
    assert (dist / "ketentuan/index.html").is_file()  # sumber (dist) tidak diubah


def test_redirects_hanya_fallback_spa_tanpa_aturan_netlify(dist, tmp_path):
    out = tmp_path / "stage"
    cf.prepare(dist, out, TOML)
    text = (out / "_redirects").read_text()
    assert text.strip() == "/*  /index.html  200"
    assert "netlify" not in text and "/api" not in text and "hf.space" not in text


def test_headers_diturunkan_dari_netlify_toml(dist, tmp_path):
    out = tmp_path / "stage"
    cf.prepare(dist, out, TOML)
    h = (out / "_headers").read_text()
    for must in ("/*", "  X-Frame-Options: DENY", "  Strict-Transport-Security:", "  Content-Security-Policy: default-src 'self'",
                 "/assets/*", "  Cache-Control: public, max-age=31536000, immutable", "/index.html", "  Cache-Control: no-cache"):
        assert must in h, must
    assert all(len(line) < 2000 for line in h.splitlines())  # batas baris _headers Cloudflare


def test_tanpa_index_html_gagal_jelas(tmp_path):
    with pytest.raises(SystemExit):
        cf.prepare(tmp_path / "kosong", tmp_path / "out", TOML)


def test_fungsi_proxy_dan_netlify_toml_menunjuk_backend_yang_sama():
    import re
    js = (ROOT / "deploy/cloudflare/functions/api/[[path]].js").read_text()
    toml = TOML.read_text()
    backend = re.search(r'DEFAULT_BACKEND = "([^"]+)"', js).group(1)
    assert f"{backend}/api/:splat" in toml

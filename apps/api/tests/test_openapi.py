"""Kontrak API: packages/api-types/openapi.json harus sama dengan skema app yang sedang berjalan.
Bila gagal: `pnpm --filter @malas/api-types generate` lalu commit hasilnya."""
from pathlib import Path

from malas_api.export_openapi import DEFAULT_OUT, build_schema, render


def test_openapi_terkomit_sinkron_dengan_app():
    assert Path(DEFAULT_OUT).read_text(encoding="utf-8") == render(), (
        "openapi.json usang. Jalankan: pnpm --filter @malas/api-types generate"
    )


def test_skema_tidak_membocorkan_data_internal():
    s = build_schema()
    props = set(s["components"]["schemas"]["JobOut"]["properties"])
    assert not props & {"owner", "template_path"}
    assert "/openapi.json" not in s["paths"]  # skema hanya lewat skrip ekspor, tidak dilayani publik

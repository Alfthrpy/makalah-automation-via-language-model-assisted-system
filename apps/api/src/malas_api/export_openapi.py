"""Ekspor skema OpenAPI ke berkas (tanpa membuka /openapi.json di server).

    uv run malas-openapi [keluaran.json]     # bawaan: packages/api-types/openapi.json

Tidak menyentuh database/worker: app dibuat dengan manager tiruan karena skema hanya bergantung pada rute.
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from malas_api.app import create_app

DEFAULT_OUT = Path(__file__).resolve().parents[4] / "packages" / "api-types" / "openapi.json"


def build_schema() -> dict:
    app = create_app(manager=SimpleNamespace(), hosted=False, auth=None, daily_quota=0)
    return app.openapi()


def render() -> str:
    return json.dumps(build_schema(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"OpenAPI -> {out}")


if __name__ == "__main__":
    main()

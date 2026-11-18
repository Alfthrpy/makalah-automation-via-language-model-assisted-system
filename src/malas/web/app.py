"""Web UI MALAS: FastAPI + halaman statis (tanpa build step).

Jalankan:  uv run malas-web      (default http://127.0.0.1:8000)
Env: MALAS_WEB_HOST, MALAS_WEB_PORT, MALAS_OUTPUT_DIR, MALAS_WEB_ALLOWED_HOSTS (koma)
"""
import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, StringConstraints, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from malas import config
from malas.docx_converter import xml_safe
from malas.steps import STEPS
from malas.web.jobs import ID_RE, JobManager

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = Path("template_and_output")
DEFAULT_TEMPLATE_NAME = "template makalah.docx"
LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

Str = lambda mx, mn=0: Annotated[str, StringConstraints(strip_whitespace=True, min_length=mn, max_length=mx)]  # noqa: E731


def list_templates() -> List[str]:
    """Hanya berkas template*.docx di folder template (hasil keluaran lama tidak ikut)."""
    if not TEMPLATE_DIR.is_dir():
        return []
    return sorted(p.name for p in TEMPLATE_DIR.glob("template*.docx") if not p.name.startswith("~$"))


class PenyusunIn(BaseModel):
    nama: Str(100, 1)
    nim: Str(30) = ""


class JobRequest(BaseModel):
    judul: Str(200, 3)
    mata_kuliah: Str(120, 2)
    dosen_pengampu: Str(120) = ""
    penyusun: List[PenyusunIn] = Field(min_length=1, max_length=10)
    kelas: Str(30) = ""
    universitas: Str(150) = ""
    fakultas: Str(150) = ""
    jurusan: Str(150) = ""
    kota: Str(80) = ""
    tahun: Annotated[str, StringConstraints(pattern=r"^(19|20)\d{2}$")] = Field(
        default_factory=lambda: str(datetime.now().year)
    )
    template: Optional[str] = None
    mock: bool = False

    @field_validator("*", mode="after")
    @classmethod
    def _bersihkan(cls, v):
        return xml_safe(v) if isinstance(v, str) else v


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "makalah"


def _public(job: dict) -> dict:
    """Bentuk job untuk klien: tanpa path internal."""
    return {k: v for k, v in job.items() if k != "template_path"}


def create_app(manager: Optional[JobManager] = None, allowed_hosts: Optional[List[str]] = None) -> FastAPI:
    mgr = manager or JobManager(Path(os.getenv("MALAS_OUTPUT_DIR", "output")))
    app = FastAPI(title="MALAS", docs_url=None, redoc_url=None, openapi_url=None)
    extra = [h.strip() for h in os.getenv("MALAS_WEB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or (LOCAL_HOSTS + extra))
    app.state.manager = mgr

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/api/config")
    def get_config() -> dict:
        return {
            **config.describe(),
            "templates": list_templates(),
            "default_template": DEFAULT_TEMPLATE_NAME,
            "steps": [{"key": k, "label": l, "hint": h} for k, l, h in STEPS],
            "active_job": mgr.active_job(),
            "year": datetime.now().year,
        }

    @app.post("/api/jobs", status_code=202)
    def create_job(req: JobRequest) -> dict:
        templates = list_templates()
        name = req.template or (DEFAULT_TEMPLATE_NAME if DEFAULT_TEMPLATE_NAME in templates else (templates[0] if templates else ""))
        if name not in templates:  # cegah path traversal: hanya nama dari daftar
            raise HTTPException(422, detail=[{"loc": ["body", "template"], "msg": "Template tidak tersedia"}])
        if not req.mock and not config.describe()["api_key_ok"]:
            raise HTTPException(
                400,
                detail="API key untuk model yang dipilih belum terdeteksi. Isi .env (lihat README) atau pakai Mode uji.",
            )
        data = req.model_dump(exclude={"template", "mock"})
        job = mgr.submit(data, req.mock, str(TEMPLATE_DIR / name), name)
        return _public(job)

    @app.get("/api/jobs")
    def list_jobs() -> list:
        return mgr.list()

    def _job_or_404(job_id: str) -> dict:
        job = mgr.get(job_id)
        if not job:
            raise HTTPException(404, "Job tidak ditemukan")
        return job

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str) -> dict:
        return _public(_job_or_404(job_id))

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str) -> FileResponse:
        job = _job_or_404(job_id)
        path = mgr.file_path(job_id)
        if not path:
            raise HTTPException(409, "Berkas belum tersedia")
        return FileResponse(
            path,
            filename=f"makalah-{_slug(job['title'])}.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str) -> dict:
        if not ID_RE.match(job_id):
            raise HTTPException(404, "Job tidak ditemukan")
        result = mgr.delete(job_id)
        if result == "missing":
            raise HTTPException(404, "Job tidak ditemukan")
        if result == "running":
            raise HTTPException(409, "Job sedang berjalan dan tidak bisa dihentikan; tunggu sampai selesai.")
        return {"result": result}

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def main() -> None:
    import uvicorn

    host = os.getenv("MALAS_WEB_HOST", "127.0.0.1")
    port = int(os.getenv("MALAS_WEB_PORT", "8000"))
    allowed = None
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            "⚠️  Server dibuka ke jaringan tanpa autentikasi: siapa pun yang bisa mengakses akan memakai "
            "kuota API Anda. Gunakan hanya di jaringan tepercaya.",
        )
        allowed = ["*"]
    print(f"MALAS web UI -> http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}")
    uvicorn.run(create_app(allowed_hosts=allowed), host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()

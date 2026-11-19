"""Web UI MALAS: FastAPI + halaman statis (tanpa build step).

Jalankan:  uv run malas-web      (default http://127.0.0.1:8000)

Dua mode:
  lokal (default)   boleh memakai API key dari .env server, atau key milik pengguna.
  hosting           MALAS_WEB_REQUIRE_KEY=1: setiap pengguna WAJIB membawa API key sendiri (BYOK);
                    key server tidak pernah dipakai, riwayat dihapus otomatis, stdout dibungkam.

Env: MALAS_WEB_HOST, MALAS_WEB_PORT, MALAS_OUTPUT_DIR, MALAS_WEB_ALLOWED_HOSTS (koma; boleh "*.onrender.com"),
     MALAS_WEB_REQUIRE_KEY, MALAS_WEB_RETENTION_HOURS (default 6 di mode hosting), MALAS_WEB_MAX_QUEUE.
"""
import hashlib
import os
import re
import secrets
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr, StringConstraints, field_validator
from pydantic_core import PydanticCustomError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from malas import config, paths
from malas.docx_converter import xml_safe
from malas.providers import PROVIDERS, get_provider, public_info
from malas.steps import STEPS
from malas_api.crypto import cipher_from_env
from malas_api.db import database_url_from_env, migrate_url_from_env
from malas_api.jobs import ID_RE, JobManager

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATE_DIR = paths.TEMPLATES_DIR
DEFAULT_TEMPLATE_NAME = paths.DEFAULT_TEMPLATE_NAME
LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
COOKIE = "malas_sid"
SID_RE = re.compile(r"^[A-Za-z0-9_\-]{30,80}$")
KEY_RE = re.compile(r"^[\x21-\x7e]{8,300}$")  # ASCII tercetak, tanpa spasi/kontrol
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,99}$")
MAX_BODY = 100_000

Str = lambda mx, mn=0: Annotated[str, StringConstraints(strip_whitespace=True, min_length=mn, max_length=mx)]  # noqa: E731


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


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
    # BYOK: key hanya dipakai untuk job ini. SecretStr agar tidak tercetak/ter-dump tanpa sengaja.
    provider: str = "openrouter"
    api_key: Optional[SecretStr] = None
    model_planner: Optional[str] = None
    model_writer: Optional[str] = None
    resume_from: Optional[str] = None  # id job gagal milik sendiri yang ingin dilanjutkan
    # Opsi 3b: simpan key terenkripsi di server (butuh MALAS_SECRET_KEY) agar job terputus bisa lanjut otomatis.
    save_key: bool = False  # api_key dikirim DAN disimpan
    use_saved_key: bool = False  # api_key kosong; pakai key tersimpan untuk `provider`

    @field_validator("resume_from", mode="before")
    @classmethod
    def _cek_resume(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str) or not ID_RE.match(v.strip()):
            raise PydanticCustomError("resume_format", "Id job tidak valid.")
        return v.strip()

    @field_validator("api_key", mode="before")
    @classmethod
    def _cek_key(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str) or not KEY_RE.match(v.strip()):
            raise PydanticCustomError("key_format", "Format API key tidak valid (8–300 karakter, tanpa spasi).")
        return v.strip()

    @field_validator("model_planner", "model_writer", mode="before")
    @classmethod
    def _cek_model(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if not isinstance(v, str) or not MODEL_RE.match(v.strip()):
            raise PydanticCustomError("model_format", "Id model tidak valid.")
        return v.strip()

    @field_validator("*", mode="after")
    @classmethod
    def _bersihkan(cls, v):
        return xml_safe(v) if isinstance(v, str) else v


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "makalah"


def _public(job: dict) -> dict:
    """Bentuk job untuk klien: tanpa path internal dan tanpa penanda pemilik."""
    return {k: v for k, v in job.items() if k not in {"template_path", "owner"}}


def create_app(manager: Optional[JobManager] = None, allowed_hosts: Optional[List[str]] = None,
               hosted: Optional[bool] = None) -> FastAPI:
    hosted = _flag("MALAS_WEB_REQUIRE_KEY") if hosted is None else hosted
    if manager is None:
        retention = os.getenv("MALAS_WEB_RETENTION_HOURS")
        manager = JobManager(
            Path(os.getenv("MALAS_OUTPUT_DIR", "output")),
            retention_hours=float(retention) if retention else (6.0 if hosted else None),
            quiet=hosted,
            database_url=database_url_from_env(),
            migrate_url=migrate_url_from_env(),
            cipher=cipher_from_env(),
        )
    mgr = manager
    max_queue = int(os.getenv("MALAS_WEB_MAX_QUEUE", "5"))

    app = FastAPI(title="MALAS", docs_url=None, redoc_url=None, openapi_url=None)
    extra = [h.strip() for h in os.getenv("MALAS_WEB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or (LOCAL_HOSTS + extra))
    app.state.manager = mgr

    # ---- sesi anonim: cookie acak -> pemilik job (tanpa login, tapi riwayat tidak bocor antar pengguna)
    @app.middleware("http")
    async def session_and_headers(request: Request, call_next):
        if request.url.path == "/healthz":  # health check platform: tanpa cookie, tanpa pemeriksaan Host
            return PlainTextResponse("ok", headers={"Cache-Control": "no-store"})
        sid = request.cookies.get(COOKIE)
        fresh = not (sid and SID_RE.match(sid))
        if fresh:
            sid = secrets.token_urlsafe(32)
        request.state.owner = hashlib.sha256(sid.encode()).hexdigest()

        if request.method == "POST" and int(request.headers.get("content-length") or 0) > MAX_BODY:
            return JSONResponse({"detail": "Permintaan terlalu besar."}, status_code=413)

        resp: Response = await call_next(request)
        path = request.url.path
        if fresh and (path == "/" or path.startswith("/api/")):
            https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
            resp.set_cookie(COOKIE, sid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax", secure=https, path="/")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        if path.startswith("/api/") or path == "/":
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def _own_job(job_id: str, request: Request) -> dict:
        job = mgr.get(job_id)
        if not job or job.get("owner") != request.state.owner:
            raise HTTPException(404, "Job tidak ditemukan")  # 404, bukan 403: tidak membocorkan keberadaan
        return job

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Jangan pernah memantulkan 'input' (bisa berisi API key) kembali ke klien.
        errors = []
        for e in exc.errors():
            ctx = {k: v for k, v in (e.get("ctx") or {}).items() if isinstance(v, (int, float, str))}
            errors.append({"loc": list(e["loc"]), "type": e["type"], "msg": e["msg"], **({"ctx": ctx} if ctx else {})})
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/api/config")
    def get_config(request: Request) -> dict:
        desc = config.describe()
        return {
            "hosted": hosted,
            "server_key_available": (not hosted) and desc["api_key_ok"],
            "models": None if hosted else desc["models"],  # mode hosting: konfigurasi server tidak relevan
            "api_key_ok": False if hosted else desc["api_key_ok"],
            "mock_default": False if hosted else desc["mock_default"],
            "fulltext": desc["fulltext"],
            "providers": public_info(),
            "templates": list_templates(),
            "default_template": DEFAULT_TEMPLATE_NAME,
            "steps": [{"key": k, "label": l, "hint": h} for k, l, h in STEPS],
            "active_job": mgr.active_job(request.state.owner),
            "key_storage": mgr.key_storage_enabled,
            "year": datetime.now().year,
        }

    @app.post("/api/jobs", status_code=202)
    def create_job(req: JobRequest, request: Request) -> dict:
        owner = request.state.owner
        templates = list_templates()
        resume_job = None
        if req.resume_from:
            resume_job = _own_job(req.resume_from, request)  # 404 bila bukan milik pengguna ini
            if resume_job["status"] not in {"error", "interrupted"} or not (resume_job.get("resume") or {}).get("available"):
                raise HTTPException(409, "Job ini tidak bisa dilanjutkan (tidak ada hasil tersimpan atau sudah selesai).")
            req.template = req.template or resume_job.get("template")
        name = req.template or (DEFAULT_TEMPLATE_NAME if DEFAULT_TEMPLATE_NAME in templates else (templates[0] if templates else ""))
        if name not in templates:  # cegah path traversal: hanya nama dari daftar
            raise HTTPException(422, detail=[{"loc": ["body", "template"], "type": "value_error", "msg": "Template tidak tersedia"}])

        runtime = None
        key_source = provider_id = models = None
        if not req.mock:
            if req.api_key is not None or req.use_saved_key:
                prov = get_provider(req.provider)
                if prov is None or not prov.enabled:
                    raise HTTPException(422, detail=[{"loc": ["body", "provider"], "type": "value_error", "msg": "Penyedia tidak tersedia"}])
                planner = req.model_planner or prov.default_planner
                writer = req.model_writer or prov.default_writer
                for field, val in (("model_planner", planner), ("model_writer", writer)):
                    if not val:
                        raise HTTPException(422, detail=[{"loc": ["body", field], "type": "missing", "msg": "Model wajib diisi"}])
                provider_id, models = prov.id, {"planner": planner, "writer": writer}
                if req.api_key is not None and not req.save_key:
                    runtime = config.Runtime(prov.id, req.api_key.get_secret_value(), planner, writer)
                else:  # key tersimpan (terenkripsi) dipakai job
                    if not mgr.key_storage_enabled:
                        raise HTTPException(409, "Penyimpanan API key tidak aktif di server ini.")
                    if req.api_key is not None:
                        mgr.save_user_key(owner, prov.id, req.api_key.get_secret_value())
                    elif not mgr.has_user_key(owner, prov.id):
                        raise HTTPException(422, detail=[{"loc": ["body", "api_key"], "type": "missing", "msg": "Belum ada API key tersimpan untuk penyedia ini"}])
                    key_source = "saved"
            elif hosted:
                raise HTTPException(422, detail=[{"loc": ["body", "api_key"], "type": "missing", "msg": "API key wajib diisi"}])
            elif not config.describe()["api_key_ok"]:
                raise HTTPException(400, detail="API key server belum terdeteksi. Isi .env (lihat README), masukkan API key Anda, atau pakai Mode uji.")

        if hosted:  # cegah satu pengguna/bot memenuhi antrean bersama
            if mgr.active_job(owner):
                raise HTTPException(429, "Anda masih punya makalah yang sedang diproses. Tunggu sampai selesai.")
            if mgr.count_active() >= max_queue:
                raise HTTPException(429, "Antrean penuh. Coba lagi beberapa menit lagi.")

        data = req.model_dump(exclude={"template", "mock", "provider", "api_key", "model_planner", "model_writer", "resume_from",
                                          "save_key", "use_saved_key"})
        if resume_job:  # data makalah harus sama dengan job asal agar checkpoint (outline/referensi) tetap cocok
            data = resume_job["request"]
        try:
            job = mgr.submit(data, req.mock, str(TEMPLATE_DIR / name), name, owner=owner, runtime=runtime,
                             resume_from=resume_job["id"] if resume_job else None,
                             key_source=key_source, provider=provider_id, models=models)
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        return _public(job)

    @app.get("/api/jobs")
    def list_jobs(request: Request) -> list:
        return mgr.list(request.state.owner)

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str, request: Request) -> dict:
        return _public(_own_job(job_id, request))

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str, request: Request) -> Response:
        job = _own_job(job_id, request)
        content = mgr.read_file(job_id)
        if content is None:
            raise HTTPException(409, "Berkas belum tersedia")
        return Response(
            content,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="makalah-{_slug(job["title"])}.docx"'},
        )

    @app.delete("/api/jobs/{job_id}")
    def delete_job(job_id: str, request: Request) -> dict:
        if not ID_RE.match(job_id):
            raise HTTPException(404, "Job tidak ditemukan")
        _own_job(job_id, request)
        result = mgr.delete(job_id)
        if result == "missing":
            raise HTTPException(404, "Job tidak ditemukan")
        if result == "running":
            raise HTTPException(409, "Job sedang berjalan dan tidak bisa dihentikan; tunggu sampai selesai.")
        return {"result": result}

    # ---- API key tersimpan (opsi 3b): hanya daftar penyedia; nilai key TIDAK PERNAH dikembalikan
    @app.get("/api/keys")
    def list_keys(request: Request) -> dict:
        return {"enabled": mgr.key_storage_enabled, "keys": mgr.list_user_keys(request.state.owner)}

    @app.delete("/api/keys/{provider}")
    def delete_key(provider: str, request: Request) -> dict:
        if get_provider(provider) is None or not mgr.delete_user_key(request.state.owner, provider):
            raise HTTPException(404, "Key tersimpan tidak ditemukan")
        return {"result": "deleted"}

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def server_allowed_hosts(host: str, env=os.environ) -> Optional[List[str]]:
    """Daftar Host yang diterima saat server dibuka ke jaringan (None = bawaan lokal).

    Urutan: MALAS_WEB_ALLOWED_HOSTS (koma) + RENDER_EXTERNAL_HOSTNAME (diisi otomatis oleh Render).
    Tanpa keduanya -> "*" (server publik tanpa cookie/otoritas login, jadi pemeriksaan Host
    tidak melindungi apa pun; yang penting health check platform tetap lolos).
    """
    if host in {"127.0.0.1", "localhost", "::1"}:
        return None
    names = [h.strip() for h in env.get("MALAS_WEB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    render = env.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render:
        names.append(render)
    return (names + LOCAL_HOSTS) if names else ["*"]


def main() -> None:
    import uvicorn

    host = os.getenv("MALAS_WEB_HOST", "127.0.0.1")
    # PORT: diisi otomatis oleh Render/Heroku-style platform; MALAS_WEB_PORT menimpa.
    port = int(os.getenv("MALAS_WEB_PORT") or os.getenv("PORT") or "8000")
    allowed = server_allowed_hosts(host)
    if allowed is not None and not _flag("MALAS_WEB_REQUIRE_KEY"):
        print(
            "⚠️  Server dibuka ke jaringan TANPA mode BYOK: pengguna akan memakai API key di .env server. "
            "Set MALAS_WEB_REQUIRE_KEY=1 agar setiap pengguna memakai key sendiri.",
        )
    print(f"MALAS web UI -> http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
          f"{' (mode hosting/BYOK)' if _flag('MALAS_WEB_REQUIRE_KEY') else ''}")
    # proxy_headers: di balik proxy HTTPS (Render, dsb.) agar skema https terdeteksi untuk cookie Secure.
    uvicorn.run(create_app(allowed_hosts=allowed), host=host, port=port, log_level="warning",
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()

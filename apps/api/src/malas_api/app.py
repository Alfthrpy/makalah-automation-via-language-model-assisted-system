"""API web MALAS: FastAPI (UI ada di apps/web, dilayani terpisah).

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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field, SecretStr, StringConstraints, field_validator
from pydantic_core import PydanticCustomError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from malas import config, paths
from malas.logo import LogoError, normalize_logo
from malas.docx_converter import xml_safe
from malas.providers import PROVIDERS, get_provider, public_info
from malas.steps import STEPS
from malas_api.auth import Authenticator, AuthError, authenticator_from_env, token_from_request
from malas_api.crypto import cipher_from_env
from malas_api.db import database_url_from_env, migrate_url_from_env
from malas_api.jobs import ID_RE, JobManager
from malas_api.schemas import ConfigOut, JobOut, JobSummary, KeysOut, LogoOut, MeOut, ResultOut
from malas_api.storage import storage_from_env

TEMPLATE_DIR = paths.TEMPLATES_DIR
DEFAULT_TEMPLATE_NAME = paths.DEFAULT_TEMPLATE_NAME
LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
COOKIE = "malas_sid"
SID_RE = re.compile(r"^[A-Za-z0-9_\-]{30,80}$")
KEY_RE = re.compile(r"^[\x21-\x7e]{8,300}$")  # ASCII tercetak, tanpa spasi/kontrol
MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,99}$")
MAX_BODY = 100_000
MAX_LOGO_UPLOAD = 300_000  # sama dengan malas.logo.MAX_INPUT_BYTES
DEFAULT_RETENTION_HOURS = 48.0  # riwayat/berkas dihapus N jam setelah selesai (mode hosting); ubah di teks hukum juga
PUBLIC_API = {"/api/config"}  # boleh diakses tanpa login (UI perlu tahu mode auth)

Str = lambda mx, mn=0: Annotated[str, StringConstraints(strip_whitespace=True, min_length=mn, max_length=mx)]  # noqa: E731


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def retention_from_env(hosted: bool, env=os.environ) -> Optional[float]:
    """Jam penyimpanan riwayat setelah job selesai. MALAS_WEB_RETENTION_HOURS menimpa; mode hosting default 48 jam;
    lokal tanpa batas. Angka ini juga tertulis di Ketentuan/Privasi (web) dan ditampilkan lewat /api/config."""
    raw = (env.get("MALAS_WEB_RETENTION_HOURS") or "").strip()
    if raw:
        return float(raw)
    return DEFAULT_RETENTION_HOURS if hosted else None


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
    use_logo: bool = False  # pakai logo kampus/sekolah tersimpan (PUT /api/logo) di sampul

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


def quota_tz():
    from zoneinfo import ZoneInfo

    return ZoneInfo(os.getenv("MALAS_QUOTA_TZ", "Asia/Jakarta"))


def quota_day() -> str:
    return datetime.now(quota_tz()).strftime("%Y-%m-%d")


def quota_resets_at() -> str:
    now = datetime.now(quota_tz())
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return nxt.isoformat(timespec="seconds")


def create_app(manager: Optional[JobManager] = None, allowed_hosts: Optional[List[str]] = None,
               hosted: Optional[bool] = None, auth: Optional[Authenticator] = None,
               daily_quota: Optional[int] = None) -> FastAPI:
    """auth: verifikator Clerk. None = ambil dari env (CLERK_*); bila tetap kosong -> mode anonim (cookie acak).
    daily_quota: maks job NYATA (bukan Mode uji, bukan lanjutan) per pengguna per hari; 0/None = tanpa batas
    (default dari MALAS_DAILY_QUOTA)."""
    hosted = _flag("MALAS_WEB_REQUIRE_KEY") if hosted is None else hosted
    auth = authenticator_from_env() if auth is None else auth
    if daily_quota is None:
        daily_quota = int(os.getenv("MALAS_DAILY_QUOTA", "0") or 0)
    if _flag("MALAS_AUTH_REQUIRED") and auth is None:
        raise RuntimeError("MALAS_AUTH_REQUIRED=1 tetapi CLERK_ISSUER/CLERK_JWKS_URL belum diisi.")
    if manager is None:
        manager = JobManager(
            Path(os.getenv("MALAS_OUTPUT_DIR", "output")),
            retention_hours=retention_from_env(hosted),
            quiet=hosted,
            database_url=database_url_from_env(),
            migrate_url=migrate_url_from_env(),
            cipher=cipher_from_env(),
            storage=storage_from_env(),  # R2 bila R2_* diisi, selain itu bytea di database
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
        fresh = False
        if auth is not None:  # Clerk: pemilik = `sub` JWT; tanpa token sah, hanya jalur publik
            token = token_from_request(request.headers, request.cookies, request.method)
            owner = None
            if token:
                try:
                    owner = await run_in_threadpool(auth.verify, token)  # bisa mengunduh JWKS (I/O)
                except AuthError:
                    owner = None
            request.state.owner = owner
            path0 = request.url.path
            if owner is None and path0.startswith("/api/") and path0 not in PUBLIC_API:
                return JSONResponse({"detail": "Silakan masuk terlebih dahulu."}, status_code=401,
                                    headers={"Cache-Control": "no-store", "WWW-Authenticate": "Bearer"})
        else:  # anonim: cookie acak -> pemilik (riwayat tidak bocor antar browser)
            sid = request.cookies.get(COOKIE)
            fresh = not (sid and SID_RE.match(sid))
            if fresh:
                sid = secrets.token_urlsafe(32)
            request.state.owner = hashlib.sha256(sid.encode()).hexdigest()

        if request.method == "POST" and int(request.headers.get("content-length") or 0) > MAX_BODY:
            return JSONResponse({"detail": "Permintaan terlalu besar."}, status_code=413)

        resp: Response = await call_next(request)
        path = request.url.path
        if fresh and auth is None and path.startswith("/api/"):
            https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
            resp.set_cookie(COOKIE, sid, max_age=60 * 60 * 24 * 365, httponly=True, samesite="lax", secure=https, path="/")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        if path.startswith("/api/"):
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

    @app.get("/api/config", response_model=ConfigOut)
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
            "active_job": mgr.active_job(request.state.owner) if request.state.owner else None,
            "auth": {"mode": "clerk" if auth else "anonymous", "required": auth is not None},
            "daily_quota": daily_quota or None,
            "key_storage": mgr.key_storage_enabled,
            "retention_hours": mgr.retention_hours,
            "year": datetime.now().year,
        }

    @app.post("/api/jobs", status_code=202, response_model=JobOut)
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

        if req.use_logo and not mgr.logo_info(owner):  # (ringan; satu baris tabel)
            raise HTTPException(422, detail=[{"loc": ["body", "use_logo"], "type": "missing", "msg": "Belum ada logo tersimpan"}])

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

        consumed_day = None
        if daily_quota and not req.mock and not resume_job:  # lanjutan & Mode uji tidak memakai kuota
            consumed_day = quota_day()
            if not mgr.consume_quota(owner, consumed_day, daily_quota):
                raise HTTPException(429, f"Kuota harian ({daily_quota} makalah) habis. Coba lagi besok.")

        data = req.model_dump(exclude={"template", "mock", "provider", "api_key", "model_planner", "model_writer", "resume_from",
                                          "save_key", "use_saved_key", "use_logo"})
        if resume_job:  # data makalah harus sama dengan job asal agar checkpoint (outline/referensi) tetap cocok
            data = resume_job["request"]
        try:
            job = mgr.submit(data, req.mock, str(TEMPLATE_DIR / name), name, owner=owner, runtime=runtime,
                             resume_from=resume_job["id"] if resume_job else None,
                             key_source=key_source, provider=provider_id, models=models, quota_day=consumed_day,
                             use_logo=req.use_logo)
        except Exception as e:
            if consumed_day:
                mgr.refund_quota(owner, consumed_day)  # job tidak terbentuk: kuota dikembalikan
            if isinstance(e, ValueError):
                raise HTTPException(409, str(e)) from e
            raise
        return _public(job)

    @app.get("/api/jobs", response_model=List[JobSummary])
    def list_jobs(request: Request) -> list:
        return mgr.list(request.state.owner)

    @app.get("/api/jobs/{job_id}", response_model=JobOut)
    def get_job(job_id: str, request: Request) -> dict:
        job = _public(_own_job(job_id, request))
        job["queue_position"] = mgr.queue_position(job_id) if job["status"] == "queued" else None
        return job

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

    @app.delete("/api/jobs/{job_id}", response_model=ResultOut)
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

    @app.get("/api/me", response_model=MeOut)
    def me(request: Request) -> dict:
        owner = request.state.owner
        used = mgr.quota_used(owner, quota_day()) if daily_quota else 0
        logo = mgr.logo_info(owner)
        return {
            "logo": {"size": logo["size"], "updated_at": logo["updated_at"]} if logo else None,
            "id": owner if auth else None,  # id Clerk (bukan rahasia); anonim: tidak ditampilkan
            "mode": "clerk" if auth else "anonymous",
            "quota": ({"limit": daily_quota, "used": used, "remaining": max(daily_quota - used, 0),
                       "resets_at": quota_resets_at()} if daily_quota else None),
        }

    # ---- logo kampus/sekolah (satu per pengguna). Unggahan mentah (image/png|jpeg) divalidasi dan dikodekan ulang oleh
    # malas.logo; yang tersimpan hanya PNG bersih. Tidak pernah dikirim ke penyedia LLM.
    @app.put("/api/logo", response_model=LogoOut)
    async def put_logo(request: Request) -> dict:
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_LOGO_UPLOAD:
            raise HTTPException(413, "Ukuran logo maksimal 300 KB.")
        buf = bytearray()
        async for chunk in request.stream():
            buf += chunk
            if len(buf) > MAX_LOGO_UPLOAD:
                raise HTTPException(413, "Ukuran logo maksimal 300 KB.")
        try:
            png = await run_in_threadpool(normalize_logo, bytes(buf))
        except LogoError as e:
            raise HTTPException(422, str(e)) from e
        await run_in_threadpool(mgr.save_logo, request.state.owner, png)
        info = mgr.logo_info(request.state.owner)
        return {"size": info["size"], "updated_at": info["updated_at"]}

    @app.get("/api/logo", response_class=Response, responses={200: {"content": {"image/png": {}}}, 404: {"description": "Belum ada logo"}})
    def get_logo(request: Request) -> Response:
        png = mgr.get_logo(request.state.owner)
        if png is None:
            raise HTTPException(404, "Belum ada logo tersimpan")
        return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.delete("/api/logo", response_model=ResultOut)
    def delete_logo(request: Request) -> dict:
        if not mgr.delete_logo(request.state.owner):
            raise HTTPException(404, "Belum ada logo tersimpan")
        return {"result": "deleted"}

    # ---- API key tersimpan (opsi 3b): hanya daftar penyedia; nilai key TIDAK PERNAH dikembalikan
    @app.get("/api/keys", response_model=KeysOut)
    def list_keys(request: Request) -> dict:
        return {"enabled": mgr.key_storage_enabled, "keys": mgr.list_user_keys(request.state.owner)}

    @app.delete("/api/keys/{provider}", response_model=ResultOut)
    def delete_key(provider: str, request: Request) -> dict:
        if get_provider(provider) is None or not mgr.delete_user_key(request.state.owner, provider):
            raise HTTPException(404, "Key tersimpan tidak ditemukan")
        return {"result": "deleted"}

    return app


def server_allowed_hosts(host: str, env=os.environ) -> Optional[List[str]]:
    """Daftar Host yang diterima saat server dibuka ke jaringan (None = bawaan lokal).

    Urutan: MALAS_WEB_ALLOWED_HOSTS (koma) + RENDER_EXTERNAL_HOSTNAME / SPACE_HOST (diisi otomatis oleh Render / HF Spaces).
    Tanpa keduanya -> "*" (server publik tanpa cookie/otoritas login, jadi pemeriksaan Host
    tidak melindungi apa pun; yang penting health check platform tetap lolos).
    """
    if host in {"127.0.0.1", "localhost", "::1"}:
        return None
    names = [h.strip() for h in env.get("MALAS_WEB_ALLOWED_HOSTS", "").split(",") if h.strip()]
    for var in ("RENDER_EXTERNAL_HOSTNAME", "SPACE_HOST"):  # diisi otomatis oleh Render / Hugging Face Spaces
        host_ = env.get(var, "").strip()
        if host_:
            names.append(host_)
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
    clerk = bool(os.getenv("CLERK_ISSUER") or os.getenv("CLERK_JWKS_URL"))
    if allowed is not None and not clerk:
        print("⚠️  Server dibuka ke jaringan TANPA login (CLERK_ISSUER/CLERK_JWKS_URL kosong): pengguna dibedakan hanya oleh cookie acak.")
    print(f"MALAS web UI -> http://{host if host != '0.0.0.0' else '127.0.0.1'}:{port}"
          f"{' (mode hosting/BYOK)' if _flag('MALAS_WEB_REQUIRE_KEY') else ''}{' (login Clerk)' if clerk else ''}")
    # proxy_headers: di balik proxy HTTPS (Render, dsb.) agar skema https terdeteksi untuk cookie Secure.
    uvicorn.run(create_app(allowed_hosts=allowed), host=host, port=port, log_level="warning",
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()

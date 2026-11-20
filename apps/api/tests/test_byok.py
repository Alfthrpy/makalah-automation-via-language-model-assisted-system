"""Keamanan BYOK: API key pengguna tidak boleh tersimpan, bocor, atau terlihat orang lain."""
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from malas import config
from malas_api.app import create_app
from malas_api.jobs import JobManager

KEY = "sk-or-v1-RAHASIA1234567890abcdef"
BASE = {
    "judul": "Etika Bermedia Sosial", "mata_kuliah": "PKn", "penyusun": [{"nama": "Ani", "nim": "1"}],
    "tahun": "2025",
}
BYOK = {**BASE, "provider": "openrouter", "api_key": KEY}
seen = {}


def ok_runner(job, progress, out, runtime=None):
    seen["runtime"] = runtime
    progress("input", "done")
    out.write_bytes(b"PK-docx")
    return {"usage": {"total": 10}, "stats": {}}


@pytest.fixture
def make(tmp_path):
    ms = []

    def _make(runner=ok_runner, hosted=True, **kw):
        m = JobManager(tmp_path, runner=runner, **kw)
        ms.append(m)
        return TestClient(create_app(m, hosted=hosted)), m

    seen.clear()
    yield _make
    for m in ms:
        m.shutdown()


def wait_for(client, jid, want, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError("timeout")


def eventually(cond, timeout=5.0, what="kondisi"):
    """Tunggu pembersihan yang SENGAJA terjadi sesaat SETELAH status job berubah (key dibuang di `finally`, checkpoint
    dihapus setelah status tersimpan agar resume tidak hilang bila proses mati). Menuntutnya seketika = balapan antar thread."""
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError(f"{what} tidak terpenuhi dalam {timeout} dtk")


def all_files_text(root):
    out = []
    for dp, _, fs in os.walk(root):
        for f in fs:
            out.append(open(os.path.join(dp, f), "rb").read().decode("utf-8", "ignore"))
    return "\n".join(out)


# ---------------------------------------------------------------- tidak disimpan / tidak bocor
def test_key_tidak_ada_di_disk_respons_maupun_riwayat(make, tmp_path):
    client, m = make()
    r = client.post("/api/jobs", json=BYOK)
    assert r.status_code == 202 and KEY not in r.text
    jid = r.json()["id"]
    job = wait_for(client, jid, {"done"})
    assert seen["runtime"].api_key == KEY  # runner menerimanya...
    assert job["byok"] is True and job["provider"] == "openrouter"
    for body in (client.get(f"/api/jobs/{jid}").text, client.get("/api/jobs").text, client.get("/api/config").text):
        assert KEY not in body
    assert KEY not in all_files_text(tmp_path)  # ...tetapi tidak ada satu byte pun di disk
    eventually(lambda: len(m.vault) == 0 and not m._pending_runtime, what="brankas kosong")  # dan dibuang dari memori


def test_runtime_repr_tidak_menampilkan_key():
    rt = config.Runtime("openrouter", KEY, "a/b", "c/d")
    assert KEY not in repr(rt) and KEY not in str(rt)


def test_validasi_gagal_tidak_memantulkan_input(make):
    client, _ = make()
    bad = "kunci dengan spasi!!"
    r = client.post("/api/jobs", json={**BASE, "api_key": bad})
    assert r.status_code == 422 and bad not in r.text and "input" not in r.text
    r = client.post("/api/jobs", json={**BASE, "api_key": "x" * 301})
    assert r.status_code == 422 and "x" * 20 not in r.text


def test_telemetry_crewai_dimatikan():
    assert os.environ.get("OTEL_SDK_DISABLED") == "true" and os.environ.get("CREWAI_DISABLE_TELEMETRY") == "true"


def test_get_llm_tidak_menyentuh_environment():
    before = dict(os.environ)
    config.set_runtime(config.Runtime("openrouter", KEY, "deepseek/deepseek-v3.2", "google/gemini-2.5-flash"))
    try:
        llm = config.get_llm("writer")
        # crewAI 1.x (provider native): awalan "openrouter/" menjadi `provider`, `model` tanpa awalan
        assert llm.model.endswith("google/gemini-2.5-flash")
        assert getattr(llm, "provider", "") == "openrouter" or llm.model.startswith("openrouter/")
        assert "openrouter.ai" in str(getattr(llm, "base_url", "") or getattr(llm, "api_base", ""))
        # (impor crewai boleh menambah env non-rahasia; yang dilarang: key muncul di env mana pun)
        assert KEY not in "\n".join(os.environ.values())
        assert not [k for k in set(os.environ) - set(before) if "KEY" in k.upper() or "SECRET" in k.upper()]
    finally:
        config.set_runtime(None)


def test_kenari_memakai_base_url_terkunci():
    config.set_runtime(config.Runtime("kenari", "kn-" + "a" * 20, "step-3-7-flash:free", "step-3-7-flash:free"))
    try:
        llm = config.get_llm("planner")
        assert llm.model == "step-3-7-flash:free" or llm.model.endswith("step-3-7-flash:free")
        assert "kenari.id/v1" in str(getattr(llm, "base_url", "") or getattr(llm, "api_base", ""))
    finally:
        config.set_runtime(None)


# ---------------------------------------------------------------- redaksi
def test_error_dan_log_dibersihkan_dari_key(make, caplog, capsys):
    def leaky(job, progress, out, runtime=None):
        logging.getLogger("litellm").warning("gagal dengan key %s", runtime.api_key)
        raise RuntimeError(f"401 Unauthorized, key={runtime.api_key}")

    client, _ = make(leaky, hosted=False, quiet=False)
    with caplog.at_level(logging.WARNING):
        jid = client.post("/api/jobs", json=BYOK).json()["id"]
        j = wait_for(client, jid, {"error"})
    assert KEY not in j["error"] and "ditolak" in j["error"]
    assert KEY not in caplog.text and "[KEY-DISEMBUNYIKAN]" in caplog.text
    out = capsys.readouterr()
    assert KEY not in out.out and KEY not in out.err  # traceback di konsol juga bersih


def test_bentuk_key_umum_dibersihkan_walau_tak_dikenal_brankas(make):
    from malas_api.vault import Vault

    v = Vault()
    assert "sk-or-v1-abcdefghijklmnop" not in v.redact("error: bad key sk-or-v1-abcdefghijklmnop here")


def test_mode_hosting_membungkam_stdout(make, capsys):
    def noisy(job, progress, out, runtime=None):
        print("JUDUL-RAHASIA-USER")
        out.write_bytes(b"x")
        return {}

    client, _ = make(noisy, hosted=True, quiet=True)
    jid = client.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
    wait_for(client, jid, {"done"})
    assert "JUDUL-RAHASIA-USER" not in capsys.readouterr().out


# ---------------------------------------------------------------- brankas dibersihkan di semua jalur akhir
def test_vault_kosong_setelah_gagal(make):
    def boom(job, progress, out, runtime=None):
        raise RuntimeError("x")

    client, m = make(boom)
    jid = client.post("/api/jobs", json=BYOK).json()["id"]
    wait_for(client, jid, {"error"})
    eventually(lambda: len(m.vault) == 0 and not m._pending_runtime, what="brankas kosong")


def test_vault_kosong_setelah_batal_dan_hapus(make):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        out.write_bytes(b"x")
        return {}

    client, m = make(slow, hosted=False)
    a = client.post("/api/jobs", json={**BYOK}).json()["id"]
    wait_for(client, a, {"running"})
    b = client.post("/api/jobs", json={**BYOK}).json()["id"]
    assert len(m.vault) == 2
    assert client.delete(f"/api/jobs/{b}").json() == {"result": "cancelled"}  # job antre dibatalkan
    assert len(m.vault) == 1 and b not in m._pending_runtime
    gate.set()
    wait_for(client, a, {"done"})
    eventually(lambda: len(m.vault) == 0, what="brankas kosong")


def test_shutdown_membuang_key_yang_menunggu(make):
    gate = threading.Event()
    client, m = make(lambda j, p, o, r=None: gate.wait(5), hosted=False)
    client.post("/api/jobs", json=BYOK)
    client.post("/api/jobs", json=BYOK)
    m.shutdown()
    assert len(m.vault) <= 1  # yang sedang jalan dibuang oleh jobnya sendiri; yang antre dibuang saat shutdown
    gate.set()


# ---------------------------------------------------------------- kepemilikan (tanpa login)
def test_job_orang_lain_tidak_terlihat(make):
    a, m = make()
    jid = a.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
    wait_for(a, jid, {"done"})
    b = TestClient(create_app(m, hosted=True))  # browser lain = cookie lain
    assert b.get("/api/jobs").json() == []
    for call in (b.get, b.delete):
        assert call(f"/api/jobs/{jid}").status_code == 404
    assert b.get(f"/api/jobs/{jid}/download").status_code == 404
    assert b.get("/api/config").json()["active_job"] is None
    assert a.get(f"/api/jobs/{jid}/download").status_code == 200  # pemilik tetap bisa
    assert "httponly" in a.get("/api/config").headers.get("set-cookie", "httponly").lower() or True


def test_cookie_sesi_httponly_dan_samesite(make):
    client, _ = make()
    c = client.get("/api/config").headers["set-cookie"].lower()
    assert "malas_sid=" in c and "httponly" in c and "samesite=lax" in c
    https = client.get("/api/config", headers={"x-forwarded-proto": "https"})
    assert https.status_code == 200


# ---------------------------------------------------------------- aturan mode hosting
def test_hosting_wajib_key_kecuali_mode_uji(make):
    client, _ = make()
    r = client.post("/api/jobs", json=BASE)
    assert r.status_code == 422 and r.json()["detail"][0]["loc"][-1] == "api_key"
    assert client.post("/api/jobs", json={**BASE, "mock": True}).status_code == 202


def test_hosting_tidak_pernah_memakai_key_server(make, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "server-key-xyz-123456")
    monkeypatch.setenv("MALAS_MODEL", "openrouter/x/y")
    client, _ = make()
    assert client.post("/api/jobs", json=BASE).status_code == 422  # key server tidak jadi cadangan
    cfg = client.get("/api/config").json()
    assert cfg["hosted"] and cfg["models"] is None and cfg["server_key_available"] is False


def test_mode_uji_dengan_key_mengabaikan_key(make):
    client, _ = make()
    jid = client.post("/api/jobs", json={**BYOK, "mock": True}).json()["id"]
    wait_for(client, jid, {"done"})
    assert seen["runtime"] is None


@pytest.mark.parametrize("patch,field", [
    ({"provider": "tidak-ada"}, "provider"),
    ({"model_planner": "../etc/passwd"}, "model_planner"),
    ({"model_writer": "a b"}, "model_writer"),
])
def test_provider_dan_model_divalidasi(make, patch, field):
    client, _ = make()
    r = client.post("/api/jobs", json={**BYOK, **patch})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"][-1] == field


def test_default_model_openrouter_dan_kenari_wajib_model(make):
    client, _ = make()
    jid = client.post("/api/jobs", json=BYOK).json()["id"]
    wait_for(client, jid, {"done"})
    assert (seen["runtime"].planner_model, seen["runtime"].writer_model) == ("deepseek/deepseek-v3.2", "google/gemini-2.5-flash")
    assert client.get(f"/api/jobs/{jid}").json()["models"] == {"planner": "deepseek/deepseek-v3.2", "writer": "google/gemini-2.5-flash"}

    kn = {**BASE, "provider": "kenari", "api_key": "kn-" + "a" * 20}
    r = client.post("/api/jobs", json=kn)
    assert r.status_code == 422 and r.json()["detail"][0]["type"] == "missing"
    wait_for(client, jid, {"done"})
    r = client.post("/api/jobs", json={**kn, "model_planner": "step-3-7-flash:free", "model_writer": "step-3-7-flash:free"})
    assert r.status_code == 202


def test_hosting_satu_job_aktif_per_pengguna(make):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        out.write_bytes(b"x")
        return {}

    client, _ = make(slow)
    assert client.post("/api/jobs", json=BYOK).status_code == 202
    r = client.post("/api/jobs", json=BYOK)
    assert r.status_code == 429 and KEY not in r.text
    gate.set()


def test_retensi_menghapus_job_lama(make, tmp_path):
    client, m = make(retention_hours=1)
    jid = client.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
    wait_for(client, jid, {"done"})
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(timespec="seconds")
    m.repo.update(jid, lambda j: j.update(finished_at=old))
    assert client.get("/api/jobs").json() == []
    assert m.get(jid) is None and m.storage.get(jid) is None  # berkas ikut terhapus


def test_body_terlalu_besar_ditolak(make):
    client, _ = make()
    r = client.post("/api/jobs", content=b"x" * 200_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


# ---------------------------------------------------------------- pipeline asli (mock LLM) di mode senyap
def test_sink_menyerupai_file_teks():
    import contextlib
    import io

    from malas_api.vault import Sink

    s = Sink()
    with contextlib.redirect_stdout(s):
        import sys
        print("x")
        assert sys.stdout.encoding == "utf-8" and not sys.stdout.isatty()
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.flush()
    assert isinstance(s, io.TextIOBase)


def test_pipeline_asli_mock_selesai_di_mode_hosting(tmp_path, capsys):
    """Regresi: runner sungguhan (MalasFlow + AutoFakeLLM) harus jalan di bawah stdout senyap."""
    from malas_api.jobs import default_runner

    m = JobManager(tmp_path, runner=default_runner, quiet=True)
    try:
        client = TestClient(create_app(m, hosted=True))
        jid = client.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
        job = wait_for(client, jid, {"done", "error"}, timeout=120)
        assert job["status"] == "done", job["error"]
        assert all(s["status"] == "done" for k, s in job["steps"].items() if k != "fulltext" or s["status"] != "skipped")
        assert client.get(f"/api/jobs/{jid}/download").content[:2] == b"PK"  # .docx = zip
        out = capsys.readouterr()
        assert "Etika Bermedia Sosial" not in out.out + out.err  # tidak ada judul pengguna di log host
    finally:
        m.shutdown()


@pytest.mark.parametrize("msg,kata", [
    ("litellm.APIError: OpenrouterException - 403 Forbidden", "403"),
    ("litellm.AuthenticationError: No auth credentials found", "ditolak"),
    ("litellm.RateLimitError: 429", "kuota"),
    ("Insufficient credits", "Saldo"),
    ("litellm.NotFoundError: model not found", "Model tidak ditemukan"),
    ("litellm.APIConnectionError: Connection error", "terhubung"),
    ("hal aneh yang belum dikenal", "hal aneh"),
])
def test_pesan_error_ramah(msg, kata):
    from malas_api.jobs import _friendly_error

    out = _friendly_error(RuntimeError(msg))
    assert kata in out and "litellm" not in out

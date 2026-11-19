import threading
import time

import pytest
from fastapi.testclient import TestClient

from malas_api.app import create_app
from malas_api.jobs import JobManager

VALID = {
    "judul": "Sistem Rekomendasi & Machine Learning",
    "mata_kuliah": "Kecerdasan Buatan",
    "dosen_pengampu": "Dr. Budi",
    "penyusun": [{"nama": "Al-Fathir", "nim": "123"}],
    "kelas": "IF-4", "universitas": "Univ X", "fakultas": "FT", "jurusan": "TI", "kota": "Bandung", "tahun": "2025",
    "mock": True,
}


def fake_runner(job, progress, out, runtime=None):
    progress("input", "running"); progress("input", "done")
    progress("tulis", "running"); progress("tulis", "info", "1/2 · 2.1 Teori"); progress("tulis", "done")
    out.write_bytes(b"PK-fake-docx")
    return {"usage": {"total": 1234}, "stats": {"refs_final": 3}}


def wait_for(client, job_id, want, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{job_id}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError(f"timeout; status terakhir={j['status']}")


@pytest.fixture
def make(tmp_path):
    managers = []

    def _make(runner=fake_runner, root=None):
        m = JobManager(root or tmp_path, runner=runner, stale_after=0)  # stale_after=0: restart dianggap langsung basi
        managers.append(m)
        return TestClient(create_app(m)), m

    yield _make
    for m in managers:
        m.shutdown()


def test_config(make):
    client, _ = make()
    c = client.get("/api/config").json()
    assert [s["key"] for s in c["steps"]][:2] == ["input", "outline"]
    assert "template makalah.docx" in c["templates"]
    assert not any(t.startswith("makalah_output") for t in c["templates"])
    assert set(c["models"]) == {"planner", "writer", "reviewer"}


def test_alur_job_selesai_dan_unduh(make):
    client, _ = make()
    r = client.post("/api/jobs", json=VALID)
    assert r.status_code == 202
    jid = r.json()["id"]
    assert "template_path" not in r.json() and "owner" not in r.json()  # data internal tidak bocor
    job = wait_for(client, jid, {"done"})
    assert job["steps"]["input"]["status"] == "done"
    assert job["steps"]["tulis"]["detail"] == "1/2 · 2.1 Teori"
    assert job["usage"] == {"total": 1234} and job["has_file"]

    d = client.get(f"/api/jobs/{jid}/download")
    assert d.status_code == 200 and d.content == b"PK-fake-docx"
    assert "wordprocessingml" in d.headers["content-type"]
    assert "makalah-sistem-rekomendasi-machine-learning.docx" in d.headers["content-disposition"]


@pytest.mark.parametrize("patch", [
    {"judul": ""}, {"judul": "ab"}, {"penyusun": []}, {"tahun": "25"}, {"tahun": "abcd"},
    {"penyusun": [{"nama": ""}]}, {"penyusun": [{"nama": "x"}] * 11}, {"template": "../../etc/passwd"},
    {"template": "tidak-ada.docx"}, {"judul": "x" * 201},
])
def test_validasi_input(make, patch):
    client, m = make()
    r = client.post("/api/jobs", json={**VALID, **patch})
    assert r.status_code == 422
    assert m.list() == []  # tidak ada job terbentuk


def test_rejects_non_json_post(make):
    client, _ = make()
    r = client.post("/api/jobs", content="judul=x", headers={"content-type": "text/plain"})
    assert r.status_code == 422


def test_karakter_kontrol_dibuang(make):
    client, _ = make()
    r = client.post("/api/jobs", json={**VALID, "judul": "Judul\x00 Uji\x07"})
    assert r.json()["title"] == "Judul Uji"


def test_tanpa_api_key_ditolak_kecuali_mock(make, monkeypatch):
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("MALAS_MODEL", "gemini/gemini-2.5-flash")
    client, _ = make()
    r = client.post("/api/jobs", json={**VALID, "mock": False})
    assert r.status_code == 400 and "API key" in r.json()["detail"]
    assert client.post("/api/jobs", json=VALID).status_code == 202  # mode uji tetap boleh


def test_id_tidak_valid_dan_traversal(make):
    client, _ = make()
    for bad in ("zzz", "../../etc/passwd", "0" * 31, "A" * 32):
        assert client.get(f"/api/jobs/{bad}").status_code == 404
        assert client.get(f"/api/jobs/{bad}/download").status_code == 404
        assert client.delete(f"/api/jobs/{bad}").status_code == 404
    assert client.get("/api/jobs/" + "0" * 32).status_code == 404


def test_runner_gagal_menjadi_error_ramah(make):
    def boom(job, progress, out, runtime=None):
        progress("outline", "running")
        progress("outline", "error", "AuthenticationError")
        raise RuntimeError('litellm.AuthenticationError: {"error": {"code": 400, "message": "API key not valid"}}')

    client, _ = make(boom)
    jid = client.post("/api/jobs", json=VALID).json()["id"]
    j = wait_for(client, jid, {"error"})
    assert "API key" in j["error"] and "litellm" not in j["error"]  # detail mentah tidak bocor ke UI
    assert j["error_step"] == "outline" and not j["has_file"]
    assert client.get(f"/api/jobs/{jid}/download").status_code == 409


def test_antrean_batal_dan_hapus(make):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        return fake_runner(job, progress, out)

    client, _ = make(slow)
    a = client.post("/api/jobs", json=VALID).json()["id"]
    wait_for(client, a, {"running"})
    b = client.post("/api/jobs", json=VALID).json()["id"]
    assert client.get(f"/api/jobs/{b}").json()["status"] == "queued"
    assert client.get("/api/config").json()["active_job"] in {a, b}

    assert client.delete(f"/api/jobs/{a}").status_code == 409  # sedang berjalan
    assert client.delete(f"/api/jobs/{b}").json() == {"result": "cancelled"}
    assert client.get(f"/api/jobs/{b}").json()["status"] == "cancelled"

    gate.set()
    wait_for(client, a, {"done"})
    assert client.delete(f"/api/jobs/{a}").json() == {"result": "deleted"}
    assert client.get(f"/api/jobs/{a}").status_code == 404


def test_riwayat_selamat_dari_restart(make, tmp_path):
    client, m = make()
    jid = client.post("/api/jobs", json=VALID).json()["id"]
    wait_for(client, jid, {"done"})
    m.shutdown()

    client2, _ = make(root=tmp_path)
    client2.cookies.set("malas_sid", client.cookies.get("malas_sid"))  # browser yang sama
    assert [j["id"] for j in client2.get("/api/jobs").json()] == [jid]
    assert client2.get(f"/api/jobs/{jid}/download").content == b"PK-fake-docx"


def test_job_menggantung_ditandai_interrupted(make, tmp_path):
    gate = threading.Event()
    client, m = make(lambda j, p, o, r=None: gate.wait(5))
    jid = client.post("/api/jobs", json=VALID).json()["id"]
    wait_for(client, jid, {"running"})
    m.shutdown()  # simulasi server mati; job masih berstatus running di DB
    client2, _ = make(root=tmp_path)
    client2.cookies.set("malas_sid", client.cookies.get("malas_sid"))
    assert client2.get(f"/api/jobs/{jid}").json()["status"] == "interrupted"
    gate.set()


def test_host_asing_ditolak_dan_header_keamanan(make):
    client, _ = make()
    assert client.get("/api/config", headers={"host": "evil.example"}).status_code == 400
    r = client.get("/api/config")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_healthz_lolos_dengan_host_apa_pun_dan_tanpa_cookie(make):
    client, _ = make()
    r = client.get("/healthz", headers={"host": "10.0.0.7:10000"})
    assert r.status_code == 200 and r.text == "ok"
    assert "set-cookie" not in r.headers
    assert client.get("/api/config", headers={"host": "10.0.0.7:10000"}).status_code == 400  # selain health: tetap ditolak


def test_server_allowed_hosts():
    from malas_api.app import server_allowed_hosts

    assert server_allowed_hosts("127.0.0.1", {}) is None
    assert server_allowed_hosts("0.0.0.0", {}) == ["*"]
    got = server_allowed_hosts("0.0.0.0", {"RENDER_EXTERNAL_HOSTNAME": "malas.onrender.com", "MALAS_WEB_ALLOWED_HOSTS": "a.com, b.com"})
    assert got[:3] == ["a.com", "b.com", "malas.onrender.com"] and "localhost" in got


def test_ringkasan_riwayat_memuat_progres_dan_posisi_antrean(make):
    """B1/B2: riwayat memuat mata_kuliah, progres tahap, tahap berjalan; job antre punya posisi."""
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        progress("input", "running"); progress("input", "done")
        progress("outline", "running"); progress("outline", "info", "menyusun outline")
        gate.wait(5)
        return fake_runner(job, progress, out)

    client, _ = make(slow)
    a = client.post("/api/jobs", json=VALID).json()["id"]
    end = time.time() + 5
    while time.time() < end:
        row = next(j for j in client.get("/api/jobs").json() if j["id"] == a)
        if row["current_step"] == "outline":
            break
        time.sleep(0.02)
    assert row["mata_kuliah"] == "Kecerdasan Buatan"
    assert row["progress"] == {"done": 1, "total": 7}
    assert row["current_detail"] == "menyusun outline"
    assert row["queue_position"] is None

    b = client.post("/api/jobs", json=VALID).json()["id"]
    rows = {j["id"]: j for j in client.get("/api/jobs").json()}
    assert rows[b]["queue_position"] == 1
    assert client.get(f"/api/jobs/{b}").json()["queue_position"] == 1
    assert client.get(f"/api/jobs/{a}").json()["queue_position"] is None
    gate.set()
    done = wait_for(client, a, {"done"})
    assert next(j for j in client.get("/api/jobs").json() if j["id"] == a)["progress"] is None
    # B3: waktu per tahap
    st = done["steps"]["input"]
    assert st["started_at"] and st["finished_at"]

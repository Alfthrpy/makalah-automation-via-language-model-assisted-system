"""Logo kampus/sekolah: unggah, validasi, isolasi antar pengguna, dan logo benar-benar tertanam di .docx hasil."""
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from malas_api.app import create_app
from malas_api.jobs import JobManager, default_runner
from PIL import Image

BASE = {
    "judul": "Etika Bermedia Sosial", "mata_kuliah": "Etika", "dosen_pengampu": "Dosen",
    "penyusun": [{"nama": "A", "nim": "1"}], "kelas": "A", "universitas": "Universitas Contoh",
    "fakultas": "F", "jurusan": "J", "kota": "Kota", "tahun": "2025", "mock": True,
}


def png(color=(20, 90, 180), size=(240, 160)):
    b = io.BytesIO(); Image.new("RGB", size, color).save(b, format="PNG"); return b.getvalue()


def ok_runner(job, progress, out, runtime=None):
    progress("input", "done"); out.write_bytes(b"PK-x"); seen["job"] = dict(job)
    return {"usage": {}, "stats": {}}


seen: dict = {}


@pytest.fixture
def make(tmp_path):
    ms = []

    def _make(runner=ok_runner, hosted=True):
        m = JobManager(tmp_path, runner=runner)
        ms.append(m)
        return TestClient(create_app(m, hosted=hosted)), m

    seen.clear()
    yield _make
    for m in ms:
        m.shutdown()


def wait_for(client, jid, want=("done", "error"), timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError("timeout")


def test_alur_unggah_lihat_hapus(make):
    c, _ = make()
    assert c.get("/api/logo").status_code == 404 and c.get("/api/me").json()["logo"] is None
    r = c.put("/api/logo", content=png(), headers={"Content-Type": "image/png"})
    assert r.status_code == 200 and r.json()["size"] > 0
    got = c.get("/api/logo")
    assert got.status_code == 200 and got.headers["content-type"] == "image/png" and got.headers["cache-control"] == "no-store"
    assert Image.open(io.BytesIO(got.content)).size == (600, 600)  # dinormalkan ke PNG persegi
    assert c.get("/api/me").json()["logo"]["size"] == r.json()["size"]
    assert c.delete("/api/logo").json() == {"result": "deleted"}
    assert c.get("/api/logo").status_code == 404 and c.delete("/api/logo").status_code == 404


def test_ganti_logo_menimpa(make):
    c, _ = make()
    c.put("/api/logo", content=png((255, 0, 0)))
    first = c.get("/api/logo").content
    c.put("/api/logo", content=png((0, 0, 255)))
    assert c.get("/api/logo").content != first


@pytest.mark.parametrize("body,status,kata", [
    (b"", 422, "kosong"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", 422, "valid"),
    (b"GIF89a" + b"\0" * 30, 422, "valid"),
    (b"x" * 300_001, 413, "300 KB"),
])
def test_unggahan_buruk_ditolak_dan_tidak_tersimpan(make, body, status, kata):
    c, _ = make()
    r = c.put("/api/logo", content=body)
    assert r.status_code == status and kata in r.json()["detail"]
    assert c.get("/api/logo").status_code == 404


def test_logo_terisolasi_antar_pengguna(make):
    a, m = make()
    b = TestClient(create_app(m, hosted=True))  # klien lain = cookie/pemilik lain
    a.put("/api/logo", content=png())
    assert a.get("/api/logo").status_code == 200 and b.get("/api/logo").status_code == 404
    assert b.delete("/api/logo").status_code == 404 and a.get("/api/logo").status_code == 200


def test_use_logo_tanpa_logo_ditolak_dan_dengan_logo_dibawa_ke_runner(make):
    c, _ = make()
    r = c.post("/api/jobs", json={**BASE, "use_logo": True})
    assert r.status_code == 422 and "logo" in str(r.json()["detail"]).lower()
    c.put("/api/logo", content=png())
    r = c.post("/api/jobs", json={**BASE, "use_logo": True})
    assert r.status_code == 202 and r.json()["use_logo"] is True
    job = wait_for(c, r.json()["id"])
    assert job["status"] == "done"
    assert seen["job"]["logo_path"].endswith("logo.png") and seen["job"]["neutral_logo"] is True
    assert "use_logo" not in seen["job"]["request"]  # bukan bagian data makalah (tidak masuk ke Makalah/prompt)


def test_tanpa_use_logo_runner_dapat_penanda_netral(make):
    c, _ = make()
    c.put("/api/logo", content=png())
    jid = c.post("/api/jobs", json=BASE).json()["id"]
    wait_for(c, jid)
    assert "logo_path" not in seen["job"] and seen["job"]["neutral_logo"] is True


def test_logo_dihapus_saat_job_mengantre_job_tetap_selesai_tanpa_logo(make):
    import threading
    gate = threading.Event()
    started = threading.Event()

    def runner(job, progress, out, runtime=None):
        if job["title"] == "Job penahan":
            started.set(); gate.wait(10)
        out.write_bytes(b"PK-x"); seen[job["title"]] = dict(job)
        return {"usage": {}, "stats": {}}

    c, _ = make(runner, hosted=False)  # lokal: boleh lebih dari satu job aktif per pengguna
    c.put("/api/logo", content=png())
    c.post("/api/jobs", json={**BASE, "judul": "Job penahan"})
    assert started.wait(5)
    jid = c.post("/api/jobs", json={**BASE, "use_logo": True}).json()["id"]  # mengantre di belakang job penahan
    assert c.delete("/api/logo").status_code == 200
    gate.set()
    job = wait_for(c, jid)
    assert job["status"] == "done"  # tidak gagal walau logo sudah dihapus
    assert "logo_path" not in seen[BASE["judul"]] and seen[BASE["judul"]]["neutral_logo"] is True
    assert "logo tersimpan tidak ditemukan" in job["steps"]["docx"]["detail"]


def test_retensi_default_48_jam_di_mode_hosting_dan_tanpa_batas_lokal(make):
    from malas_api.app import retention_from_env
    assert retention_from_env(True, {}) == 48.0 and retention_from_env(False, {}) is None
    assert retention_from_env(True, {"MALAS_WEB_RETENTION_HOURS": "6"}) == 6.0  # env menimpa
    c, m = make(hosted=True)
    assert c.get("/api/config").json()["retention_hours"] == m.retention_hours


def test_pipeline_asli_menanam_logo_pengguna_di_docx(tmp_path):
    m = JobManager(tmp_path, runner=default_runner, quiet=True)
    try:
        c = TestClient(create_app(m, hosted=True))
        c.put("/api/logo", content=png((200, 20, 20), (300, 300)))
        stored = c.get("/api/logo").content
        jid = c.post("/api/jobs", json={**BASE, "use_logo": True}).json()["id"]
        job = wait_for(c, jid, timeout=120)
        assert job["status"] == "done", job["error"]
        with zipfile.ZipFile(io.BytesIO(c.get(f"/api/jobs/{jid}/download").content)) as z:
            assert z.read("word/media/image1.png") == stored  # logo pengguna, bukan logo bawaan template
        # job tanpa use_logo: penanda netral (bukan logo institusi bawaan template)
        jid2 = c.post("/api/jobs", json=BASE).json()["id"]
        assert wait_for(c, jid2, timeout=120)["status"] == "done"
        from malas.logo import placeholder_logo
        with zipfile.ZipFile(io.BytesIO(c.get(f"/api/jobs/{jid2}/download").content)) as z:
            assert z.read("word/media/image1.png") == placeholder_logo()
    finally:
        m.shutdown()

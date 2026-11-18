"""Lanjutkan job gagal dari checkpoint + coba ulang sub-bab."""
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from malas import checkpoint
from malas.crews.models.TaskOutput import Bab, ContentText, Makalah, ReferenceItem, SubBab
from malas.web.app import create_app
from malas.web.jobs import JobManager, default_runner

BASE = {"judul": "Uji Lanjut", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani"}], "mock": True}


def wait_for(client, jid, want, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.05)
    raise AssertionError(f"timeout, status={j['status']}")


# ---------------------------------------------------------------- checkpoint
def _state(done=1):
    subs = [SubBab(judul=f"1.{i}", content=[ContentText(isi="x")] if i <= done else []) for i in range(1, 4)]
    return Makalah(judul="J", bab={"I": Bab(judul="Bab 1", subbab=subs)},
                   daftar_pustaka=[ReferenceItem(title="t", authors=["A B"], year=2024)])


def test_checkpoint_roundtrip_dan_meta(tmp_path):
    p = tmp_path / "ck.json"
    checkpoint.save(p, _state(2), {"total": 5}, {"x": 1})
    ck = checkpoint.load(p)
    assert ck["meta"] == {"outline": True, "done": 2, "total": 3} and ck["usage"] == {"total": 5}
    assert Makalah.model_validate(ck["state"]).bab["I"].subbab[0].content[0].isi == "x"


def test_checkpoint_rusak_atau_versi_beda_diabaikan(tmp_path):
    p = tmp_path / "ck.json"
    assert checkpoint.load(p) is None  # tidak ada
    p.write_text("{rusak", encoding="utf-8")
    assert checkpoint.load(p) is None
    p.write_text('{"version": 999, "state": {}}', encoding="utf-8")
    assert checkpoint.load(p) is None


# ---------------------------------------------------------------- coba ulang sub-bab
@pytest.fixture
def flow(monkeypatch):
    from malas.main import MalasFlow

    monkeypatch.setattr(time, "sleep", lambda s: None)
    f = MalasFlow()
    f._ensure_counters()
    return f


def _crew(outcomes):
    """Crew palsu: tiap kickoff mengikuti outcomes (Exception = dilempar, list = konten)."""
    calls = {"n": 0}
    out = SimpleNamespace(output=None)

    def kickoff(inputs):
        o = outcomes[min(calls["n"], len(outcomes) - 1)]
        calls["n"] += 1
        if isinstance(o, Exception):
            raise o
        out.output = SimpleNamespace(pydantic=SimpleNamespace(content=o) if o is not None else None)
        return SimpleNamespace(token_usage=None)

    return SimpleNamespace(kickoff=kickoff), SimpleNamespace(tasks=[out]), calls


GOOD = [ContentText(isi="isi")]


def test_ulang_sekali_untuk_galat_sementara(flow):
    crew, writer, calls = _crew([ConnectionError("Connection reset"), GOOD])
    assert flow._write_subbab(crew, writer, {}, "1.1") == GOOD and calls["n"] == 2


def test_galat_fatal_tidak_diulang(flow):
    crew, writer, calls = _crew([RuntimeError("401 Unauthorized: invalid API key"), GOOD])
    with pytest.raises(RuntimeError, match="401"):
        flow._write_subbab(crew, writer, {}, "1.1")
    assert calls["n"] == 1  # tidak membuang token/waktu untuk galat yang pasti gagal lagi


def test_keluaran_kosong_diulang_lalu_gagal_keras(flow):
    crew, writer, calls = _crew([None])
    with pytest.raises(RuntimeError, match="tidak menghasilkan isi"):
        flow._write_subbab(crew, writer, {}, "1.1")
    assert calls["n"] == 2
    crew, writer, calls = _crew([[], GOOD])  # kosong lalu bagus
    assert flow._write_subbab(crew, writer, {}, "1.1") == GOOD


# ---------------------------------------------------------------- end-to-end: gagal lalu lanjut
def test_gagal_di_tengah_lalu_dilanjutkan(tmp_path, monkeypatch):
    from malas.main import MalasFlow

    original = MalasFlow._write_subbab
    written, state = [], {"fail": True}

    def flaky(self, crew, writer, inputs, judul):
        if state["fail"] and judul.startswith("2.1"):
            raise RuntimeError("koneksi putus permanen")
        written.append(judul)
        return original(self, crew, writer, inputs, judul)

    monkeypatch.setattr(MalasFlow, "_write_subbab", flaky)
    monkeypatch.setattr(time, "sleep", lambda s: None)

    m = JobManager(tmp_path, runner=default_runner)
    try:
        client = TestClient(create_app(m, hosted=False))
        j1 = wait_for(client, client.post("/api/jobs", json=BASE).json()["id"], {"error", "done"})
        assert j1["status"] == "error" and j1["error_step"] == "tulis"
        assert j1["resume"] == {"available": True, "done": 3, "total": 11}
        assert written == ["1.1 Latar Belakang", "1.2 Rumusan Masalah", "1.3 Tujuan Penulisan"]

        # lanjutkan: outline TIDAK diulang, hanya 8 sub-bab sisa yang ditulis
        state["fail"] = False
        written.clear()
        r = client.post("/api/jobs", json={**BASE, "resume_from": j1["id"]})
        assert r.status_code == 202 and r.json()["resume_from"] == j1["id"]
        j2 = wait_for(client, r.json()["id"], {"error", "done"})
        assert j2["status"] == "done", j2["error"]
        assert len(written) == 8 and written[0].startswith("2.1")
        assert "memakai hasil sebelumnya (3/11" in j2["steps"]["outline"]["detail"]
        assert "dilewati" in "\n".join(l["msg"] for l in j2["log"])
        assert client.get(f"/api/jobs/{j2['id']}/download").content[:2] == b"PK"
        assert not (tmp_path / "jobs" / j2["id"] / "checkpoint.json").exists()  # selesai: draf dibuang

        # job asal tetap bisa dilanjutkan lagi; job selesai tidak bisa
        assert client.get(f"/api/jobs/{j1['id']}").json()["resume"]["available"] is True
        assert client.post("/api/jobs", json={**BASE, "resume_from": j2["id"]}).status_code == 409
    finally:
        m.shutdown()


def test_lanjut_hanya_untuk_pemilik_dan_id_valid(tmp_path):
    def fail(job, progress, out, runtime=None):
        checkpoint.save(out.parent / "checkpoint.json", _state(1), {}, {})
        raise RuntimeError("x")

    m = JobManager(tmp_path, runner=fail)
    try:
        a = TestClient(create_app(m, hosted=False))
        jid = a.post("/api/jobs", json=BASE).json()["id"]
        wait_for(a, jid, {"error"})
        assert a.get(f"/api/jobs/{jid}").json()["resume"]["done"] == 1
        b = TestClient(create_app(m, hosted=False))  # pengguna lain
        assert b.post("/api/jobs", json={**BASE, "resume_from": jid}).status_code == 404
        assert a.post("/api/jobs", json={**BASE, "resume_from": "../../etc"}).status_code == 422
        assert a.post("/api/jobs", json={**BASE, "resume_from": "0" * 32}).status_code == 404
    finally:
        m.shutdown()


def test_job_tanpa_outline_tidak_bisa_dilanjutkan(tmp_path):
    def fail(job, progress, out, runtime=None):
        s = Makalah(judul="J")  # outline belum jadi
        checkpoint.save(out.parent / "checkpoint.json", s, {}, {})
        raise RuntimeError("x")

    m = JobManager(tmp_path, runner=fail)
    try:
        c = TestClient(create_app(m, hosted=False))
        jid = c.post("/api/jobs", json=BASE).json()["id"]
        j = wait_for(c, jid, {"error"})
        assert j["resume"]["available"] is False
        assert c.post("/api/jobs", json={**BASE, "resume_from": jid}).status_code == 409
    finally:
        m.shutdown()

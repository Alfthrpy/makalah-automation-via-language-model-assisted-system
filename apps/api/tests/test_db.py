"""Fase 2: database (migrasi, antrean atomik, heartbeat/pemulihan, checkpoint & berkas di DB, key terenkripsi)."""
import threading
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text

from malas import checkpoint
from malas.crews.models.TaskOutput import Bab, ContentText, Makalah, ReferenceItem, SubBab
from malas_api import db as dbmod
from malas_api.app import create_app
from malas_api.crypto import CryptoError, KeyCipher, cipher_from_env
from malas_api.jobs import JobManager

SECRET = "rahasia-server-uji-yang-cukup-panjang-123456"
KEY = "sk-or-v1-TERSIMPAN1234567890abcdef"
BASE = {"judul": "Uji DB", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani"}], "tahun": "2025"}
REQ = {"judul": "Uji DB", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani", "nim": ""}], "tahun": "2025"}


def state(done=1):
    subs = [SubBab(judul=f"1.{i}", content=[ContentText(isi="x")] if i <= done else []) for i in range(1, 4)]
    return Makalah(judul="J", bab={"I": Bab(judul="Bab 1", subbab=subs)},
                   daftar_pustaka=[ReferenceItem(title="t", authors=["A B"], year=2024)])


def wait_for(client, jid, want, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError(f"timeout; status={j['status']}")


def ok_runner(job, progress, out, runtime=None):
    progress("input", "done")
    out.write_bytes(b"PK-docx")
    return {"usage": {}, "stats": {}}


@pytest.fixture
def managers(tmp_path):
    ms = []

    def _make(runner=ok_runner, **kw):
        kw.setdefault("stale_after", 0)
        m = JobManager(tmp_path, runner=runner, **kw)
        ms.append(m)
        return m

    yield _make
    for m in ms:
        m.shutdown()


def submit(m, owner="u1", **kw):
    return m.submit(dict(REQ), True, "tpl.docx", "tpl.docx", owner=owner, **kw)


# ---------------------------------------------------------------- migrasi & skema
def test_migrasi_membuat_skema_dan_idempoten(tmp_path):
    d = dbmod.Database(dbmod.sqlite_url(tmp_path / "x.db"))
    names = set(inspect(d.engine).get_table_names())
    assert {"users", "jobs", "job_checkpoints", "job_files", "user_api_keys", "alembic_version"} <= names
    dbmod.migrate(d.engine)  # kedua kali: tidak error, tidak menggandakan
    with d.engine.connect() as c:
        assert c.execute(text("select count(*) from alembic_version")).scalar() == 1
    d.dispose()


def test_skema_migrasi_sama_dengan_model(tmp_path):
    """Migrasi dan model tidak boleh menyimpang (autogenerate tidak menemukan beda)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    d = dbmod.Database(dbmod.sqlite_url(tmp_path / "x.db"))
    with d.engine.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), dbmod.Base.metadata)
    assert diff == [], diff
    d.dispose()


def test_url_neon_dinormalisasi():
    assert dbmod.normalize_url("postgres://u:p@h/db?sslmode=require") == "postgresql+psycopg://u:p@h/db?sslmode=require"
    assert dbmod.normalize_url("postgresql://u@h/db").startswith("postgresql+psycopg://")
    assert dbmod.normalize_url("sqlite:///a.db") == "sqlite:///a.db"


# ---------------------------------------------------------------- antrean
def test_claim_fifo_dan_hanya_sekali(tmp_path):
    d = dbmod.Database(dbmod.sqlite_url(tmp_path / "q.db"))
    from malas_api.jobs import _now
    from malas_api.repo import Repo

    repo = Repo(d)
    ids = []
    for i in range(3):
        jid = f"{i:032x}"
        repo.create_job({"id": jid, "owner": "u", "status": "queued", "created_at": f"2025-01-01T00:00:0{i}+00:00",
                         "title": "t", "request": {}, "steps": {}, "log": []})
        ids.append(jid)
    assert [repo.claim_next() for _ in range(4)] == [*ids, None]
    assert repo.get(ids[0])["status"] == "running" and _now()
    d.dispose()


def test_claim_paralel_tidak_ada_job_ganda(tmp_path):
    d = dbmod.Database(dbmod.sqlite_url(tmp_path / "q.db"))
    from malas_api.repo import Repo

    repo = Repo(d)
    for i in range(12):
        repo.create_job({"id": f"{i:032x}", "owner": "u", "status": "queued", "created_at": f"2025-01-01T00:00:{i:02d}+00:00",
                         "title": "t", "request": {}, "steps": {}, "log": []})
    got, lock = [], threading.Lock()

    def worker():
        while (j := repo.claim_next()):
            with lock:
                got.append(j)

    ts = [threading.Thread(target=worker) for _ in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert sorted(got) == sorted(f"{i:032x}" for i in range(12))  # tiap job tepat sekali
    d.dispose()


def test_skip_locked_di_postgres(pg_url):
    """Baris antre yang sedang dikunci pekerja lain dilewati (bukan ditunggu)."""
    from malas_api.repo import Repo

    d = dbmod.Database(pg_url)
    repo = Repo(d)
    for i in range(2):
        repo.create_job({"id": f"{i:032x}", "owner": "u", "status": "queued", "created_at": f"2025-01-01T00:00:0{i}+00:00",
                         "title": "t", "request": {}, "steps": {}, "log": []})
    other = create_engine(d.url).connect()
    tx = other.begin()
    other.execute(text("select id from jobs where status='queued' order by created_at limit 1 for update"))  # pegang job #0
    try:
        t0 = time.time()
        assert repo.claim_next() == f"{1:032x}"  # job #1, tidak menunggu job #0
        assert time.time() - t0 < 2
    finally:
        tx.rollback()
        other.close()
    d.dispose()


def test_job_antre_dijalankan_berurutan_dan_hasil_di_db(managers):
    m = managers()
    a, b = submit(m)["id"], submit(m)["id"]
    c = TestClient(create_app(m, hosted=False))
    for jid in (a, b):
        end = time.time() + 5
        while m.get(jid)["status"] != "done" and time.time() < end:
            time.sleep(0.02)
        assert m.get(jid)["status"] == "done"
    assert m.get(a)["finished_at"] <= m.get(b)["started_at"] or m.get(a)["finished_at"][:19] <= m.get(b)["started_at"][:19]
    assert m.read_file(a) == b"PK-docx" and m.storage.get(b) == b"PK-docx"
    assert c  # app terbentuk di atas manager yang sama


# ---------------------------------------------------------------- heartbeat & pemulihan
def test_heartbeat_menjaga_job_tidak_dianggap_mati(managers):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        out.write_bytes(b"x")
        return {}

    m = managers(runner=slow, stale_after=0.6, heartbeat_every=0.1)
    jid = submit(m)["id"]
    end = time.time() + 3
    while m.get(jid)["status"] != "running" and time.time() < end:
        time.sleep(0.02)
    time.sleep(1.2)  # > stale_after, tapi heartbeat jalan
    assert m.recover_stale() == 0 and m.get(jid)["status"] == "running"
    gate.set()
    end = time.time() + 5
    while m.get(jid)["status"] != "done" and time.time() < end:
        time.sleep(0.02)
    assert m.get(jid)["status"] == "done"


def test_job_mati_ditandai_interrupted_dan_zombie_tidak_menimpa(managers, tmp_path):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        from malas.checkpoint import save
        save(out.parent / "checkpoint.json", state(2), {}, {})
        progress("tulis", "running")  # memicu sinkron checkpoint ke DB
        gate.wait(5)
        out.write_bytes(b"x")
        return {}

    m1 = managers(runner=slow, stale_after=0, heartbeat_every=60)
    jid = submit(m1)["id"]
    end = time.time() + 3
    while m1.get(jid)["status"] != "running" or not m1.repo.checkpoint_meta(jid):
        assert time.time() < end
        time.sleep(0.02)
    m1.shutdown()  # server "mati": heartbeat berhenti

    m2 = managers()  # server baru di DB yang sama
    j = m2.get(jid)
    assert j["status"] == "interrupted" and j["resume"] == {"available": True, "done": 2, "total": 3}
    gate.set()  # proses lama (zombie) akhirnya selesai...
    time.sleep(0.4)
    assert m2.get(jid)["status"] == "interrupted" and not m2.get(jid)["has_file"]  # ...tapi tidak menimpa


def test_job_antre_dengan_key_sesi_hilang_saat_restart(managers):
    gate = threading.Event()
    m1 = managers(runner=lambda j, p, o, r=None: gate.wait(5) and {}, stale_after=0, heartbeat_every=60)
    from malas.config import Runtime
    a = submit(m1)["id"]
    end = time.time() + 3
    while m1.get(a)["status"] != "running":
        assert time.time() < end
        time.sleep(0.02)
    b = m1.submit(dict(REQ), False, "t", "t", owner="u1", runtime=Runtime("openrouter", KEY, "p", "w"))["id"]
    assert m1.get(b)["status"] == "queued"
    m1.shutdown()
    m2 = managers()
    end = time.time() + 5
    while m2.get(b)["status"] in {"queued", "running"}:
        assert time.time() < end
        time.sleep(0.02)
    jb = m2.get(b)
    assert jb["status"] == "error" and "tidak disimpan" in jb["error"] and KEY not in str(jb)
    gate.set()


def eventually(cond, timeout=5.0, what="kondisi"):
    """Tunggu pembersihan yang SENGAJA terjadi sesaat SETELAH status job berubah (key dibuang di `finally`, checkpoint
    dihapus setelah status tersimpan agar resume tidak hilang bila proses mati). Menuntutnya seketika = balapan antar thread."""
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError(f"{what} tidak terpenuhi dalam {timeout} dtk")


def test_checkpoint_dan_berkas_selamat_dari_restart_lalu_lanjut(managers):
    def fail(job, progress, out, runtime=None):
        checkpoint.save(out.parent / "checkpoint.json", state(2), {}, {})
        progress("tulis", "running")
        raise RuntimeError("putus")

    def resume_ok(job, progress, out, runtime=None):
        ck = checkpoint.load(out.parent / "checkpoint.json")  # dipulihkan dari DB ke folder kerja
        assert ck and ck["meta"]["done"] == 2 and job["resume_from"]
        out.write_bytes(b"PK-lanjut")
        return {}

    m1 = managers(runner=fail)
    jid = submit(m1)["id"]
    end = time.time() + 3
    while m1.get(jid)["status"] != "error":
        assert time.time() < end
        time.sleep(0.02)
    m1.shutdown()

    m2 = managers(runner=resume_ok)
    assert m2.get(jid)["resume"] == {"available": True, "done": 2, "total": 3}
    j2 = m2.submit(dict(REQ), True, "t", "t", owner="u1", resume_from=jid)["id"]
    end = time.time() + 3
    while m2.get(j2)["status"] != "done":
        assert time.time() < end, m2.get(j2)
        time.sleep(0.02)
    assert m2.read_file(j2) == b"PK-lanjut"
    eventually(lambda: m2.repo.checkpoint_meta(j2) is None, what="checkpoint job selesai terhapus")
    assert m2.repo.checkpoint_meta(jid) is not None  # job asal tetap bisa dilanjutkan lagi
    with pytest.raises(ValueError):
        m2.submit(dict(REQ), True, "t", "t", owner="u1", resume_from="0" * 32)


def test_hapus_job_membersihkan_checkpoint_dan_berkas(managers):
    m = managers()
    jid = submit(m)["id"]
    end = time.time() + 3
    while m.get(jid)["status"] != "done":
        assert time.time() < end
        time.sleep(0.02)
    m.repo.put_checkpoint(jid, b"{}", {"outline": True, "done": 1, "total": 2})
    assert m.delete(jid) == "deleted"
    assert m.get(jid) is None and m.storage.get(jid) is None and m.repo.checkpoint_meta(jid) is None


# ---------------------------------------------------------------- enkripsi key
def test_cipher_roundtrip_dan_rotasi():
    c1 = KeyCipher([SECRET])
    token = c1.encrypt(KEY)
    assert KEY not in token and c1.decrypt(token) == KEY
    c2 = KeyCipher(["rahasia-baru-yang-juga-cukup-panjang-98765", SECRET])  # rotasi: yang lama masih bisa dibaca
    assert c2.decrypt(token) == KEY
    with pytest.raises(CryptoError):
        KeyCipher(["rahasia-lain-yang-sama-sekali-berbeda-000000"]).decrypt(token)


def test_cipher_dari_env_butuh_rahasia_panjang():
    assert cipher_from_env({}) is None
    assert cipher_from_env({"MALAS_SECRET_KEY": "pendek"}) is None
    assert cipher_from_env({"MALAS_SECRET_KEY": SECRET}) is not None


def dump_db(m) -> str:
    out = []
    with m.db.engine.connect() as c:
        for t in dbmod.Base.metadata.sorted_tables:
            for row in c.execute(select(t)):
                out.append(repr(tuple(bytes(x).decode("latin1") if isinstance(x, (bytes, memoryview)) else x for x in row)))
    return "\n".join(out)


def make_client(m, hosted=True):
    return TestClient(create_app(m, hosted=hosted))


def test_simpan_key_ditolak_bila_server_tanpa_rahasia(managers):
    c = make_client(managers())
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True})
    assert r.status_code == 409 and KEY not in r.text
    assert c.get("/api/keys").json() == {"enabled": False, "keys": []}


def test_key_tersimpan_dipakai_job_tanpa_pernah_plaintext_di_db(managers):
    seen = {}

    def runner(job, progress, out, runtime=None):
        seen["rt"] = runtime
        out.write_bytes(b"PK")
        return {}

    m = managers(runner=runner, cipher=KeyCipher([SECRET]))
    c = make_client(m, hosted=False)
    assert c.get("/api/config").json()["key_storage"] is True
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True})
    assert r.status_code == 202 and KEY not in r.text
    assert r.json()["key_source"] == "saved" and r.json()["byok"] is True
    wait_for(c, r.json()["id"], {"done"})
    assert seen["rt"].api_key == KEY and seen["rt"].provider_id == "openrouter"  # didekripsi saat job jalan
    assert KEY not in dump_db(m)  # di DB hanya ciphertext
    keys = c.get("/api/keys").json()
    assert keys["keys"][0]["provider"] == "openrouter" and KEY not in str(keys)

    # job berikutnya tanpa mengirim key
    r2 = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True})
    assert r2.status_code == 202
    wait_for(c, r2.json()["id"], {"done"})
    assert seen["rt"].api_key == KEY
    eventually(lambda: len(m.vault) == 0, what="brankas kosong")  # brankas bersih setelah job

    assert c.delete("/api/keys/openrouter").json() == {"result": "deleted"}
    assert c.delete("/api/keys/openrouter").status_code == 404
    assert c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).status_code == 422


def test_key_tersimpan_milik_pengguna_lain_tidak_terpakai(managers):
    m = managers(cipher=KeyCipher([SECRET]))
    a, b = make_client(m, hosted=False), make_client(m, hosted=False)
    assert a.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True}).status_code == 202
    assert b.get("/api/keys").json()["keys"] == []
    assert b.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).status_code == 422


def test_rahasia_server_berubah_job_gagal_ramah(managers):
    m = managers(cipher=KeyCipher([SECRET]))
    c = make_client(m, hosted=False)
    jid = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True}).json()["id"]
    wait_for(c, jid, {"done", "error"})
    m.cipher = KeyCipher(["rahasia-berganti-yang-cukup-panjang-1111111"])
    j2 = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()["id"]
    j = wait_for(c, j2, {"error"})
    assert "didekripsi" in j["error"] and KEY not in str(j)


def test_lanjut_otomatis_bila_key_tersimpan(managers):
    calls = []
    gate = threading.Event()

    def runner(job, progress, out, runtime=None):
        calls.append((job["id"], bool(job.get("resume_from")), runtime.api_key if runtime else None))
        if not job.get("resume_from"):
            checkpoint.save(out.parent / "checkpoint.json", state(2), {}, {})
            progress("tulis", "running")
            gate.wait(5)
            return {}
        out.write_bytes(b"PK-auto")
        return {}

    cipher = KeyCipher([SECRET])
    m1 = managers(runner=runner, cipher=cipher, heartbeat_every=60)
    c1 = make_client(m1, hosted=False)
    jid = c1.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True}).json()["id"]
    end = time.time() + 3
    while not m1.repo.checkpoint_meta(jid):
        assert time.time() < end
        time.sleep(0.02)
    m1.shutdown()

    m2 = managers(runner=runner, cipher=cipher)  # restart: pemulihan + lanjut otomatis tanpa campur tangan pengguna
    assert m2.get(jid)["status"] == "interrupted"
    end = time.time() + 5
    resumed = None
    while not resumed:
        assert time.time() < end
        resumed = next((x for x in (m2.get(i["id"]) for i in m2.list(m2.get(jid)["owner"])) if x["resume_from"] == jid), None)
        time.sleep(0.02)
    while m2.get(resumed["id"])["status"] != "done":
        assert time.time() < end
        time.sleep(0.02)
    assert m2.read_file(resumed["id"]) == b"PK-auto"
    assert calls[-1] == (resumed["id"], True, KEY)
    assert m2.get(jid)["auto_resumed"] is True
    gate.set()
    # tidak diulang tanpa batas: pemulihan kedua tidak membuat job baru lagi
    assert len([i for i in m2.list(m2.get(jid)["owner"]) if m2.get(i["id"])["resume_from"] == jid]) == 1

"""Pengerasan penyimpanan key (P0): hanya pemilik stabil, tidak tersimpan bila ditolak, PUT eksplisit,
kedaluwarsa key menganggur, hapus data saat akun Clerk dihapus, dan redaksi key Kenari."""
import base64
import hashlib
import hmac
import json
import threading
import time
from datetime import timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from malas_api import db as dbmod
from malas_api import webhooks
from malas_api.app import create_app
from malas_api.auth import Authenticator
from malas_api.crypto import KeyCipher
from malas_api.jobs import JobManager
from malas_api.vault import REDACTED, Vault

SECRET = "rahasia-server-uji-yang-cukup-panjang-123456"
KEY = "sk-or-v1-TERSIMPAN1234567890abcdef"
KEY2 = "sk-or-v1-GANTI0987654321abcdefghij"
BASE = {"judul": "Uji Key", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani"}], "tahun": "2025"}
ISS, AZP = "https://clerk.test", "https://app.test"
PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Stub:
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": PRIV.public_key()})()


def authn():
    return Authenticator(issuer=ISS, jwks=Stub(), authorized_parties=[AZP])


def token(sub):
    now = int(time.time())
    return jwt.encode({"sub": sub, "iss": ISS, "azp": AZP, "exp": now + 300, "iat": now}, PRIV, algorithm="RS256")


def wait_for(c, jid, want, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError(j)


def eventually(cond, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("kondisi tidak terpenuhi")


seen = {}


def ok_runner(job, progress, out, runtime=None):
    seen["key"] = runtime.api_key if runtime else None
    out.write_bytes(b"PK-docx")
    return {}


@pytest.fixture
def make(tmp_path):
    ms = []

    def _make(runner=ok_runner, cipher=True, **kw):
        m = JobManager(tmp_path, runner=runner, cipher=KeyCipher([SECRET]) if cipher else None, stale_after=0, **kw)
        ms.append(m)
        return m

    seen.clear()
    yield _make
    for m in ms:
        m.shutdown()


def web(m, *, hosted, auth=None, tok=None, quota=0):
    c = TestClient(create_app(m, hosted=hosted, auth=auth, daily_quota=quota))
    if tok:
        c.headers["Authorization"] = f"Bearer {tok}"
    return c


# ---------------------------------------------------------------- hanya pemilik stabil
def test_hosting_anonim_tidak_boleh_menyimpan_key(make):
    m = make()
    c = web(m, hosted=True)  # hosting tanpa Clerk: pemilik = cookie acak
    assert c.get("/api/config").json()["key_storage"] is False
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True})
    assert r.status_code == 409 and KEY not in r.text
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).status_code == 409
    assert c.get("/api/keys").json() == {"enabled": False, "keys": []}
    with m.db.session() as s:
        assert s.scalar(select(dbmod.UserApiKey.ciphertext)) is None  # tidak ada yang tersimpan


def test_hosting_dengan_clerk_boleh_menyimpan(make):
    m = make()
    c = web(m, hosted=True, auth=authn(), tok=token("user_a"))
    assert c.get("/api/config").json()["key_storage"] is True
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).json() == {"result": "saved_unverified"}  # verifikasi mati di tes


def test_lokal_anonim_tetap_boleh(make):
    c = web(make(), hosted=False)
    assert c.get("/api/config").json()["key_storage"] is True


# ---------------------------------------------------------------- tidak tersimpan bila ditolak
def test_permintaan_ditolak_tidak_menyimpan_key(make):
    m = make()
    c = web(m, hosted=False, auth=authn(), tok=token("user_q"), quota=1)
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY})  # memakai kuota (key sesi)
    assert r.status_code == 202
    wait_for(c, r.json()["id"], {"done"})
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY2, "save_key": True})
    assert r.status_code == 429 and KEY2 not in r.text
    assert c.get("/api/keys").json()["keys"] == []  # ditolak -> tidak ada key yang tertinggal


# ---------------------------------------------------------------- PUT /api/keys/{provider}
def test_put_key_simpan_ganti_dan_dipakai_job(make):
    m = make()
    c = web(m, hosted=False, auth=authn(), tok=token("user_p"))
    r = c.put("/api/keys/openrouter", json={"api_key": KEY})
    assert r.status_code == 200 and KEY not in r.text
    listed = c.get("/api/keys").json()
    assert [k["provider"] for k in listed["keys"]] == ["openrouter"] and KEY not in str(listed)
    assert c.put("/api/keys/openrouter", json={"api_key": KEY2}).status_code == 200  # ganti
    j = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()
    wait_for(c, j["id"], {"done"})
    assert seen["key"] == KEY2


def test_put_key_validasi_tidak_memantulkan_input(make):
    c = web(make(), hosted=False)
    bad = "kunci dengan spasi!!"
    r = c.put("/api/keys/openrouter", json={"api_key": bad})
    assert r.status_code == 422 and bad not in r.text
    assert c.put("/api/keys/openrouter", json={"api_key": ""}).status_code == 422
    assert c.put("/api/keys/openrouter", json={}).status_code == 422
    assert c.put("/api/keys/tidak-ada", json={"api_key": KEY}).status_code == 404
    r = c.put("/api/keys/openrouter", content=json.dumps({"api_key": "x" * 5000}), headers={"content-type": "application/json"})
    assert r.status_code == 413


def test_put_key_butuh_login_di_mode_clerk(make):
    c = web(make(), hosted=True, auth=authn())  # tanpa token
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).status_code == 401


# ---------------------------------------------------------------- kedaluwarsa key menganggur
def _age_key(m, days):
    old = dbmod.utcnow() - timedelta(days=days)
    with m.db.session.begin() as s:
        s.execute(update(dbmod.UserApiKey).values(updated_at=old, last_used_at=None))


def _key_rows(m):
    with m.db.session() as s:
        return s.scalars(select(dbmod.UserApiKey.provider)).all()


def test_key_menganggur_dihapus_dan_pemakaian_menyegarkan(make):
    m = make(key_ttl_days=30)
    c = web(m, hosted=False)
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).status_code == 200
    _age_key(m, 10)
    assert m.purge_idle_keys(interval=0) == 0 and _key_rows(m) == ["openrouter"]  # belum lewat TTL
    _age_key(m, 31)
    assert m.purge_idle_keys(interval=0) == 1 and _key_rows(m) == []


def test_pemakaian_key_mengisi_last_used_dan_menunda_kedaluwarsa(make):
    m = make(key_ttl_days=30)
    c = web(m, hosted=False)
    c.put("/api/keys/openrouter", json={"api_key": KEY})
    _age_key(m, 31)  # nyaris kedaluwarsa...
    j = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()
    wait_for(c, j["id"], {"done"})  # ...tetapi dipakai
    assert m.purge_idle_keys(interval=0) == 0 and _key_rows(m) == ["openrouter"]


def test_key_tidak_dihapus_saat_pemiliknya_punya_job_aktif(make):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        out.write_bytes(b"PK")
        return {}

    m = make(runner=slow, key_ttl_days=30)
    c = web(m, hosted=False)
    c.put("/api/keys/openrouter", json={"api_key": KEY})
    j = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()
    eventually(lambda: c.get(f"/api/jobs/{j['id']}").json()["status"] == "running")
    _age_key(m, 365)
    assert m.purge_idle_keys(interval=0) == 0 and _key_rows(m) == ["openrouter"]  # job berjalan: dilewati
    gate.set()
    wait_for(c, j["id"], {"done"})
    # key sudah dipakai job (last_used_at baru) -> tetap aman; kedaluwarsakan lagi lalu bersihkan
    _age_key(m, 365)
    assert m.purge_idle_keys(interval=0) == 1


def test_ttl_nol_mematikan_pembersihan(make):
    m = make(key_ttl_days=0)
    web(m, hosted=False).put("/api/keys/openrouter", json={"api_key": KEY})
    _age_key(m, 3650)
    assert m.purge_idle_keys(interval=0) == 0 and _key_rows(m) == ["openrouter"]


def test_skema_punya_kolom_last_used_at(make):
    from sqlalchemy import inspect
    m = make()
    assert "last_used_at" in {c["name"] for c in inspect(m.db.engine).get_columns("user_api_keys")}


# ---------------------------------------------------------------- redaksi
def test_key_kenari_disaring_walau_tak_ada_di_brankas():
    leak = "gagal: key kn-abcdefghijklmnopqrst ditolak"
    out = Vault().redact(leak)
    assert "kn-abcdefghij" not in out and REDACTED in out


# ---------------------------------------------------------------- webhook Clerk user.deleted
WH_RAW = b"w" * 24
WH_ENV = "whsec_" + base64.b64encode(WH_RAW).decode()


def sign(body: bytes, *, mid="msg_1", ts=None, key=WH_RAW):
    ts = str(int(time.time()) if ts is None else ts)
    sig = base64.b64encode(hmac.new(key, f"{mid}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    return {"svix-id": mid, "svix-timestamp": ts, "svix-signature": f"v1,{sig}", "content-type": "application/json"}


def event(kind="user.deleted", uid="user_alice"):
    return json.dumps({"type": kind, "data": {"id": uid}}).encode()


@pytest.fixture
def hook(monkeypatch):
    monkeypatch.setenv("CLERK_WEBHOOK_SECRET", WH_ENV)


def test_webhook_nonaktif_tanpa_secret(make):
    c = web(make(), hosted=True, auth=authn())
    body = event()
    assert c.post("/api/webhooks/clerk", content=body, headers=sign(body)).status_code == 404


def test_webhook_menghapus_semua_data_pengguna_yang_dihapus(make, hook):
    m = make()
    app_auth = authn()
    alice = web(m, hosted=True, auth=app_auth, tok=token("user_alice"))
    bob = web(m, hosted=True, auth=app_auth, tok=token("user_bob"))
    for c in (alice, bob):
        assert c.put("/api/keys/openrouter", json={"api_key": KEY}).status_code == 200
    ja = alice.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()["id"]
    wait_for(alice, ja, {"done"})
    jb = bob.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()["id"]
    wait_for(bob, jb, {"done"})

    anon = web(m, hosted=True, auth=app_auth)  # tanpa Bearer: webhook memakai tanda tangan, bukan login
    body = event()
    r = anon.post("/api/webhooks/clerk", content=body, headers=sign(body))
    assert r.status_code == 200
    assert m.repo.user_id("user_alice") is None
    assert m.get(ja) is None and m.storage.get(ja) is None and m.list_user_keys("user_alice") == []
    assert m.repo.user_id("user_bob") and m.get(jb) and m.list_user_keys("user_bob")  # pengguna lain utuh
    assert anon.post("/api/webhooks/clerk", content=body, headers=sign(body)).status_code == 200  # idempoten


def test_webhook_menolak_tanda_tangan_salah_basi_dan_acak(make, hook):
    m = make()
    c = web(m, hosted=True, auth=authn())
    web(m, hosted=True, auth=authn(), tok=token("user_alice")).put("/api/keys/openrouter", json={"api_key": KEY})
    body = event()
    assert c.post("/api/webhooks/clerk", content=body, headers=sign(body, key=b"z" * 24)).status_code == 400
    assert c.post("/api/webhooks/clerk", content=body, headers=sign(body, ts=int(time.time()) - 3600)).status_code == 400
    assert c.post("/api/webhooks/clerk", content=body, headers={"content-type": "application/json"}).status_code == 400
    assert c.post("/api/webhooks/clerk", content=body + b"x", headers=sign(body)).status_code == 400  # body diubah
    assert m.repo.user_id("user_alice")  # tidak ada yang terhapus


def test_webhook_event_lain_tidak_menghapus(make, hook):
    m = make()
    c = web(m, hosted=True, auth=authn())
    web(m, hosted=True, auth=authn(), tok=token("user_alice")).put("/api/keys/openrouter", json={"api_key": KEY})
    for body in (event("user.updated"), json.dumps({"type": "user.deleted", "data": {}}).encode(), b"[]"):
        assert c.post("/api/webhooks/clerk", content=body, headers=sign(body)).status_code in (200, 400)
    assert m.repo.user_id("user_alice")


def test_verify_menerima_salah_satu_dari_beberapa_tanda_tangan():
    body, h = b"{}", sign(b"{}")
    h["svix-signature"] = "v1,AAAA " + h["svix-signature"]
    webhooks.verify(WH_RAW, h, body)
    h["svix-signature"] = h["svix-signature"].replace("v1,", "v2,")
    with pytest.raises(webhooks.WebhookError):
        webhooks.verify(WH_RAW, h, body)


def test_secret_webhook_salah_format_gagal_cepat():
    with pytest.raises(RuntimeError):
        webhooks.secret_from_env({"CLERK_WEBHOOK_SECRET": "whsec_bukan base64!!"})
    assert webhooks.secret_from_env({}) is None

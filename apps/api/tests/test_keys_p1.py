"""P1: AES-256-GCM dengan AAD (ciphertext terikat ke pemilik), kid, token lama tetap terbaca, penulisan ulang
(malas + berkala) untuk rotasi, rahasia monoton ditolak, dan pemeriksaan key ke penyedia sebelum disimpan."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from malas_api import crypto, keycheck
from malas_api import db as dbmod
from malas_api.app import create_app
from malas_api.auth import Authenticator
from malas_api.crypto import CryptoError, KeyCipher, cipher_from_env
from malas_api.jobs import JobManager

SECRET = "rahasia-server-uji-yang-cukup-panjang-123456"
NEW = "rahasia-baru-yang-juga-cukup-panjang-98765"
KEY = "sk-or-v1-TERSIMPAN1234567890abcdef"
BASE = {"judul": "Uji P1", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani"}], "tahun": "2025"}
ISS, AZP = "https://clerk.test", "https://app.test"
PRIV = rsa.generate_private_key(public_exponent=65537, key_size=2048)
seen = {"calls": 0}


class Stub:
    def get_signing_key_from_jwt(self, token):
        return type("K", (), {"key": PRIV.public_key()})()


def tok(sub):
    now = int(time.time())
    return jwt.encode({"sub": sub, "iss": ISS, "azp": AZP, "exp": now + 300, "iat": now}, PRIV, algorithm="RS256")


def runner(job, progress, out, runtime=None):
    seen["calls"] += 1
    seen["key"] = runtime.api_key if runtime else None
    out.write_bytes(b"PK")
    return {}


@pytest.fixture
def make(tmp_path):
    ms = []

    def _make(cipher=None, **kw):
        m = JobManager(tmp_path, runner=runner, cipher=cipher or KeyCipher([SECRET]), stale_after=0, **kw)
        ms.append(m)
        return m

    seen.update(calls=0, key=None)
    yield _make
    for m in ms:
        m.shutdown()


def web(m, sub, quota=0):
    c = TestClient(create_app(m, hosted=True, auth=Authenticator(issuer=ISS, jwks=Stub(), authorized_parties=[AZP]),
                              daily_quota=quota))
    c.headers["Authorization"] = f"Bearer {tok(sub)}"
    return c


def wait_for(c, jid, want, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError(j)


def stored(m, owner, provider="openrouter"):
    return m.repo.get_key(owner, provider)


def legacy_token(secret=SECRET, plaintext=KEY):
    return crypto._fernet(secret).encrypt(plaintext.encode()).decode()


# ---------------------------------------------------------------- primitif
def test_token_v2_format_dan_roundtrip_dengan_aad():
    c = KeyCipher([SECRET])
    t = c.encrypt(KEY, b"aad-1")
    assert t.startswith(f"v2.{c.primary_kid}.") and KEY not in t
    assert c.decrypt(t, b"aad-1") == KEY
    assert c.encrypt(KEY, b"aad-1") != t  # nonce acak


def test_aad_berbeda_tamper_kunci_lain_dan_sampah_ditolak():
    c = KeyCipher([SECRET])
    t = c.encrypt(KEY, b"aad-1")
    for bad in (lambda: c.decrypt(t, b"aad-2"), lambda: c.decrypt(t, b""),
                lambda: c.decrypt(t[:-3] + ("AAA" if not t.endswith("AAA") else "BBB"), b"aad-1"),
                lambda: KeyCipher([NEW]).decrypt(t, b"aad-1"),  # kid tidak dikenal
                lambda: c.decrypt("v2.zzzz", b""), lambda: c.decrypt("v2.", b""), lambda: c.decrypt("sampah", b""),
                lambda: c.decrypt("v2." + c.primary_kid + ".!!!", b"")):
        with pytest.raises(CryptoError):
            bad()


def test_token_fernet_lama_masih_terbaca_dan_ditandai_rekey():
    c = KeyCipher([SECRET])
    old = legacy_token()
    assert c.decrypt(old, b"apa-saja") == KEY and c.needs_rekey(old)
    assert not c.needs_rekey(c.encrypt(KEY, b"x"))


def test_rotasi_kunci_lama_terbaca_dan_ditandai_rekey():
    t = KeyCipher([SECRET]).encrypt(KEY, b"a")
    c2 = KeyCipher([NEW, SECRET])
    assert c2.decrypt(t, b"a") == KEY and c2.needs_rekey(t)
    t2 = c2.encrypt(KEY, b"a")
    assert not c2.needs_rekey(t2) and c2.primary_kid != KeyCipher([SECRET]).primary_kid


def test_rahasia_monoton_atau_pendek_ditolak():
    assert cipher_from_env({"MALAS_SECRET_KEY": "a" * 64}) is None
    assert cipher_from_env({"MALAS_SECRET_KEY": "1234" * 16}) is None
    assert cipher_from_env({"MALAS_SECRET_KEY": SECRET}) is not None
    c = cipher_from_env({"MALAS_SECRET_KEY": SECRET, "MALAS_SECRET_KEY_OLD": f"{'z' * 50},{NEW}"})
    assert c.decrypt(KeyCipher([NEW]).encrypt(KEY)) == KEY  # OLD yang sah dipakai; yang monoton diabaikan


# ---------------------------------------------------------------- terikat ke pemilik
def test_ciphertext_disalin_ke_pengguna_lain_tidak_bisa_dipakai(make):
    m = make()
    alice, bob = web(m, "user_alice"), web(m, "user_bob")
    assert alice.put("/api/keys/openrouter", json={"api_key": KEY}).status_code == 200
    m.repo.save_key("user_bob", "openrouter", stored(m, "user_alice"))  # penyerang dengan akses tulis DB
    jid = bob.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()["id"]
    j = wait_for(bob, jid, {"error", "done"})
    assert j["status"] == "error" and "didekripsi" in j["error"]
    assert seen["calls"] == 0 and KEY not in str(j)  # runner tidak pernah menerima key korban


def test_ciphertext_dipindah_antar_penyedia_juga_gagal(make):
    m = make()
    alice = web(m, "user_alice")
    alice.put("/api/keys/openrouter", json={"api_key": KEY})
    m.repo.save_key("user_alice", "kenari", stored(m, "user_alice"))
    jid = alice.post("/api/jobs", json={**BASE, "provider": "kenari", "use_saved_key": True,
                                         "model_planner": "x", "model_writer": "x"}).json()["id"]
    assert "didekripsi" in wait_for(alice, jid, {"error", "done"})["error"]


# ---------------------------------------------------------------- penulisan ulang
def test_token_lama_ditulis_ulang_saat_dipakai(make):
    m = make()
    c = web(m, "user_alice")
    m.repo.save_key("user_alice", "openrouter", legacy_token())
    assert m.keys_needing_rekey() == 1
    jid = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).json()["id"]
    wait_for(c, jid, {"done"})
    assert seen["key"] == KEY
    row = stored(m, "user_alice")
    assert row.startswith(m.cipher.current_prefix) and m.keys_needing_rekey() == 0
    assert m.cipher.decrypt(row, m._aad("user_alice", "openrouter")) == KEY


def test_rekey_berkala_untuk_rotasi_dan_cas(make):
    m = make()
    for u in ("user_a", "user_b"):
        m.repo.save_key(u, "openrouter", legacy_token())
    m.repo.save_key("user_c", "openrouter", legacy_token(secret="rahasia-lain-yang-hilang-selamanya-000999"))  # tak terbaca
    assert m.keys_needing_rekey() == 3
    assert m.rekey_keys() == (2, 1)
    assert m.keys_needing_rekey() == 1  # sisanya tidak dirusak
    # rotasi: kunci utama diganti -> semua baris v2 lama ikut ditulis ulang oleh siklus pemeliharaan berkala
    m.cipher = KeyCipher([NEW, SECRET])
    assert m.keys_needing_rekey() == 3
    m.purge_idle_keys(interval=0)
    assert m.keys_needing_rekey() == 1  # tinggal yang memang tak terbaca
    assert m.cipher.decrypt(stored(m, "user_a"), m._aad("user_a", "openrouter")) == KEY
    # compare-and-swap: tidak menimpa bila ciphertext sudah berubah
    assert m.repo.swap_key_ciphertext("user_a", "openrouter", "bukan-token-sekarang", "x") is False
    assert stored(m, "user_a") != "x"


def test_rekey_tanpa_cipher_tidak_melakukan_apa_apa(make, tmp_path):
    m = JobManager(tmp_path / "x", runner=runner, stale_after=0)
    try:
        assert m.rekey_keys() == (0, 0) and m.keys_needing_rekey() == 0 and m.purge_idle_keys(interval=0) == 0
    finally:
        m.shutdown()


# ---------------------------------------------------------------- pemeriksaan ke penyedia
@pytest.fixture
def verify_on(monkeypatch):
    monkeypatch.setenv("MALAS_KEY_VERIFY", "1")


@pytest.mark.parametrize("status,want", [(200, "valid"), (204, "valid"), (401, "invalid"), (403, "unknown"),
                                         (404, "unknown"), (429, "unknown"), (500, "unknown"), (None, "unknown")])
def test_keycheck_memetakan_status(monkeypatch, verify_on, status, want):
    monkeypatch.setattr(keycheck, "_status", lambda url, key: status)
    assert keycheck.check("openrouter", KEY) == want


def test_keycheck_url_dikunci_dan_bisa_dimatikan(monkeypatch, verify_on):
    urls = []
    monkeypatch.setattr(keycheck, "_status", lambda url, key: urls.append(url) or 200)
    keycheck.check("openrouter", KEY)
    keycheck.check("kenari", KEY)
    assert urls == ["https://openrouter.ai/api/v1/key", "https://kenari.id/v1/models"]
    assert keycheck.check("tidak-ada", KEY) == "unknown" and len(urls) == 2
    monkeypatch.setenv("MALAS_KEY_VERIFY", "0")
    assert keycheck.check("openrouter", KEY) == "unknown" and len(urls) == 2  # mati: tanpa panggilan


def test_keycheck_tidak_mengikuti_redirect():
    assert keycheck._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.test/") is None


def test_put_key_ditolak_bila_penyedia_menyatakan_salah(make, monkeypatch):
    monkeypatch.setattr(keycheck, "check", lambda p, k: "invalid")
    m = make()
    c = web(m, "user_alice")
    r = c.put("/api/keys/openrouter", json={"api_key": KEY})
    assert r.status_code == 422 and KEY not in r.text and "ditolak penyedia" in r.text
    assert c.get("/api/keys").json()["keys"] == []


def test_put_key_status_valid_dan_tak_terverifikasi(make, monkeypatch):
    m = make()
    c = web(m, "user_alice")
    monkeypatch.setattr(keycheck, "check", lambda p, k: "valid")
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).json() == {"result": "saved"}
    monkeypatch.setattr(keycheck, "check", lambda p, k: "unknown")  # penyedia tak terjangkau: tetap boleh disimpan
    assert c.put("/api/keys/openrouter", json={"api_key": KEY}).json() == {"result": "saved_unverified"}


def test_job_save_key_ditolak_mengembalikan_kuota_dan_tidak_menyimpan(make, monkeypatch):
    m = make()
    c = web(m, "user_q", quota=1)
    monkeypatch.setattr(keycheck, "check", lambda p, k: "invalid")
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True})
    assert r.status_code == 422 and KEY not in r.text
    assert c.get("/api/keys").json()["keys"] == [] and c.get("/api/me").json()["quota"]["used"] == 0
    monkeypatch.setattr(keycheck, "check", lambda p, k: "valid")
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True})
    assert r.status_code == 202  # kuota utuh, key sah diterima
    wait_for(c, r.json()["id"], {"done"})
    with m.db.session() as s:
        assert s.scalar(select(dbmod.UserApiKey.ciphertext)).startswith("v2.")

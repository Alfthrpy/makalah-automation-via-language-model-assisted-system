"""Fase 3: login Clerk (JWT RS256 via JWKS), isolasi antar pengguna, dan kuota harian."""
import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from malas_api import app as appmod
from malas_api.app import create_app
from malas_api.auth import Authenticator, AuthError, authenticator_from_env, token_from_request
from malas_api.jobs import JobManager

ISS = "https://clerk.test"
AZP = "https://app.test"
BASE = {"judul": "Uji Auth", "mata_kuliah": "Uji", "penyusun": [{"nama": "Ani"}], "tahun": "2025"}
KEY = "sk-or-v1-RAHASIA1234567890abcdef"


def gen_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


PRIV, OTHER = gen_key(), gen_key()


class Stub:
    def __init__(self, key=PRIV.public_key(), error=None):
        self.key, self.error = key, error

    def get_signing_key_from_jwt(self, token):
        if self.error:
            raise self.error
        return type("K", (), {"key": self.key})()


def token(sub="user_1", *, key=PRIV, iss=ISS, azp=AZP, exp=300, alg="RS256", **extra):
    claims = {"sub": sub, "iss": iss, "exp": int(time.time()) + exp, "iat": int(time.time()), **extra}
    if azp:
        claims["azp"] = azp
    return jwt.encode(claims, key, algorithm=alg)


def authn(**kw):
    return Authenticator(issuer=ISS, jwks=kw.pop("jwks", Stub()), authorized_parties=kw.pop("parties", [AZP]), **kw)


def ok_runner(job, progress, out, runtime=None):
    progress("input", "done")
    out.write_bytes(b"PK-docx")
    return {}


@pytest.fixture
def make(tmp_path):
    ms = []

    def _make(runner=ok_runner, auth="default", quota=0, **kw):
        m = JobManager(tmp_path, runner=runner, **kw)
        ms.append(m)
        a = authn() if auth == "default" else auth
        return m, a, quota

    yield _make
    for m in ms:
        m.shutdown()


def client(m, a, quota=0, tok=None):
    c = TestClient(create_app(m, hosted=False, auth=a, daily_quota=quota))
    if tok:
        c.headers["Authorization"] = f"Bearer {tok}"
    return c


def wait_status(c, jid, want, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        j = c.get(f"/api/jobs/{jid}").json()
        if j["status"] in want:
            return j
        time.sleep(0.02)
    raise AssertionError(j)


# ---------------------------------------------------------------- verifikasi token
def test_token_sah_mengembalikan_sub():
    assert authn().verify(token("user_abc")) == "user_abc"


@pytest.mark.parametrize("bad", [
    lambda: token(exp=-3600),                           # kedaluwarsa
    lambda: token(iss="https://evil.test"),             # issuer salah
    lambda: token(azp="https://evil.test"),             # origin tak diizinkan
    lambda: token(azp=None),                            # azp wajib bila daftar diisi
    lambda: token(key=OTHER),                           # tanda tangan kunci lain
    lambda: jwt.encode({"sub": "u", "iss": ISS, "exp": int(time.time()) + 99, "azp": AZP}, "x" * 40, algorithm="HS256"),
    lambda: "bukan.jwt.sama-sekali",
    lambda: "",
    lambda: "a" * 5000,
])
def test_token_tidak_sah_ditolak(bad):
    with pytest.raises(AuthError):
        authn().verify(bad())


def test_serangan_alg_none_dan_hs256_dengan_kunci_publik_ditolak():
    from cryptography.hazmat.primitives import serialization

    pub_pem = PRIV.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    none_tok = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': 'u', 'iss': ISS, 'exp': int(time.time()) + 99, 'azp': AZP})}."
    with pytest.raises(AuthError):
        authn().verify(none_tok)
    import hmac, hashlib  # noqa: E401 - HS256 ditandatangani dengan PEM kunci publik (algorithm confusion)
    head = b64({"alg": "HS256", "typ": "JWT"})
    body = b64({"sub": "u", "iss": ISS, "exp": int(time.time()) + 99, "azp": AZP})
    sig = base64.urlsafe_b64encode(hmac.new(pub_pem, f"{head}.{body}".encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
    with pytest.raises(AuthError):
        authn().verify(f"{head}.{body}.{sig}")


def test_kegagalan_jwks_menjadi_authkerror_bukan_500():
    with pytest.raises(AuthError):
        authn(jwks=Stub(error=jwt.PyJWKClientError("jaringan putus"))).verify(token())


def test_token_dari_header_atau_cookie_get_saja():
    assert token_from_request({"authorization": "Bearer abc"}, {}, "POST") == "abc"
    assert token_from_request({}, {"__session": "ck"}, "GET") == "ck"
    assert token_from_request({}, {"__session": "ck"}, "POST") is None  # cookie tidak cukup untuk mengubah data
    assert token_from_request({"authorization": "Basic xx"}, {}, "DELETE") is None


def test_authenticator_dari_env():
    assert authenticator_from_env({}) is None
    a = authenticator_from_env({"CLERK_ISSUER": "https://x.clerk.accounts.dev/", "CLERK_AUTHORIZED_PARTIES": "https://a, https://b"})
    assert a.issuer == "https://x.clerk.accounts.dev" and a.authorized_parties == ["https://a", "https://b"]
    b = authenticator_from_env({"CLERK_JWKS_URL": "https://y.clerk.accounts.dev/.well-known/jwks.json"})
    assert b.issuer == "https://y.clerk.accounts.dev"  # diturunkan dari URL JWKS


def test_jwks_sungguhan_lewat_http_lokal(monkeypatch):
    """PyJWKClient mengunduh JWKS dari server HTTP, memilih kunci lewat `kid`, dan memverifikasi token."""
    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(PRIV.public_key()))
    jwk.update(kid="k1", use="sig", alg="RS256")
    body = json.dumps({"keys": [jwk]}).encode()

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        for v in ("NO_PROXY", "no_proxy"):
            monkeypatch.setenv(v, "127.0.0.1,localhost")
        a = authenticator_from_env({"CLERK_ISSUER": base})
        good = jwt.encode({"sub": "user_9", "iss": base, "exp": int(time.time()) + 99}, PRIV, algorithm="RS256", headers={"kid": "k1"})
        assert a.verify(good) == "user_9"
        forged = jwt.encode({"sub": "user_9", "iss": base, "exp": int(time.time()) + 99}, OTHER, algorithm="RS256", headers={"kid": "k1"})
        with pytest.raises(AuthError):
            a.verify(forged)
        unknown = jwt.encode({"sub": "u", "iss": base, "exp": int(time.time()) + 99}, PRIV, algorithm="RS256", headers={"kid": "zzz"})
        with pytest.raises(AuthError):
            a.verify(unknown)
    finally:
        srv.shutdown()


def test_auth_wajib_tanpa_konfigurasi_menolak_start(make, monkeypatch):
    m, _, _ = make(auth=None)
    monkeypatch.setenv("MALAS_AUTH_REQUIRED", "1")
    with pytest.raises(RuntimeError):
        create_app(m, hosted=False)


# ---------------------------------------------------------------- akses & isolasi
def test_tanpa_login_hanya_jalur_publik(make):
    m, a, _ = make()
    c = client(m, a)
    assert c.get("/healthz").text == "ok"
    assert c.get("/").status_code == 404  # UI ada di apps/web, bukan di API
    cfg = c.get("/api/config").json()
    assert cfg["auth"] == {"mode": "clerk", "required": True} and cfg["active_job"] is None
    for method, path in [("get", "/api/jobs"), ("post", "/api/jobs"), ("get", "/api/me"), ("get", "/api/keys"),
                         ("get", "/api/jobs/" + "0" * 32), ("delete", "/api/jobs/" + "0" * 32)]:
        r = getattr(c, method)(path)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", (method, path)
    r = c.get("/api/jobs", headers={"Authorization": "Bearer " + token(exp=-999)})
    assert r.status_code == 401
    assert "set-cookie" not in c.get("/api/config").headers  # mode Clerk tidak menerbitkan cookie sesi


def test_dua_pengguna_terisolasi_dan_pemilik_adalah_sub(make):
    m, a, _ = make()
    alice, bob = client(m, a, tok=token("user_alice")), client(m, a, tok=token("user_bob"))
    jid = alice.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
    wait_status(alice, jid, {"done"})
    assert m.get(jid)["owner"] == "user_alice"
    assert [j["id"] for j in alice.get("/api/jobs").json()] == [jid]
    assert bob.get("/api/jobs").json() == []
    assert bob.get(f"/api/jobs/{jid}").status_code == 404
    assert bob.get(f"/api/jobs/{jid}/download").status_code == 404
    assert bob.delete(f"/api/jobs/{jid}").status_code == 404
    assert alice.get("/api/me").json()["id"] == "user_alice"
    assert alice.get("/api/config").json()["active_job"] is None
    assert alice.get(f"/api/jobs/{jid}/download").content == b"PK-docx"


def test_cookie_session_hanya_untuk_get(make):
    m, a, _ = make()
    c = client(m, a)
    tok = token("user_c")
    jid = client(m, a, tok=tok).post("/api/jobs", json={**BASE, "mock": True}).json()["id"]
    wait_status(client(m, a, tok=tok), jid, {"done"})
    c.cookies.set("__session", tok)
    assert c.get(f"/api/jobs/{jid}/download").content == b"PK-docx"  # tautan unduh <a href> tanpa header
    assert c.post("/api/jobs", json={**BASE, "mock": True}).status_code == 401  # CSRF: cookie tidak cukup
    assert c.delete(f"/api/jobs/{jid}").status_code == 401


def test_key_tersimpan_terpisah_per_pengguna_clerk(make):
    from malas_api.crypto import KeyCipher

    m, a, _ = make(cipher=KeyCipher(["rahasia-server-uji-yang-cukup-panjang-123456"]))
    alice, bob = client(m, a, tok=token("user_alice")), client(m, a, tok=token("user_bob"))
    assert alice.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY, "save_key": True}).status_code == 202
    assert [k["provider"] for k in alice.get("/api/keys").json()["keys"]] == ["openrouter"]
    assert bob.get("/api/keys").json()["keys"] == []
    assert bob.post("/api/jobs", json={**BASE, "provider": "openrouter", "use_saved_key": True}).status_code == 422


# ---------------------------------------------------------------- kuota
def test_kuota_harian_menghitung_job_nyata_saja(make):
    m, a, _ = make()
    c = client(m, a, quota=2, tok=token("user_q"))
    assert c.get("/api/me").json()["quota"]["remaining"] == 2
    for _ in range(2):
        r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY})
        assert r.status_code == 202
        wait_status(c, r.json()["id"], {"done"})
    r = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY})
    assert r.status_code == 429 and "Kuota harian" in r.json()["detail"] and KEY not in r.text
    me = c.get("/api/me").json()["quota"]
    assert (me["limit"], me["used"], me["remaining"]) == (2, 2, 0) and me["resets_at"]
    assert c.get("/api/config").json()["daily_quota"] == 2
    mock = c.post("/api/jobs", json={**BASE, "mock": True})
    assert mock.status_code == 202  # Mode uji gratis
    wait_status(c, mock.json()["id"], {"done"})
    other = client(m, a, quota=2, tok=token("user_lain"))  # kuota per pengguna
    assert other.get("/api/me").json()["quota"]["used"] == 0


def test_kuota_kembali_bila_job_antre_dibatalkan(make):
    gate = threading.Event()

    def slow(job, progress, out, runtime=None):
        gate.wait(5)
        out.write_bytes(b"x")
        return {}

    m, a, _ = make(runner=slow)
    c = client(m, a, quota=2, tok=token("user_r"))
    first = c.post("/api/jobs", json={**BASE, "mock": True}).json()["id"]  # mengisi pekerja
    wait_status(c, first, {"running"})
    # hosted=False: boleh antre lebih dari satu; job nyata kedua antre di belakang
    q = c.post("/api/jobs", json={**BASE, "provider": "openrouter", "api_key": KEY}).json()["id"]
    assert c.get("/api/me").json()["quota"]["used"] == 1
    assert c.delete(f"/api/jobs/{q}").json() == {"result": "cancelled"}
    assert c.get("/api/me").json()["quota"]["used"] == 0  # dikembalikan
    gate.set()


def test_kuota_lanjutan_tidak_dihitung_dan_reset_besok(make, monkeypatch):
    from malas import checkpoint
    from malas.crews.models.TaskOutput import Bab, ContentText, Makalah, ReferenceItem, SubBab

    fail = {"on": True}

    def runner(job, progress, out, runtime=None):
        if fail["on"]:
            s = Makalah(judul="J", bab={"I": Bab(judul="B", subbab=[SubBab(judul="1.1", content=[ContentText(isi="x")])])},
                        daftar_pustaka=[ReferenceItem(title="t", authors=["A B"], year=2024)])
            checkpoint.save(out.parent / "checkpoint.json", s, {}, {})
            progress("tulis", "running")
            raise RuntimeError("putus")
        out.write_bytes(b"PK")
        return {}

    m, a, _ = make(runner=runner)
    c = client(m, a, quota=1, tok=token("user_s"))
    body = {**BASE, "provider": "openrouter", "api_key": KEY}
    jid = c.post("/api/jobs", json=body).json()["id"]
    wait_status(c, jid, {"error"})
    assert c.post("/api/jobs", json=body).status_code == 429  # kuota 1 habis
    fail["on"] = False
    r = c.post("/api/jobs", json={**body, "resume_from": jid})  # lanjutan: gratis
    assert r.status_code == 202
    wait_status(c, r.json()["id"], {"done"})
    monkeypatch.setattr(appmod, "quota_day", lambda: "2099-01-01")  # hari berganti
    assert c.get("/api/me").json()["quota"]["used"] == 0
    assert c.post("/api/jobs", json=body).status_code == 202


def test_kuota_konsumsi_paralel_tepat_sebatas_limit(make):
    m, _, _ = make()
    wins, lock = [], threading.Lock()

    def go():
        r = m.consume_quota("user_p", "2030-01-01", 3)
        with lock:
            wins.append(r)

    ts = [threading.Thread(target=go) for _ in range(12)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert wins.count(True) == 3 and m.quota_used("user_p", "2030-01-01") == 3
    m.refund_quota("user_p", "2030-01-01")
    assert m.quota_used("user_p", "2030-01-01") == 2


def test_mode_anonim_tetap_berfungsi_tanpa_clerk(make):
    m, _, _ = make(auth=None)
    c = TestClient(create_app(m, hosted=False, auth=None))
    cfg = c.get("/api/config").json()
    assert cfg["auth"] == {"mode": "anonymous", "required": False}
    r = c.post("/api/jobs", json={**BASE, "mock": True})
    assert r.status_code == 202 and "malas_sid" in c.cookies
    assert c.get("/api/me").json()["mode"] == "anonymous"

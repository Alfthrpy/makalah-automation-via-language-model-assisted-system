"""Enkripsi API key yang disimpan pengguna (opsional, opsi 3b).

Rahasia server: env MALAS_SECRET_KEY (string acak panjang, >= 32 karakter, tidak monoton). Tanpa itu fitur simpan-key mati.

Format token:
  v2.<kid>.<b64url(nonce || ciphertext+tag)>   AES-256-GCM. AAD = identitas pemilik + penyedia (lihat jobs._aad),
                                              jadi ciphertext yang disalin ke baris/pengguna lain TIDAK bisa didekripsi.
                                              `kid` = sidik jari kunci; tahu persis kunci mana yang dipakai tiap baris.
  gAAAA...                                    format lama (Fernet, tanpa AAD). Masih bisa DIBACA, dan ditulis ulang
                                              ke v2 secara malas (saat dipakai) dan berkala (JobManager.rekey_keys).

Rotasi: pasang rahasia baru di MALAS_SECRET_KEY dan yang lama di MALAS_SECRET_KEY_OLD (koma). Baris lama ditulis ulang
otomatis ke kunci baru; bila `keys_needing_rekey()` = 0, rahasia lama aman dibuang.
"""
import base64
import hashlib
import logging
import os
import secrets as _secrets
from typing import Dict, List, Optional

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

log = logging.getLogger("malas.crypto")

MIN_SECRET_LEN = 32
MIN_DISTINCT_CHARS = 12  # tolak rahasia monoton seperti "aaaa..." / "1234123412..."
_SALT = b"malas-user-api-key-v1"
_V2 = "v2"


class CryptoError(Exception):
    pass


def _derive(secret: str, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=info).derive(secret.encode())


def _fernet(secret: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(_derive(secret, b"fernet")))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class KeyCipher:
    def __init__(self, secrets: List[str]):
        self._legacy = MultiFernet([_fernet(s) for s in secrets])  # hanya untuk membaca token lama
        self._aes: Dict[str, AESGCM] = {}
        self._kids: List[str] = []
        for s in secrets:
            key = _derive(s, b"aes256gcm-v2")
            kid = hashlib.sha256(key).hexdigest()[:8]
            self._aes.setdefault(kid, AESGCM(key))
            self._kids.append(kid)
        self.primary_kid = self._kids[0]

    def encrypt(self, plaintext: str, aad: bytes = b"") -> str:
        nonce = _secrets.token_bytes(12)
        ct = self._aes[self.primary_kid].encrypt(nonce, plaintext.encode(), aad)
        return f"{_V2}.{self.primary_kid}.{_b64(nonce + ct)}"

    def decrypt(self, token: str, aad: bytes = b"") -> str:
        fail = CryptoError("Key tersimpan tidak bisa didekripsi (rahasia server berubah?).")
        try:
            if token.startswith(_V2 + "."):
                _, kid, body = token.split(".", 2)
                aes = self._aes.get(kid)
                if aes is None:
                    raise fail
                raw = _unb64(body)
                return aes.decrypt(raw[:12], raw[12:], aad).decode()
            return self._legacy.decrypt(token.encode()).decode()
        except (InvalidTag, InvalidToken, ValueError, UnicodeDecodeError) as e:  # ValueError: token rusak
            raise fail from e

    def needs_rekey(self, token: str) -> bool:
        """True bila token bukan v2 atau memakai kunci selain yang utama saat ini."""
        return not token.startswith(f"{_V2}.{self.primary_kid}.")

    @property
    def current_prefix(self) -> str:
        return f"{_V2}.{self.primary_kid}."


def _usable(secret: str, name: str) -> bool:
    if len(secret) < MIN_SECRET_LEN:
        log.warning("%s kurang dari %d karakter; diabaikan.", name, MIN_SECRET_LEN)
        return False
    if len(set(secret)) < MIN_DISTINCT_CHARS:
        log.warning("%s terlalu monoton (kurang dari %d karakter berbeda); diabaikan.", name, MIN_DISTINCT_CHARS)
        return False
    return True


def cipher_from_env(env=os.environ) -> Optional[KeyCipher]:
    secret = (env.get("MALAS_SECRET_KEY") or "").strip()
    if not secret:
        return None
    if not _usable(secret, "MALAS_SECRET_KEY"):
        return None
    old = [s.strip() for s in (env.get("MALAS_SECRET_KEY_OLD") or "").split(",") if s.strip()]
    return KeyCipher([secret, *[s for s in old if _usable(s, "MALAS_SECRET_KEY_OLD")]])

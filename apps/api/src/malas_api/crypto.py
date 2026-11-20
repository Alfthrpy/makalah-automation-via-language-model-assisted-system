"""Enkripsi API key yang disimpan pengguna (opsional, opsi 3b).

Rahasia server: env MALAS_SECRET_KEY (string acak panjang, >= 32 karakter). Tanpa itu fitur simpan-key mati.
Fernet (AES-128-CBC + HMAC). Kunci diturunkan dengan HKDF dari rahasia. MALAS_SECRET_KEY_OLD (koma) =
rahasia lama yang masih boleh MEMBACA agar rotasi tidak merusak data.
"""
import base64
import os
from typing import List, Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MIN_SECRET_LEN = 32


class CryptoError(Exception):
    pass


def _fernet(secret: str) -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"malas-user-api-key-v1", info=b"fernet").derive(secret.encode())
    return Fernet(base64.urlsafe_b64encode(key))


class KeyCipher:
    def __init__(self, secrets: List[str]):
        self._mf = MultiFernet([_fernet(s) for s in secrets])

    def encrypt(self, plaintext: str) -> str:
        return self._mf.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._mf.decrypt(token.encode()).decode()
        except InvalidToken as e:
            raise CryptoError("Key tersimpan tidak bisa didekripsi (rahasia server berubah?).") from e


def cipher_from_env(env=os.environ) -> Optional[KeyCipher]:
    secret = (env.get("MALAS_SECRET_KEY") or "").strip()
    if len(secret) < MIN_SECRET_LEN:
        return None
    old = [s.strip() for s in (env.get("MALAS_SECRET_KEY_OLD") or "").split(",") if len(s.strip()) >= MIN_SECRET_LEN]
    return KeyCipher([secret, *old])

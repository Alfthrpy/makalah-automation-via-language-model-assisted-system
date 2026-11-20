"""Autentikasi Clerk: verifikasi JWT sesi (RS256) lewat JWKS.

Env (aktif bila salah satu terisi):
  CLERK_ISSUER             mis. https://xxx.clerk.accounts.dev   (JWKS = <issuer>/.well-known/jwks.json)
  CLERK_JWKS_URL           bila JWKS berada di alamat lain
  CLERK_AUTHORIZED_PARTIES koma; origin yang boleh (klaim `azp`), mis. https://malas.netlify.app,http://localhost:5173
Token dibaca dari `Authorization: Bearer ...`; untuk GET (mis. tautan unduh) juga dari cookie `__session` milik Clerk.
Metode yang mengubah data HANYA menerima header Authorization (cookie tidak cukup) agar kebal CSRF.
"""
import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Protocol

import jwt

log = logging.getLogger("malas.auth")
MAX_TOKEN = 4096
SESSION_COOKIE = "__session"


class AuthError(Exception):
    pass


class KeyResolver(Protocol):
    def get_signing_key_from_jwt(self, token: str): ...  # objek dengan atribut `.key`


@dataclass
class Authenticator:
    issuer: Optional[str]
    jwks: KeyResolver
    authorized_parties: Optional[List[str]] = None
    leeway: int = 10  # detik toleransi selisih jam

    def verify(self, token: str) -> str:
        """Kembalikan `sub` (id pengguna Clerk) bila token sah; AuthError bila tidak."""
        if not token or len(token) > MAX_TOKEN:
            raise AuthError("token tidak valid")
        try:
            key = self.jwks.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, key, algorithms=["RS256"], issuer=self.issuer, leeway=self.leeway,
                options={"require": ["exp", "sub"], "verify_aud": False, "verify_iss": bool(self.issuer)},
            )
        except (jwt.PyJWTError, KeyError, ValueError) as e:  # PyJWKClientError turunan PyJWTError
            raise AuthError(e.__class__.__name__) from e
        azp = claims.get("azp")
        if self.authorized_parties and azp not in self.authorized_parties:
            raise AuthError("azp tidak diizinkan")
        sub = claims["sub"]
        if not isinstance(sub, str) or not sub or len(sub) > 190:
            raise AuthError("sub tidak valid")
        return sub


def token_from_request(headers, cookies, method: str) -> Optional[str]:
    h = headers.get("authorization", "")
    if h[:7].lower() == "bearer ":
        return h[7:].strip() or None
    if method in {"GET", "HEAD"}:  # cookie hanya untuk pembacaan (tautan unduh)
        return cookies.get(SESSION_COOKIE) or None
    return None


def authenticator_from_env(env=os.environ) -> Optional[Authenticator]:
    issuer = (env.get("CLERK_ISSUER") or "").strip().rstrip("/") or None
    jwks_url = (env.get("CLERK_JWKS_URL") or "").strip()
    if not issuer and not jwks_url:
        return None
    jwks_url = jwks_url or f"{issuer}/.well-known/jwks.json"
    if not issuer and jwks_url.endswith("/.well-known/jwks.json"):
        issuer = jwks_url[: -len("/.well-known/jwks.json")]  # Clerk: issuer = host JWKS
    parties = [x.strip() for x in (env.get("CLERK_AUTHORIZED_PARTIES") or "").split(",") if x.strip()]
    client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=10)
    return Authenticator(issuer=issuer, jwks=client, authorized_parties=parties or None)

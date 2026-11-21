"""Verifikasi webhook Clerk (Svix): tanda tangan HMAC-SHA256 atas `id.timestamp.body`.

Env CLERK_WEBHOOK_SECRET (format `whsec_<base64>`, dari dashboard Clerk -> Webhooks). Tanpa itu endpoint tidak aktif.
Kami memverifikasi sendiri (tanpa dependensi baru): header svix-id, svix-timestamp, svix-signature ("v1,<b64> v1,<b64>").
"""
import base64
import binascii
import hashlib
import hmac
import time
from typing import Mapping, Optional

TOLERANCE = 300  # detik; menolak replay lama


class WebhookError(Exception):
    pass


def secret_from_env(env) -> Optional[bytes]:
    raw = (env.get("CLERK_WEBHOOK_SECRET") or "").strip()
    if not raw:
        return None
    raw = raw[len("whsec_"):] if raw.startswith("whsec_") else raw
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as e:
        raise RuntimeError("CLERK_WEBHOOK_SECRET tidak valid (harus whsec_<base64>).") from e
    if len(key) < 16:
        raise RuntimeError("CLERK_WEBHOOK_SECRET terlalu pendek.")
    return key


def verify(secret: bytes, headers: Mapping[str, str], body: bytes, now: Optional[float] = None) -> None:
    """Lolos diam-diam bila sah; WebhookError bila tidak."""
    msg_id = headers.get("svix-id", "")
    ts = headers.get("svix-timestamp", "")
    sigs = headers.get("svix-signature", "")
    if not msg_id or not ts or not sigs or len(sigs) > 2000:
        raise WebhookError("header tidak lengkap")
    try:
        tsv = int(ts)
    except ValueError as e:
        raise WebhookError("timestamp tidak valid") from e
    if abs((now if now is not None else time.time()) - tsv) > TOLERANCE:
        raise WebhookError("timestamp di luar toleransi")
    expected = base64.b64encode(hmac.new(secret, f"{msg_id}.{ts}.".encode() + body, hashlib.sha256).digest()).decode()
    for part in sigs.split():
        ver, _, sig = part.partition(",")
        if ver == "v1" and hmac.compare_digest(sig, expected):
            return
    raise WebhookError("tanda tangan tidak cocok")

"""S3Storage diuji dengan klien S3 palsu di memori (R2 asli belum dicoba: tidak ada kredensial di sandbox)."""
import pytest
from malas_api.storage import R2_VARS, S3Storage, storage_from_env


class _NoSuchKey(Exception):
    pass


class FakeS3:
    class exceptions:
        NoSuchKey = _NoSuchKey

    def __init__(self):
        self.objs = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objs[(Bucket, Key)] = (Body, ContentType)

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objs:
            raise _NoSuchKey()
        body = self.objs[(Bucket, Key)][0]
        return {"Body": type("B", (), {"read": lambda self_: body})()}

    def delete_object(self, Bucket, Key):
        self.objs.pop((Bucket, Key), None)


def test_roundtrip_timpa_dan_hapus():
    c = FakeS3()
    s = S3Storage(c, "bkt")
    assert s.get("a" * 32) is None
    s.put("a" * 32, b"PK1")
    s.put("a" * 32, b"PK2")
    assert s.get("a" * 32) == b"PK2"
    assert ("bkt", "jobs/" + "a" * 32 + ".docx") in c.objs and "wordprocessingml" in c.objs[("bkt", "jobs/" + "a" * 32 + ".docx")][1]
    s.delete("a" * 32)
    s.delete("a" * 32)  # idempoten
    assert s.get("a" * 32) is None


def test_env_kosong_pakai_db_sebagian_ditolak_lengkap_membuat_klien():
    assert storage_from_env({}) is None
    with pytest.raises(RuntimeError, match="R2_BUCKET"):
        storage_from_env({"R2_ENDPOINT_URL": "https://x.r2.cloudflarestorage.com", "R2_ACCESS_KEY_ID": "a", "R2_SECRET_ACCESS_KEY": "b"})
    full = dict(zip(R2_VARS, ["https://x.r2.cloudflarestorage.com", "bkt", "id", "secret"]))
    st = storage_from_env(full)
    assert isinstance(st, S3Storage)  # klien dibuat tanpa koneksi jaringan

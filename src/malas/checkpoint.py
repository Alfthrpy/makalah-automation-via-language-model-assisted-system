"""Checkpoint pembuatan makalah agar job gagal bisa dilanjutkan tanpa mengulang dari awal.

Disimpan sebagai JSON di folder job: state makalah (outline, referensi, isi sub-bab yang sudah jadi),
penghitung token, dan statistik. TIDAK berisi API key.
"""
import json
import os
from pathlib import Path
from typing import Optional

from malas.crews.models.TaskOutput import Makalah

VERSION = 1


def meta_of(state: Makalah) -> dict:
    total = sum(len(b.subbab) for b in state.bab.values())
    done = sum(1 for b in state.bab.values() for s in b.subbab if s.content)
    return {"outline": bool(state.bab and state.daftar_pustaka), "done": done, "total": total}


def save(path: Path, state: Makalah, usage: dict, stats: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload = {"version": VERSION, "meta": meta_of(state), "state": state.model_dump(mode="json"),
               "usage": usage, "stats": stats}
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def load(path: Path) -> Optional[dict]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != VERSION:
            return None
        Makalah.model_validate(data["state"])  # pastikan masih sesuai skema
        return data
    except (OSError, ValueError, KeyError):
        return None


def read_meta(path: Path) -> Optional[dict]:
    data = load(path)
    return data["meta"] if data else None

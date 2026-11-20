"""Benchmark pencarian referensi (RC-05 / S14) dengan jaringan NYATA, tanpa LLM.

Untuk tiap judul uji: rencana query dari `heuristic_plan` (tanpa LLM) -> `search_references` dengan klien sungguhan
(`refsearch.make_client`) pada sub-bab standar (1.1 + 2.1..2.5), lalu melaporkan jumlah referensi, rasio bahasa
Indonesia, jumlah karya "landmark" (cited_by >= 300), rentang tahun, sumber, durasi, dan jumlah HTTP.

Skrip ini sengaja hanya memakai API publik refsearch yang ada SEBELUM dan SESUDAH S14 (`heuristic_plan`,
`search_references` tanpa `k` eksplisit) agar baseline dan hasil sesudah perubahan dapat dibandingkan apa adanya.
Bahasa & jumlah kutipan tidak ada di `ReferenceItem`, jadi dibaca dari kandidat lewat pembungkus `orchestrator.choose`.

    PYTHONPATH=packages/engine/src python packages/engine/scripts/bench_refsearch.py --out hasil.json

Kesopanan API: email kontak dikosongkan (tanpa data pribadi), cache disk baru & kosong per run (perbandingan adil),
jeda antar judul, dan peringatan bila total request melewati --max-http.
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

os.environ["MALAS_CONTACT_EMAIL"] = ""  # jangan kirim email/data pribadi ke API

from malas.refsearch import heuristic_plan, make_client, orchestrator, search_references
from malas.refsearch.rank import ckey

JUDUL_UJI = [
    "Penerapan Gamifikasi untuk Meningkatkan Motivasi Belajar Bahasa Arab",
    "Pengaruh Media Sosial terhadap Kesehatan Mental Remaja",
    "Analisis Hukum Pidana terhadap Tindak Pidana Korupsi di Indonesia",
    "Penerapan Machine Learning untuk Deteksi Penipuan Transaksi Keuangan",
    "Strategi Pemasaran Digital untuk UMKM di Era Ekonomi Syariah",
    "Sejarah Kerajaan Majapahit dan Pengaruhnya terhadap Nusantara",
]
SUBBAB = [
    "1.1 Latar Belakang",
    "2.1 Landasan Teori",
    "2.2 Tinjauan Penelitian Terdahulu",
    "2.3 Analisis dan Pembahasan",
    "2.4 Studi Kasus",
    "2.5 Tantangan dan Implikasi",
]
LANDMARK_CITES = 300
# karya dasar yang diharapkan (pola judul, huruf kecil) per indeks judul uji
HARAPAN = {
    0: {"Ryan & Deci 2000 (SDT)": r"self-determination theory|intrinsic and extrinsic motivations",
        "Deterding dkk. 2011": r"game design elements to gamefulness"},
}
# penanda judul berbahasa Indonesia (metrik sekunder; Crossref tidak memberi bahasa)
_ID_WORDS = re.compile(r"\b(yang|dan|untuk|pada|dalam|terhadap|dengan|di|dari|oleh|sebagai|pengaruh|penerapan|"
                       r"analisis|siswa|peserta|didik|pembelajaran|melalui|berbasis)\b", re.IGNORECASE)


def _id_by_title(title: str) -> bool:
    return len(_ID_WORDS.findall(title or "")) >= 2


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="berkas JSON hasil")
    ap.add_argument("--label", default="", help="label run, mis. baseline / after")
    ap.add_argument("--judul", action="append", help="judul (boleh diulang); default 6 judul uji")
    ap.add_argument("--cache-dir", help="folder cache; default: folder sementara BARU (tanpa cache lama)")
    ap.add_argument("--pause", type=float, default=2.0, help="jeda antar judul (detik)")
    ap.add_argument("--max-http", type=int, default=200, help="batas sopan total request (hanya peringatan)")
    a = ap.parse_args()

    cache = Path(a.cache_dir) if a.cache_dir else Path(tempfile.mkdtemp(prefix="bench-refsearch-"))
    client = make_client(cache_dir=cache)
    seen = {}  # ckey -> kandidat terpilih (punya language & cited_by)
    asli = orchestrator.choose

    def choose_tercatat(*args, **kw):
        picked = asli(*args, **kw)
        for c in picked:
            seen[ckey(c)] = c
        return picked

    orchestrator.choose = choose_tercatat
    hasil, total_t0 = [], time.time()
    for i, judul in enumerate(a.judul or JUDUL_UJI):
        if i:
            time.sleep(a.pause)
        seen.clear()
        plan = heuristic_plan(judul, SUBBAB)
        t0, calls0, hits0 = time.time(), client.calls, client.cache_hits
        refs, rep = search_references(plan, judul, client)
        dt = time.time() - t0
        rows = []
        for r in refs:
            c = seen.get(f"doi:{r.doi}" if r.doi else None) or next(
                (v for v in seen.values() if v.title == r.title), None)
            rows.append({
                "year": r.year, "cited_by": getattr(c, "cited_by", None), "language": getattr(c, "language", None),
                "id_by_title": _id_by_title(r.title), "source": r.source, "title": r.title, "doi": r.doi,
                "sections": r.sections,
            })
        n = len(rows)
        n_id = sum(1 for x in rows if x["language"] == "id")
        n_lang = sum(1 for x in rows if x["language"])
        n_idt = sum(1 for x in rows if x["id_by_title"])
        landmarks = [x for x in rows if (x["cited_by"] or 0) >= LANDMARK_CITES]
        years = [x["year"] for x in rows if x["year"]]
        harapan = {nama: any(re.search(pola, x["title"].lower()) for x in rows)
                   for nama, pola in HARAPAN.get(i, {}).items()} if not a.judul else {}
        item = {
            "judul": judul,
            "plan": [{"section": p.section, "q_en": p.q_en, "q_id": p.q_id, "indo": p.indo,
                      **{f: getattr(p, f) for f in ("role", "landmark_terms") if hasattr(p, f)}} for p in plan],
            "n_refs": n,
            "lang_id": n_id, "lang_known": n_lang,
            "ratio_id_lang": round(n_id / n, 3) if n else None,
            "ratio_id_title": round(n_idt / n, 3) if n else None,
            "landmark_count": len(landmarks),
            "landmarks": [f'{x["cited_by"]} | {x["year"]} | {x["title"][:90]}' for x in landmarks],
            "year_min": min(years) if years else None, "year_max": max(years) if years else None,
            "by_source": rep.get("by_source", {}),
            "per_section": rep.get("per_section", {}),
            "sections_without_refs": rep.get("sections_without_refs", []),
            "duration_s": round(dt, 1), "http": client.calls - calls0, "cache_hits": client.cache_hits - hits0,
            "harapan_landmark": harapan,
            "report_extra": {k: rep[k] for k in ("language_ratio", "landmark_count", "k_per_section") if k in rep},
            "refs": rows,
        }
        hasil.append(item)
        print(f"== {judul}\n   ref {n} | id(lang) {n_id}/{n} | id(judul) {n_idt}/{n} | landmark {len(landmarks)} | "
              f"tahun {item['year_min']}-{item['year_max']} | sumber {item['by_source']} | HTTP {item['http']} | "
              f"{dt:.1f}s {('| harapan ' + json.dumps(harapan, ensure_ascii=False)) if harapan else ''}")
    out = {
        "label": a.label, "tanggal": time.strftime("%Y-%m-%d %H:%M:%S"), "subbab": SUBBAB,
        "landmark_cites": LANDMARK_CITES, "total_http": client.calls, "total_cache_hits": client.cache_hits,
        "total_duration_s": round(time.time() - total_t0, 1),
        "diagnostik": dict(sorted(client.stats.items())),
        "catatan": "rencana dari heuristic_plan (tanpa LLM); email kontak kosong; cache baru per run",
        "judul": hasil,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"TOTAL HTTP {client.calls} (cache {client.cache_hits}) | {out['total_duration_s']}s | diag {out['diagnostik']}")
    if client.calls > a.max_http:
        print(f"PERINGATAN: total request {client.calls} > {a.max_http}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

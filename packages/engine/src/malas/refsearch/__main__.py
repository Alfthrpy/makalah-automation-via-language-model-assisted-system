"""Uji pencarian referensi tanpa LLM dan tanpa menjalankan seluruh pipeline.

    python -m malas.refsearch                         # 8 topik uji lintas bidang
    python -m malas.refsearch --judul "Akuntansi Syariah pada UMKM" --fulltext
    python -m malas.refsearch --json hasil.json       # simpan hasil lengkap
    MALAS_CONTACT_EMAIL=anda@mail.com MALAS_OPENALEX_API_KEY=... python -m malas.refsearch

Mencetak per topik: jumlah sub-bab yang mendapat >= 2 referensi, % beserta abstrak, % beserta PDF OA yang sudah
diketahui, rincian per sumber, jumlah request HTTP & waktu. Dengan --fulltext juga mengukur hit-rate full-text.
"""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from malas.fulltext import FullTextStore
from malas.refsearch import heuristic_plan, make_client, search_references

TOPIK_UJI = [
    "Penerapan Hukum Pidana dalam KUHP Baru di Indonesia",
    "Metode Tafsir Al-Qur'an Kontemporer",
    "Fisioterapi pada Pasien Pasca Stroke",
    "Akuntansi Syariah pada Usaha Mikro Kecil dan Menengah",
    "Sejarah Kerajaan Majapahit dan Pengaruhnya",
    "Pengaruh Budaya K-Pop terhadap Perilaku Remaja",
    "Machine Learning untuk Sistem Rekomendasi",
    "Kebijakan Pajak untuk UMKM di Indonesia",
]
SUBBAB = ["1.1 Latar Belakang", "2.1 Landasan Teori", "2.2 Analisis dan Pembahasan", "2.3 Studi Kasus"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judul", action="append", help="judul makalah (boleh diulang); default: 8 topik uji")
    ap.add_argument("--subbab", action="append", help="sub-bab (boleh diulang); default: 4 sub-bab standar")
    ap.add_argument("--k", type=int, default=2, help="referensi per sub-bab")
    ap.add_argument("--fulltext", action="store_true", help="ukur juga hit-rate full-text (mengunduh PDF)")
    ap.add_argument("--no-cache", action="store_true", help="jangan pakai cache disk")
    ap.add_argument("--json", metavar="FILE", help="simpan hasil lengkap ke file JSON")
    a = ap.parse_args()

    judul_list = a.judul or TOPIK_UJI
    subbab = a.subbab or SUBBAB
    tmp = tempfile.mkdtemp(prefix="refsearch-") if a.no_cache else None
    client = make_client(cache_dir=Path(tmp) if tmp else None) if a.no_cache else make_client()
    dump, tot = [], {"sec": 0, "ok": 0, "refs": 0, "abs": 0, "oa": 0, "ft": 0}
    for judul in judul_list:
        t0, calls0 = time.time(), client.calls
        refs, rep = search_references(heuristic_plan(judul, subbab), judul, client, k=a.k)
        dt = time.time() - t0
        ok = sum(1 for n in rep["per_section"].values() if n >= a.k)
        n_abs = sum(1 for r in refs if r.excerpt)
        n_oa = sum(1 for r in refs if r.oa_pdf_url)
        ft = ""
        if a.fulltext and refs:
            store = FullTextStore()
            hit = store.load(refs, Path(tmp or ".cache/fulltext-test"))
            tot["ft"] += hit
            ft = f" | full-text {hit}/{len(refs)}"
        tot["sec"] += len(rep["per_section"]); tot["ok"] += ok; tot["refs"] += len(refs)
        tot["abs"] += n_abs; tot["oa"] += n_oa
        print(f"\n== {judul}\n   sub-bab >=2 ref: {ok}/{len(rep['per_section'])} | ref: {len(refs)} | "
              f"abstrak {n_abs} | PDF-OA {n_oa}{ft} | sumber {rep['by_source']} | "
              f"HTTP {client.calls - calls0} | {dt:.1f}s")
        for r in refs:
            print(f"   - ({r.year}) {r.title[:90]} [{r.source}] {r.doi or r.link or ''}")
        for s in rep["sections_without_refs"]:
            print(f"   ! tanpa referensi: {s}")
        dump.append({"judul": judul, "report": rep, "refs": [r.model_dump() for r in refs]})
    pct = lambda x, y: f"{100 * x / y:.0f}%" if y else "-"
    print(f"\nRINGKASAN: sub-bab terpenuhi {tot['ok']}/{tot['sec']} ({pct(tot['ok'], tot['sec'])}) | "
          f"abstrak {pct(tot['abs'], tot['refs'])} | PDF-OA {pct(tot['oa'], tot['refs'])}"
          + (f" | full-text {pct(tot['ft'], tot['refs'])}" if a.fulltext else "")
          + f" | total HTTP {client.calls} (cache {client.cache_hits})")
    if a.json:
        Path(a.json).write_text(json.dumps(dump, ensure_ascii=False, indent=2, default=list), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

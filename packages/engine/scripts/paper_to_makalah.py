"""Ubah teks makalah (PDF hasil MALAS / template sejenis) menjadi JSON `Makalah` untuk benchmark lint.

Heuristik (best-effort, BUKAN impor .docx umum):
- teks dari ``pdftotext -layout`` (dijalankan otomatis bila masukan .pdf);
- bab: baris ``BAB I|II|III`` + baris judul berikutnya; sub-bab: baris berawalan ``1.1``/``2.3`` di kolom 0
  (judul tercetak dipertahankan apa adanya, mis. "2.1 2.1 Konsep" agar STR-001 dapat diuji);
- paragraf baru = baris berindentasi >=5 spasi; nomor halaman (baris angka/romawi saja) dibuang;
  pemenggalan kata "-" di akhir baris disambung; spasi ganda akibat rata kanan-kiri diringkas;
- butir ``1)``/``a)`` menjadi `ContentList`; sub-bab Rumusan Masalah/Tujuan/Manfaat/Saran -> ``kind="daftar"``;
- Daftar Pustaka -> `ReferenceItem` (authors "Family, I.", year, title, doi).

Data identitas (penyusun, NIM, dosen) TIDAK disalin. Pemakaian::

    python packages/engine/scripts/paper_to_makalah.py makalah.pdf /tmp/out/paper.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from malas.crews.models.TaskOutput import (
    Bab,
    ContentList,
    ContentText,
    Makalah,
    ReferenceItem,
    SubBab,
)

_BAB = re.compile(r"^\s*BAB\s+([IVX]+)\s*$")
_SUB = re.compile(r"^(\d+\.\d+)\s+\S")
_PAGE = re.compile(r"^\s*(?:\d{1,3}|[ivxlc]{1,6})\s*$")
_ITEM = re.compile(r"^\s*(?:\d{1,2}|[a-z])\)\s+")
_DP = re.compile(r"^\s*DAFTAR\s+PUSTAKA\s*$")
_DAFTAR_TITLES = ("rumusan masalah", "tujuan", "manfaat", "saran")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _join(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if out.endswith("-") and not out.endswith(" -"):
            out += s  # "Self-" + "Determination", "bersama-" + "sama"
        else:
            out = f"{out} {s}" if out else s
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def _content(lines: list[str]) -> list:
    """Baris isi satu sub-bab -> daftar ContentText/ContentList."""
    blocks: list = []  # ("p"|"li", [baris])
    in_list = False
    prev_blank = False
    for ln in lines:
        if not ln.strip():
            prev_blank = True
            continue
        ind = _indent(ln)
        if _ITEM.match(ln):
            blocks.append(("li", [_ITEM.sub("", ln, count=1)]))
            in_list = True
        elif in_list:
            # setelah daftar: paragraf baru hanya bila didahului baris kosong & berindentasi paragraf (5-8)
            if prev_blank and 5 <= ind <= 8 and ln.strip()[:1].isupper():
                blocks.append(("p", [ln]))
                in_list = False
            else:
                blocks[-1][1].append(ln)
        elif ind >= 5 or not blocks:
            blocks.append(("p", [ln]))
        else:
            blocks[-1][1].append(ln)
        prev_blank = False
    content: list = []
    for kind, ls in blocks:
        text = _join(ls)
        if not text:
            continue
        if kind == "li":
            if content and isinstance(content[-1], ContentList):
                content[-1].items.append(text)
            else:
                content.append(ContentList(items=[text]))
        else:
            content.append(ContentText(isi=text))
    return content


_AUTH_SPLIT = re.compile(r"(?<=\.)\s*,\s*&\s*|(?<=\.)\s+&\s+|(?<=\.)\s*,\s+(?=[A-Z][^,]*,)")


def parse_authors(s: str) -> list[str]:
    parts = [p.strip().rstrip(",") for p in _AUTH_SPLIT.split(s.strip()) if p.strip()]
    return [p.rstrip(".") if "," not in p else p for p in parts]


def parse_reference(entry: str) -> ReferenceItem | None:
    m = re.match(r"^(?P<a>.+?)\s*\((?P<y>(?:1[89]|20)\d{2})[a-z]?\)\.\s*(?P<rest>.+)$", entry)
    if not m:
        return None
    rest = m["rest"].strip()
    doi = None
    link = None
    dm = re.search(r"https?://(?:dx\.)?doi\.org/(\S+)", rest)
    if dm:
        doi, link = dm.group(1).rstrip("."), dm.group(0).rstrip(".")
        rest = rest[: dm.start()].strip()
    title = rest.rstrip(". ").strip()
    return ReferenceItem(title=title, authors=parse_authors(m["a"]), year=int(m["y"]), doi=doi, link=link)


def parse(text: str) -> Makalah:
    lines = [ln for ln in text.replace("\f", "\n").splitlines() if not _PAGE.match(ln)]
    judul = " ".join(x.strip() for x in lines[:4] if x.strip() and not x.strip().lower().startswith("disusun"))
    mk = re.search(r"Mata\s+Kuliah\s+(.+?)(?:\n\s*\n|$)", "\n".join(lines[:12]), re.DOTALL)
    makalah = Makalah(judul=" ".join(judul.split()),
                      mata_kuliah=" ".join(mk.group(1).split()) if mk else "Mata Kuliah",
                      dosen_pengampu="Dosen", penyusun=[], kota="Kota", tahun="2026")
    i = 0
    n = len(lines)
    bab_key = None
    sub: SubBab | None = None
    buf: list[str] = []

    def flush():
        if sub is not None:
            sub.content = _content(buf)
            if any(k in sub.judul.lower() for k in _DAFTAR_TITLES):
                sub.kind = "daftar"

    while i < n:
        ln = lines[i]
        if _DP.match(ln):
            flush()
            sub = None
            makalah.daftar_pustaka = _parse_dp(lines[i + 1:])
            break
        bm = _BAB.match(ln)
        if bm:
            flush()
            sub = None
            bab_key = bm.group(1)
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            makalah.bab[bab_key] = Bab(judul=lines[j].strip().title() if j < n else "")
            i = j + 1
            continue
        if bab_key and _SUB.match(ln) and _indent(ln) == 0:
            flush()
            title = ln.strip()
            j = i + 1
            while j < n and lines[j].strip() and 1 <= _indent(lines[j]) <= 6 and not _ITEM.match(lines[j]):
                title += " " + lines[j].strip()  # judul terbungkus ke baris berikut
                j += 1
            sub = SubBab(judul=" ".join(title.split()))
            makalah.bab[bab_key].subbab.append(sub)
            buf = []
            i = j
            continue
        if sub is not None:
            buf.append(ln)
        i += 1
    else:
        flush()
    return makalah


def _parse_dp(lines: list[str]) -> list[ReferenceItem]:
    entries: list[list[str]] = []
    for ln in lines:
        if not ln.strip():
            continue
        if _indent(ln) == 0 and re.search(r"\((?:1[89]|20)\d{2}[a-z]?\)", ln):
            entries.append([ln])
        elif entries:
            entries[-1].append(ln)
    refs = []
    for e in entries:
        r = parse_reference(_join(e))
        if r:
            refs.append(r)
    return refs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src", help=".pdf atau .txt (keluaran pdftotext -layout)")
    ap.add_argument("out", help="berkas JSON Makalah keluaran")
    a = ap.parse_args(argv)
    src = Path(a.src)
    if src.suffix.lower() == ".pdf":
        text = subprocess.run(["pdftotext", "-layout", str(src), "-"], capture_output=True, text=True,
                              check=True).stdout
    else:
        text = src.read_text(encoding="utf-8")
    makalah = parse(text)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(makalah.model_dump(mode="json"), ensure_ascii=False, indent=1),
                           encoding="utf-8")
    subs = sum(len(b.subbab) for b in makalah.bab.values())
    print(f"bab={len(makalah.bab)} subbab={subs} referensi={len(makalah.daftar_pustaka)} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

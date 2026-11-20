"""Pemeriksaan statis template Word (aturan TPL-001) dan deteksi mode template.

Hanya membaca XML di dalam .docx (zipfile + lxml); tidak merender dan tidak memanggil Word/LibreOffice.
Dipakai oleh tes (template v3 harus bersih, template lama harus berisi temuan) dan oleh `docx_converter`
untuk memilih cara normalisasi data (`detect_template_mode`).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import List, Optional

from lxml import etree

from malas.enhance.models import Finding

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
RULE_ID = "TPL-001"

V3_TEMPLATE_NAME = "template makalah v3.docx"
# numId daftar bernomor (Rumusan Masalah/Tujuan/Manfaat/Saran) di template v3. Setelah render, konverter
# memecah tiap kelompok paragraf berurutan ber-numId ini menjadi numId baru agar penomoran mulai dari 1 lagi.
DAFTAR_NUM_ID = 101

MODE_INDEXED = "indexed"  # template lama: bab.I.subbab[0..2], bab.III.subbab[0]
MODE_GENERIC = "generic"  # template v3: loop `for sub in bab.I.subbab` / `bab.III.subbab`

# salah ketik yang pernah ada di template (RC-09 d); daftar terkurasi, bukan pemeriksa ejaan
TYPOS = ("Bekalang",)

_TAG = re.compile(r"<[^>]+>")
_GENERIC_I = re.compile(r"\bfor\s+sub\s+in\s+bab\.I\.subbab\s")
_GENERIC_III = re.compile(r"\bfor\s+sub\s+in\s+bab\.III\.subbab\s")
_NAMES_LOOP = re.compile(r"\bfor\s+\w+\s+in\s+penyusun\b")


def _read(path: str | Path, part: str) -> Optional[bytes]:
    with zipfile.ZipFile(path) as z:
        try:
            return z.read(part)
        except KeyError:
            return None


def _plain(xml: bytes | str) -> str:
    """Teks XML tanpa tag (tag Jinja yang terpecah di beberapa run jadi utuh lagi)."""
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8", "replace")
    return _TAG.sub("", xml)


def detect_template_mode(path: str | Path) -> str:
    """'generic' bila Bab I DAN Bab III dirender lewat loop `for sub in bab.X.subbab`, selain itu 'indexed'.

    Dideteksi dari ISI template (bukan nama berkas), sehingga tahan diganti nama/diunggah ulang. Keduanya
    disyaratkan karena `template makalah2.docx` (lama) punya loop Bab I tetapi Bab III-nya masih bentuk lama.
    Berkas yang tak terbaca dianggap 'indexed' (perilaku lama, paling aman).
    """
    try:
        xml = _read(path, "word/document.xml")
    except (OSError, zipfile.BadZipFile):
        return MODE_INDEXED
    plain = _plain(xml or b"")
    return MODE_GENERIC if _GENERIC_I.search(plain) and _GENERIC_III.search(plain) else MODE_INDEXED


def _para_text(p) -> str:
    return "".join(p.itertext())


def _finding(severity: str, message: str, evidence: str = "", hint: str = "") -> Finding:
    return Finding(rule_id=RULE_ID, severity=severity, message=message[:200], evidence=evidence[:200], hint=hint,
                   fix="human")


def _page_break_before(paras: list, idx: int) -> bool:
    """Ada pemisah halaman tepat sebelum paragraf idx (melewati paragraf kosong tanpa teks)."""
    p = paras[idx]
    if p.xpath("./w:pPr/w:pageBreakBefore[not(@w:val='0' or @w:val='false')]", namespaces=NS):
        return True
    for prev in reversed(paras[:idx]):
        if prev.xpath(".//w:br[@w:type='page']", namespaces=NS) or prev.xpath("./w:pPr/w:sectPr", namespaces=NS):
            return True
        if _para_text(prev).strip():
            return False
    return False


def check_template(path: str | Path) -> List[Finding]:
    """Periksa cacat template yang diketahui (RC-09). Daftar kosong = tidak ada temuan dari aturan ini."""
    try:
        doc_xml = _read(path, "word/document.xml")
        settings_xml = _read(path, "word/settings.xml") or b""
        root = etree.fromstring(doc_xml) if doc_xml else None
    except (OSError, zipfile.BadZipFile, etree.XMLSyntaxError) as e:
        return [_finding("blocker", f"Template tidak bisa dibaca sebagai .docx: {e}")]
    if root is None:
        return [_finding("blocker", "Template tidak memuat word/document.xml.")]

    out: List[Finding] = []
    body = root.find("w:body", NS)
    paras = body.xpath(".//w:p", namespaces=NS) if body is not None else []
    texts = [_para_text(p) for p in paras]
    plain = _plain(doc_xml)

    instr = " ".join("".join(t.itertext()) for t in root.iter(f"{{{W_NS}}}instrText"))
    if not re.search(r"\bTOC\b", instr):
        out.append(_finding("major", "Daftar Isi tanpa field TOC: halaman Daftar Isi akan kosong.",
                            hint='Sisipkan field TOC \\o "1-2" \\h \\z \\u.'))

    if not re.search(rb'<w:updateFields\s+w:val="(?:true|1|on)"', settings_xml):
        out.append(_finding("major", "settings.xml tanpa updateFields: Word tidak menawarkan pembaruan Daftar Isi.",
                            hint='Tambahkan <w:updateFields w:val="true"/>.'))

    idx3 = next((i for i, t in enumerate(texts) if t.strip().upper().startswith("BAB III")), None)
    if idx3 is None:
        out.append(_finding("major", "Judul BAB III tidak ditemukan di template."))
    elif not _page_break_before(paras, idx3):
        out.append(_finding("major", "BAB III tidak diawali pemisah halaman (menempel pada akhir Bab II).",
                            evidence=texts[idx3]))

    for typo in TYPOS:
        hit = next((t for t in texts if typo in t), None)
        if hit is not None:
            out.append(_finding("major", f"Salah ketik di template: '{typo}'.", evidence=hit.strip()))

    i_kp = plain.find("KATA PENGANTAR")
    i_di = plain.find("DAFTAR ISI", max(i_kp, 0))
    blok = plain[i_kp:i_di] if i_kp >= 0 and i_di > i_kp else ""
    if not _NAMES_LOOP.search(blok):
        out.append(_finding("major", "Blok penutup Kata Pengantar tanpa nama penyusun (hanya tanggal/'Penulis').",
                            hint="Tambahkan {% for p in penyusun %}{{p.nama}}{% endfor %} setelah 'Penulis'."))

    for label, pat in (("I", _GENERIC_I), ("III", _GENERIC_III)):
        if not pat.search(plain):
            out.append(_finding("major", f"Bab {label} memakai indeks sub-bab tetap, bukan loop generik: "
                                         "sub-bab tambahan (Manfaat, Metode, Saran) tidak akan tampil.",
                                evidence=f"bab.{label}.subbab[...]"))
    return out

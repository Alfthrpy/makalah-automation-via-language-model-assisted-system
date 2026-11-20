"""Turunkan `template makalah v3.docx` dari `template makalah.docx` secara reprodusibel (tanpa Word).

Pemakaian (dari akar repo):
    python packages/engine/scripts/build_template_v3.py [--src SRC] [--out OUT]

Perubahan terhadap template lama (docs/enhancing-engine.md S06, RC-09):
  a) Daftar Isi: field `TOC \\o "1-2" \\h \\z \\u` + `<w:updateFields w:val="true"/>` di settings.xml.
  b) Pemisah halaman sebelum BAB III dan `pageBreakBefore` pada judul KATA PENGANTAR (Bab I tetap mulai
     halaman baru lewat pemisah bagian yang sudah ada); paragraf kosong bernomor pembawa page-break di akhir Bab I (muncul sebagai butir "2)" kosong) dibuang.
  c) Penutup Kata Pengantar: tanggal, "Penulis", lalu nama tiap penyusun (paragraf sendiri), semuanya `keepNext`
     (juga paragraf terakhir kata pengantar) agar tidak terlempar sendirian ke halaman baru.
  d) "Latar Bekalang" hilang karena judul sub-bab kini berasal dari data.
  e) Bab I dan Bab III memakai loop generik `{% for sub in bab.X.subbab %}` dengan isi per `sub.kind`
     (`daftar` = butir bernomor format Rumusan Masalah; selain itu teks/list/tabel). Bab II memakai blok isi yang
     sama sehingga bisa merender tabel (`{{p c.subdoc}}`, subdoc dibuat oleh DocxConverter).
     Judul Bab III memakai penomoran "3.x" (template lama mencetak "1.1 Kesimpulan").
Semua paragraf baru menyalin pPr/rPr dari paragraf sejenis di template lama (Times New Roman 12, spasi 1,5, rata
kiri-kanan). Tag kontrol memakai `{%p ... %}` agar paragraf pembawanya hilang saat render (tanpa baris kosong).
Hasil deterministik: menjalankan ulang menghasilkan berkas yang sama (urutan & stempel waktu zip disalin dari sumber).
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from malas.template_check import DAFTAR_NUM_ID, V3_TEMPLATE_NAME

TEMPLATES = HERE.parent / "src" / "malas" / "templates"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}
TOC_HINT = "Klik kanan di sini → Perbarui bidang (Update Field) untuk menampilkan Daftar Isi."


class BuildError(RuntimeError):
    pass


def _text(el) -> str:
    return "".join(el.itertext())


def _find(paras, pred, what):
    for i, p in enumerate(paras):
        if pred(_text(p)):
            return i
    raise BuildError(f"Paragraf acuan tidak ditemukan: {what}")


class _Ser:
    """Serialisasi elemen sebagai potongan string tanpa deklarasi namespace yang sudah ada di akar dokumen."""

    def __init__(self, root):
        self.decls = {f'xmlns:{k}="{v}"' for k, v in root.nsmap.items() if k}

    def __call__(self, el) -> str:
        s = etree.tostring(el, encoding="unicode")
        return re.sub(r'\s(xmlns:\w+="[^"]*")', lambda m: "" if m.group(1) in self.decls else m.group(0), s)


def _ppr(ser, p) -> str:
    el = p.find("w:pPr", NS)
    return ser(el) if el is not None else ""


def _run_rpr(ser, p) -> str:
    r = p.find(".//w:r/w:rPr", NS)
    return ser(r) if r is not None else ""


def _keep_next(ppr: str) -> str:
    """Sisipkan <w:keepNext/> sesuai urutan skema CT_PPr (setelah pStyle)."""
    if "<w:keepNext/>" in ppr:
        return ppr
    if not ppr:
        return "<w:pPr><w:keepNext/></w:pPr>"
    m = re.match(r"<w:pPr>(<w:pStyle [^>]*/>)?", ppr)
    return ppr[:m.end()] + "<w:keepNext/>" + ppr[m.end():]


def _para(ppr: str, text: str, rpr: str = "", lead: str = "") -> str:
    lead_run = f'<w:r>{rpr}<w:t xml:space="preserve">{escape(lead)}</w:t></w:r>' if lead else ""
    run = f'<w:r>{rpr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>' if text else ""
    return f"<w:p>{ppr}{lead_run}{run}</w:p>"


def _ctl(tag: str) -> str:
    """Paragraf kontrol docxtpl `{%p ... %}` (paragrafnya dibuang saat render)."""
    if "}" in tag or "%" in tag:
        raise BuildError(f"Tag kontrol tidak boleh memuat '}}' atau '%': {tag}")
    return f"<w:p><w:r><w:t>{escape('{%p ' + tag + ' %}')}</w:t></w:r></w:p>"


def _content_block(text_ppr: str, text_rpr: str, alpha_ppr: str) -> list[str]:
    """Isi satu sub-bab non-daftar: tabel (subdoc), list a) b) c), atau paragraf teks."""
    return [
        _ctl("for c in sub.content"),
        _ctl('if c.type == "table"'),
        "<w:p><w:r><w:t>{{p c.subdoc }}</w:t></w:r></w:p>",
        _ctl('elif c.type == "list"'),
        _ctl("if c.title_items"),
        _para(text_ppr, "{{ c.title_items }}", text_rpr),
        _ctl("endif"),
        _ctl('for item in c["items"]'),
        _para(alpha_ppr, "{{ alphabet[loop.index0] }})  {{ item }}", text_rpr),
        _ctl("endfor"),
        _ctl("else"),
        _ctl('for paragraf in (c.isi or "").split("\\n")'),
        _ctl("if paragraf.strip()"),
        _para(text_ppr, "{{ paragraf.strip() }}", text_rpr),
        _ctl("endif"),
        _ctl("endfor"),
        _ctl("endif"),
        _ctl("endfor"),
    ]


def _bab_loop(key: str, heading: str, list_ppr: str, text_ppr: str, text_rpr: str, alpha_ppr: str) -> list[str]:
    return [
        _ctl(f"for sub in bab.{key}.subbab"),
        heading,
        _ctl('if sub.kind == "daftar"'),
        _ctl('for it in (sub.content[0]["items"] if sub.content else [])'),
        _para(list_ppr, "{{ it }}", text_rpr),
        _ctl("endfor"),
        _ctl("else"),
        *_content_block(text_ppr, text_rpr, alpha_ppr),
        _ctl("endif"),
        _ctl("endfor"),
    ]


def _heading(ppr: str) -> str:
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">  </w:t></w:r><w:r><w:t>{{{{ sub.judul }}}}</w:t></w:r></w:p>'


def _drop_orphan_bookmarks(xml: str) -> str:
    starts = set(re.findall(r'<w:bookmarkStart w:id="(\d+)"', xml))
    ends = set(re.findall(r'<w:bookmarkEnd w:id="(\d+)"', xml))
    for i in ends - starts:
        xml = re.sub(rf'<w:bookmarkEnd w:id="{i}"/>', "", xml)
    for i in starts - ends:
        xml = re.sub(rf'<w:bookmarkStart w:id="{i}"[^>]*/>', "", xml)
    return xml


def build_document(xml: bytes, bab3_num_id: int) -> bytes:
    root = etree.fromstring(xml)
    ser = _Ser(root)
    body = root.find("w:body", NS)
    paras = list(body)

    i_kp = _find(paras, lambda t: t.strip() == "KATA PENGANTAR", "KATA PENGANTAR")
    i_kp_loop = _find(paras, lambda t: "kata_pengantar" in t and "for" in t, "loop kata pengantar")
    i_kp_par = i_kp_loop + 1
    i_date = _find(paras, lambda t: "{{formatted_date}}" in t, "tanggal")
    i_penulis = _find(paras, lambda t: t.strip() == "Penulis", "Penulis")
    i_di = _find(paras, lambda t: t.strip() == "DAFTAR ISI", "DAFTAR ISI")
    i_bab1 = _find(paras, lambda t: t.startswith("BAB I") and not t.startswith("BAB II"), "BAB I")
    i_lb = _find(paras, lambda t: "Latar Be" in t, "judul Latar Belakang")
    i_rm_item = _find(paras, lambda t: t.strip() == "{{r}}", "butir Rumusan Masalah")
    i_bab2 = _find(paras, lambda t: t.startswith("BAB II") and not t.startswith("BAB III"), "BAB II")
    i_h2 = _find(paras, lambda t: "sub.judul" in t, "judul sub-bab Bab II")
    i_alpha = _find(paras, lambda t: "alphabet" in t, "butir a) Bab II")
    i_bab3 = _find(paras, lambda t: t.startswith("BAB III"), "BAB III")
    i_kes = _find(paras, lambda t: t.strip() == "Kesimpulan", "judul Kesimpulan")
    i_dp = _find(paras, lambda t: t.strip() == "DAFTAR PUSTAKA", "DAFTAR PUSTAKA")
    if not (i_kp < i_kp_loop < i_date < i_penulis < i_di < i_bab1 < i_bab2 < i_bab3 < i_dp):
        raise BuildError("Urutan paragraf acuan tidak sesuai template sumber.")
    i_pb_dp = i_dp - 1  # paragraf page-break sebelum DAFTAR PUSTAKA
    if not paras[i_pb_dp].xpath(".//w:br[@w:type='page']", namespaces=NS):
        raise BuildError("Paragraf sebelum DAFTAR PUSTAKA bukan page-break.")
    i_toc_sect = i_di + 1  # paragraf JudulTOC pembawa sectPr (akhir bagian romawi)
    if not paras[i_toc_sect].xpath("./w:pPr/w:sectPr", namespaces=NS):
        raise BuildError("Paragraf setelah DAFTAR ISI bukan pembawa sectPr.")

    s = [ser(p) for p in paras]
    text_ppr, text_rpr = _ppr(ser, paras[i_kp_par]), _run_rpr(ser, paras[i_kp_par])
    sel_both = _ppr(ser, paras[i_date - 1])
    sel_right = _ppr(ser, paras[i_date])
    sel_rpr = _run_rpr(ser, paras[i_date])
    list_ppr = _ppr(ser, paras[i_rm_item]).replace('<w:numId w:val="4"/>', f'<w:numId w:val="{DAFTAR_NUM_ID}"/>')
    if f'w:val="{DAFTAR_NUM_ID}"' not in list_ppr:
        raise BuildError("Butir Rumusan Masalah tidak memakai numId 4 seperti yang diharapkan.")
    alpha_ppr = _ppr(ser, paras[i_alpha])
    h_bab1 = _heading(_ppr(ser, paras[i_lb]))
    h_bab2 = s[i_h2]
    h_bab3 = _heading(re.sub(r'<w:numId w:val="\d+"/>', f'<w:numId w:val="{bab3_num_id}"/>',
                             _ppr(ser, paras[i_kes]).replace('<w:ilvl w:val="1"/>', '<w:ilvl w:val="0"/>')))
    pb = copy.deepcopy(paras[i_pb_dp])
    page_break = ser(pb)

    kata_pengantar = [
        _ctl("for paragraf in (kata_pengantar_paragraf or [])[:-1]"),
        _para(text_ppr, "{{ paragraf }}", text_rpr),
        _ctl("endfor"),
        _ctl("if kata_pengantar_paragraf"),
        _para(_keep_next(text_ppr), "{{ kata_pengantar_paragraf[-1] }}", text_rpr),
        _ctl("endif"),
        _para(_keep_next(sel_both), ""),
        _para(_keep_next(sel_right), "{{formatted_date}}", sel_rpr),
        _para(_keep_next(sel_right), "Penulis", sel_rpr),
        _para(_keep_next(sel_both), ""),
        _ctl("for p in penyusun"),
        _para(_keep_next(sel_right), "{{ p.nama }}", sel_rpr),
        _ctl("endfor"),
    ]
    toc_ppr = text_ppr.replace('<w:ind w:firstLine="720"/>', "")
    toc = (
        f"<w:p>{toc_ppr}"
        '<w:r><w:fldChar w:fldCharType="begin" w:dirty="true"/></w:r>'
        '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        f'<w:r>{text_rpr}<w:t xml:space="preserve">{escape(TOC_HINT)}</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'
    )

    # KATA PENGANTAR selalu mulai halaman baru: di template lama ia hanya "terdorong" oleh sampul yang penuh,
    # sehingga di LibreOffice/font pengganti judul itu bisa menempel di halaman sampul.
    if "<w:pageBreakBefore/>" not in s[i_kp]:
        s[i_kp] = re.sub(r"(<w:pPr>(?:<w:pStyle [^>]*/>)?(?:<w:keepNext/>)?(?:<w:keepLines/>)?)",
                         r"\1<w:pageBreakBefore/>", s[i_kp], count=1)

    out: list[str] = []
    out += s[:i_kp_loop]  # sampul s/d judul KATA PENGANTAR + paragraf kosong
    out += kata_pengantar
    out += s[i_penulis + 1:i_di + 1]  # page-break + judul DAFTAR ISI
    out.append(toc)
    out += s[i_toc_sect:i_bab1 + 2]  # pembawa sectPr, BAB I, paragraf kosong
    out += _bab_loop("I", h_bab1, list_ppr, text_ppr, text_rpr, alpha_ppr)
    out.append(page_break)
    out.append(s[i_bab2])
    out += _bab_loop("II", h_bab2, list_ppr, text_ppr, text_rpr, alpha_ppr)
    out.append(page_break)
    out += s[i_bab3:i_bab3 + 2]  # BAB III + paragraf kosong
    out += _bab_loop("III", h_bab3, list_ppr, text_ppr, text_rpr, alpha_ppr)
    out += s[i_pb_dp:]  # page-break, DAFTAR PUSTAKA, loop referensi, sectPr akhir

    src = xml.decode("utf-8")
    m = re.search(r"<w:body>.*</w:body>", src, re.DOTALL)
    if not m:
        raise BuildError("<w:body> tidak ditemukan.")
    new = src[:m.start()] + "<w:body>" + _drop_orphan_bookmarks("".join(out)) + "</w:body>" + src[m.end():]
    etree.fromstring(new.encode("utf-8"))  # validasi well-formed
    return new.encode("utf-8")


def build_numbering(xml: bytes) -> tuple[bytes, int]:
    """Tambah numId DAFTAR_NUM_ID (format "1)" Rumusan Masalah, mulai 1) dan penomoran judul Bab III "3.x"."""
    src = xml.decode("utf-8")
    if f'<w:num w:numId="{DAFTAR_NUM_ID}"' in src:
        raise BuildError("numbering.xml sumber sudah memuat numId daftar v3.")
    abs_ids = [int(x) for x in re.findall(r'<w:abstractNum [^>]*w:abstractNumId="(\d+)"', src)]
    num_ids = [int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', src)]
    m27 = re.search(r'<w:abstractNum [^>]*w:abstractNumId="27".*?</w:abstractNum>', src, re.DOTALL)
    if not m27 or "1.%1" not in m27.group(0):
        raise BuildError("abstractNum 27 (judul '1.%1') tidak ditemukan.")
    m5 = re.search(r'<w:num w:numId="4"[^>]*><w:abstractNumId w:val="(\d+)"/>', src)
    if not m5:
        raise BuildError("numId 4 (Rumusan Masalah) tidak ditemukan.")
    new_abs, bab3_num = max(abs_ids) + 1, max(num_ids) + 1
    bab3_abs = m27.group(0)
    bab3_abs = re.sub(r'w:abstractNumId="27"', f'w:abstractNumId="{new_abs}"', bab3_abs, count=1)
    bab3_abs = re.sub(r"<w:nsid [^>]*/>|<w:tmpl [^>]*/>|<w:pStyle [^>]*/>", "", bab3_abs)
    bab3_abs = re.sub(r' w15:restartNumberingAfterBreak="[^"]*"', "", bab3_abs)
    bab3_abs = bab3_abs.replace('w:val="1.%1"', 'w:val="3.%1"', 1)
    last_abs = list(re.finditer(r"</w:abstractNum>", src))[-1].end()
    src = src[:last_abs] + bab3_abs + src[last_abs:]
    nums = (f'<w:num w:numId="{bab3_num}"><w:abstractNumId w:val="{new_abs}"/></w:num>'
            f'<w:num w:numId="{DAFTAR_NUM_ID}"><w:abstractNumId w:val="{m5.group(1)}"/>'
            '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>')
    last_num = list(re.finditer(r"</w:num>", src))[-1].end()
    src = src[:last_num] + nums + src[last_num:]
    etree.fromstring(src.encode("utf-8"))
    return src.encode("utf-8"), bab3_num


# elemen CT_Settings yang harus berada SETELAH updateFields (urutan skema)
_AFTER_UPDATE_FIELDS = ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
                        "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
                        "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown",
                        "smartTagType", "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol",
                        "listSeparator")


def build_settings(xml: bytes) -> bytes:
    src = xml.decode("utf-8")
    if "<w:updateFields" in src:
        return xml
    pos = None
    for name in _AFTER_UPDATE_FIELDS:
        m = re.search(rf"<w:{name}[\s/>]", src)
        if m and (pos is None or m.start() < pos):
            pos = m.start()
    if pos is None:
        pos = src.rindex("</w:settings>")
    src = src[:pos] + '<w:updateFields w:val="true"/>' + src[pos:]
    etree.fromstring(src.encode("utf-8"))
    return src.encode("utf-8")


def build(src: Path, out: Path) -> Path:
    with zipfile.ZipFile(src) as zin:
        items = [(info, zin.read(info.filename)) for info in zin.infolist()]
    parts = {info.filename: data for info, data in items}
    numbering, bab3_num = build_numbering(parts["word/numbering.xml"])
    new_parts = {
        "word/document.xml": build_document(parts["word/document.xml"], bab3_num),
        "word/numbering.xml": numbering,
        "word/settings.xml": build_settings(parts["word/settings.xml"]),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info, data in items:
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = info.external_attr
            zout.writestr(zi, new_parts.get(info.filename, data))
    tmp.replace(out)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", type=Path, default=TEMPLATES / "template makalah.docx")
    ap.add_argument("--out", type=Path, default=TEMPLATES / V3_TEMPLATE_NAME)
    args = ap.parse_args(argv)
    print(build(args.src, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

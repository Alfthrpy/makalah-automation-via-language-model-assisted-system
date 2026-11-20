"""Konversi state Makalah menjadi file .docx via docxtpl (Jinja2 di dalam template Word)."""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docxtpl import DocxTemplate
from jinja2 import Environment
from lxml import etree

from malas.apa import apa_sort_key, format_apa7, format_apa7_segments  # noqa: F401  (format_apa7: re-export)
from malas.crews.models.TaskOutput import Makalah
from malas.logo import apply_logo, normalize_logo
from malas.template_check import DAFTAR_NUM_ID, MODE_GENERIC, MODE_INDEXED, detect_template_mode

logger = logging.getLogger(__name__)

_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember"]


def _tanggal_indonesia(d: datetime) -> str:
    return f"{d.day} {_BULAN[d.month - 1]} {d.year}"


def _table_grid(c: dict) -> tuple:
    """(header, rows) bersih dari item tabel: sel jadi str, baris dipadatkan ke jumlah kolom terbanyak,
    baris yang seluruh selnya kosong dibuang. Kolom 0 -> ([], [])."""
    def cells(row):
        return [("" if v is None else str(v)).strip() for v in (row or [])]

    header = cells(c.get("header"))
    rows = [r for r in (cells(r) for r in (c.get("rows") or [])) if any(r)]
    ncols = max([len(header)] + [len(r) for r in rows] or [0])
    if not ncols:
        return [], []
    pad = lambda r: r + [""] * (ncols - len(r))  # noqa: E731
    return (pad(header) if any(header) else []), [pad(r) for r in rows]


def table_as_text(c: dict) -> str:
    """Ratakan tabel jadi teks (cadangan: template lama, atau subdoc gagal dibuat)."""
    header, rows = _table_grid(c)
    lines = [str(c.get("caption") or "").strip()]
    lines += [" | ".join(r) for r in ([header] if header else []) + rows]
    return "\n".join(ln for ln in lines if ln)


def _as_text(contents: list) -> list:
    """Paksa semua item konten jadi tipe 'text' (list/tabel -> baris teks).

    Template memakai c['isi'] untuk bagian naratif (Latar Belakang, Kesimpulan),
    jadi item bertipe list dari LLM harus diratakan agar tidak merusak render.
    """
    out = []
    for c in contents:
        if c.get("type") == "list":
            lines = ([c["title_items"]] if c.get("title_items") else []) + [f"- {i}" for i in c.get("items", [])]
            out.append({"type": "text", "isi": "\n".join(lines)})
        elif c.get("type") == "table":
            out.append({"type": "text", "isi": table_as_text(c)})
        else:
            out.append(c)
    return out


_DAFTAR_JUDUL = re.compile(r"^(?:rumusan\s+masalah|tujuan|manfaat|saran)\b", re.I)


def infer_kind(judul: str) -> str:
    """'daftar' untuk sub-bab yang lazimnya berupa butir (Rumusan Masalah, Tujuan, Manfaat, Saran), selain itu
    'narasi'. Hanya awal judul (tanpa nomor) yang dilihat: "Kesimpulan dan Saran" tetap narasi."""
    return "daftar" if _DAFTAR_JUDUL.match(strip_heading_number(judul or "")) else "narasi"


_MARKER = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)]|[a-zA-Z][.)])\s+")


def _as_list(contents: list) -> list:
    """Paksa konten jadi satu item 'list' (template memakai content[0]['items']).

    LLM biasanya menulis: kalimat pengantar + butir bernomor + paragraf penjelasan. Hanya BUTIR yang boleh
    jadi isi daftar (kalau tidak, pengantar/penjelasan ikut bernomor: "1) Berdasarkan latar belakang…").
    - Ada item bertipe list -> hanya butir list (pengantar teks dibuang; butir berakhiran ":" = pengantar).
    - Teks dengan >=2 baris bermarker ("1)", "a.", "-") -> hanya baris bermarker; baris tanpa marker di
      antara dua butir = lanjutan butir sebelumnya; di luar itu (pengantar/penutup) dibuang.
    - Selain itu perilaku lama: tiap baris tak kosong = satu butir.
    """
    list_items = [str(i).strip() for c in contents if c.get("type") == "list" for i in c.get("items", []) if str(i).strip()]
    if list_items:
        if len(list_items) > 1 and list_items[0].rstrip().endswith(":"):
            list_items = list_items[1:]
        return [{"type": "list", "title_items": None, "items": list_items}]

    lines = [ln for c in contents for ln in str(c.get("isi", "")).splitlines() if ln.strip()]
    marked = [i for i, ln in enumerate(lines) if _MARKER.match(ln)]
    items: list = []
    if len(marked) >= 2:
        for ln in lines[marked[0]:marked[-1] + 1]:
            if _MARKER.match(ln):
                items.append(_MARKER.sub("", ln, count=1).strip())
            elif items:  # lanjutan butir yang terpotong baris
                items[-1] = f"{items[-1]} {ln.strip()}"
    else:
        items = [_MARKER.sub("", ln, count=1).strip() for ln in lines]
    return [{"type": "list", "title_items": None, "items": [i for i in items if i]}]


_NOMOR_JUDUL = re.compile(r"^\s*\d{1,2}(?:\.\d{1,2})*[.)]?\s+")  # "2.1 ", bukan tahun "2024 "


def strip_heading_number(judul: str) -> str:
    """'2.1 Konsep Dasar' -> 'Konsep Dasar'. Gaya judul di template sudah bernomor otomatis (tanpa ini: '2.1 2.1 ...')."""
    return _NOMOR_JUDUL.sub("", judul or "", count=1).strip() or (judul or "")


_XML_ILLEGAL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")


def xml_safe(obj: Any) -> Any:
    """Buang karakter kontrol yang tidak boleh ada di XML (merusak .docx) dari seluruh data."""
    if isinstance(obj, str):
        return _XML_ILLEGAL.sub("", obj)
    if isinstance(obj, list):
        return [xml_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: xml_safe(v) for k, v in obj.items()}
    return obj


def normalize_for_template(context: Dict[str, Any], mode: str = MODE_INDEXED) -> Dict[str, Any]:
    """Samakan bentuk data LLM dengan asumsi template.

    - mode 'indexed' (template lama, indeks tetap): Bab I idx0 teks, idx lain list; Bab III teks; tabel diratakan
      jadi teks di semua bab (template lama tak punya cabang tabel).
    - mode 'generic' (template v3, loop per sub-bab): sub-bab `kind == "daftar"` jadi satu item list; sub-bab
      lain dibiarkan (teks/list/tabel dirender apa adanya; tabel diganti subdoc oleh DocxConverter).
    `kind` yang belum "daftar" ditebak dari judul (`infer_kind`) hanya untuk Bab I dan Bab III, karena judul
    pembahasan Bab II seperti "Tujuan Pembelajaran ..." tetap narasi.
    """
    bab = context.get("bab", {})

    def subs(key):
        return bab.get(key, {}).get("subbab", [])

    for key in bab:  # nomor hanya dihapus di tampilan; state/checkpoint/kunci refsearch tetap memakai judul bernomor
        for sub in subs(key):
            sub.setdefault("kind", "narasi")
            if key in ("I", "III") and sub["kind"] != "daftar" and infer_kind(sub.get("judul", "")) == "daftar":
                sub["kind"] = "daftar"
            sub["judul"] = strip_heading_number(sub.get("judul", ""))
            sub["content"] = list(sub.get("content") or [])

    if mode == MODE_GENERIC:
        for key in bab:
            for sub in subs(key):
                if sub["kind"] == "daftar":
                    sub["content"] = _as_list(sub["content"])
        return context

    for key in bab:
        for sub in subs(key):
            sub["content"] = [{"type": "text", "isi": table_as_text(c)} if c.get("type") == "table" else c
                              for c in sub["content"]]
    for idx, sub in enumerate(subs("I")):
        sub["content"] = _as_text(sub["content"]) if idx == 0 else _as_list(sub["content"])
    for sub in subs("III"):
        sub["content"] = _as_text(sub["content"])
    return context


_REF_RUN = re.compile(
    r"(<w:r(?:\s[^>]*)?>)(?:<w:rPr>((?:(?!</w:rPr>).)*)</w:rPr>)?<w:t[^>]*>\{\{\s*ref\s*\}\}</w:t></w:r>", re.S)
_RPR_HEAD = re.compile(r"^(?:<w:(?:rStyle|rFonts|b|bCs)\b[^>]*/>)*")


def italicize_ref_runs(xml: str) -> str:
    """Ganti run berisi tepat `{{ref}}` dengan loop segmen APA (teks, italik), mempertahankan rPr template.

    Template lama menulis `{{ref}}` polos (tanpa `{{r ...}}`); daripada menyunting .docx, XML yang SUDAH di-patch
    docxtpl diubah in-memory: tiap segmen jadi run sendiri dan `<w:i/>` ditambahkan pada segmen italik
    (urutan skema CT_RPr: setelah rStyle/rFonts/b/bCs). Run yang tak cocok pola dibiarkan (teks polos).
    Segmen diambil dari `daftar_pustaka_segmen[ref]`; tanpa entri -> satu segmen polos berisi `ref`.
    """
    def repl(m):
        run_open, rpr = m.group(1), m.group(2) or ""
        if "<w:i/>" in rpr or '<w:i w:val="1"/>' in rpr:
            rpr_i = rpr
        else:
            head = _RPR_HEAD.match(rpr).end()
            rpr_i = rpr[:head] + "<w:i/><w:iCs/>" + rpr[head:]
        return (
            "{% for seg in (daftar_pustaka_segmen or {}).get(ref) or [[ref, false]] %}"
            f"{run_open}{{% if seg[1] %}}<w:rPr>{rpr_i}</w:rPr>{{% else %}}<w:rPr>{rpr}</w:rPr>{{% endif %}}"
            '<w:t xml:space="preserve">{{ seg[0] }}</w:t></w:r>{% endfor %}'
        )

    return _REF_RUN.sub(repl, xml)


class _ApaDocxTemplate(DocxTemplate):
    """DocxTemplate yang merender `{{ref}}` daftar pustaka sebagai beberapa run (italik nama jurnal/volume)."""

    def patch_xml(self, src_xml):
        xml = super().patch_xml(src_xml)
        try:
            return italicize_ref_runs(xml)
        except Exception as e:  # pola aneh -> teks polos, jangan gagalkan render
            logger.warning("Italik daftar pustaka dilewati: %s", e)
            return xml


_FONT = "Times New Roman"


def _set_run_font(run, size_pt: float, bold: bool = False) -> None:
    run.font.name = _FONT
    run.font.size = Pt(size_pt)
    run.bold = bold or None
    rfonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    rfonts.set(qn("w:cs"), _FONT)
    rfonts.set(qn("w:eastAsia"), _FONT)


def _table_borders(table) -> None:
    """Garis tunggal di semua sisi + lebar 100% (tidak bergantung gaya tabel di template)."""
    tbl_pr = table._tbl.tblPr
    for tag in ("w:tblW", "w:tblBorders"):
        old = tbl_pr.find(qn(tag))
        if old is not None:
            tbl_pr.remove(old)
    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), "5000")
    tbl_w.set(qn("w:type"), "pct")
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), "4")
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "000000")
        borders.append(b)
    # urutan skema CT_TblPr: tblStyle, ..., tblW, jc, ..., tblBorders, ..., tblLook
    style = tbl_pr.find(qn("w:tblStyle"))
    idx = list(tbl_pr).index(style) + 1 if style is not None else 0
    tbl_pr.insert(idx, tbl_w)
    tbl_pr.insert(idx + 1, borders)


class XmlFragment:
    """Potongan XML body WordprocessingML siap disisipkan lewat `{{p c.subdoc}}` (setara docxtpl Subdoc).

    docxtpl `Subdoc` butuh paket opsional `docxcompose` (tidak ada di dependensi), padahal tabel tanpa gambar/gaya
    tidak membutuhkan penggabungan part. Jadi isi dibangun di dokumen python-docx sementara lalu body-nya
    diserialisasi tanpa tag <w:body> (sama seperti `Subdoc._get_xml`); prefiks `w:` sudah dideklarasikan di akar
    dokumen tujuan. `__html__` membuat autoescape Jinja tidak meng-escape XML ini.
    """

    def __init__(self):
        self.docx = Document()
        body = self.docx.element.body
        for el in list(body):
            if el.tag != qn("w:sectPr"):  # sectPr dibutuhkan python-docx (lebar tabel); tidak ikut diserialisasi
                body.remove(el)

    def add_paragraph(self):
        return self.docx.add_paragraph()

    def add_table(self, rows: int, cols: int):
        return self.docx.add_table(rows=rows, cols=cols)

    def xml(self) -> str:
        body = self.docx.element.body
        parts = [etree.tostring(el, encoding="unicode") for el in body if el.tag != qn("w:sectPr")]
        return _NS_DECL.sub("", "".join(parts))

    __str__ = __html__ = xml


_NS_DECL = re.compile(r'\sxmlns:w="http://schemas\.openxmlformats\.org/wordprocessingml/2006/main"')


def build_table_subdoc(c: dict, nomor: int) -> XmlFragment:
    """Fragmen berisi caption "Tabel N. ..." (di atas, bila ada) + tabel bergaris, header tebal.

    Tahan kolom bervariasi (dipadatkan), sel panjang, karakter XML khusus (python-docx meng-escape), baris kosong
    (dibuang). Tabel tanpa sel sama sekali -> ValueError (pemanggil menurunkannya jadi teks)."""
    header, rows = _table_grid(c)
    if not header and not rows:
        raise ValueError("tabel kosong")
    ncols = len(header or rows[0])
    sd = XmlFragment()
    caption = str(c.get("caption") or "").strip()
    if caption:
        p = sd.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(6)
        _set_run_font(p.add_run(f"Tabel {nomor}. "), 12, bold=True)
        _set_run_font(p.add_run(caption), 12)
    table = sd.add_table(rows=0, cols=ncols)
    _table_borders(table)
    for r_idx, values in enumerate(([header] if header else []) + rows):
        row = table.add_row()
        is_header = bool(header) and r_idx == 0
        if is_header:  # ulangi baris judul di tiap halaman
            tr_pr = row._tr.get_or_add_trPr()
            th = OxmlElement("w:tblHeader")
            tr_pr.append(th)
        for cell, value in zip(row.cells, values):
            p = cell.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            if is_header:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for i, line in enumerate(value.split("\n")):
                run = p.add_run()
                if i:
                    run.add_break()  # baris baru di dalam sel tetap satu paragraf
                run.add_text(line)
                _set_run_font(run, 11, bold=is_header)
    sd.add_paragraph()  # jarak setelah tabel (dan memastikan tabel tak menempel ke judul berikutnya)
    return sd


def attach_table_subdocs(context: Dict[str, Any]) -> int:
    """Isi `c['subdoc']` tiap item tabel di semua bab (penomoran "Tabel N" mengikuti urutan dokumen).
    Gagal membuat tabel -> item diturunkan jadi teks (render tak boleh gagal karena tabel). Mengembalikan N."""
    nomor = 0
    for bab in (context.get("bab") or {}).values():
        for sub in bab.get("subbab", []):
            for i, c in enumerate(sub.get("content", [])):
                if c.get("type") != "table":
                    continue
                try:
                    c["subdoc"] = build_table_subdoc(c, nomor + 1)
                    nomor += 1
                except Exception as e:
                    logger.warning("Tabel dirender sebagai teks: %s", e)
                    sub["content"][i] = {"type": "text", "isi": table_as_text(c)}
    return nomor


def restart_daftar_numbering(docx_obj, num_id: int = DAFTAR_NUM_ID) -> int:
    """Tiap kelompok paragraf berurutan ber-numId `num_id` mendapat w:num baru (abstrak sama, mulai 1),
    sehingga Rumusan Masalah, Tujuan, dst. masing-masing bernomor 1), 2), ... Mengembalikan jumlah kelompok."""
    body = docx_obj.element.body
    try:
        numbering = docx_obj.part.numbering_part.element
    except Exception:  # template tanpa numbering.xml
        return 0
    src = next((n for n in numbering.findall(qn("w:num")) if n.get(qn("w:numId")) == str(num_id)), None)
    if src is None:
        return 0
    abstract = src.find(qn("w:abstractNumId")).get(qn("w:val"))
    next_id = max(int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))) + 1
    groups, prev_in = 0, False
    current = str(num_id)
    for el in body:
        nid = el.find(f"./{qn('w:pPr')}/{qn('w:numPr')}/{qn('w:numId')}") if el.tag == qn("w:p") else None
        is_in = nid is not None and nid.get(qn("w:val")) == str(num_id)
        if is_in and not prev_in:
            groups += 1
            if groups > 1:
                current = str(next_id)
                next_id += 1
                num = OxmlElement("w:num")
                num.set(qn("w:numId"), current)
                a = OxmlElement("w:abstractNumId")
                a.set(qn("w:val"), abstract)
                num.append(a)
                ov = OxmlElement("w:lvlOverride")
                ov.set(qn("w:ilvl"), "0")
                so = OxmlElement("w:startOverride")
                so.set(qn("w:val"), "1")
                ov.append(so)
                num.append(ov)
                last = numbering.findall(qn("w:num"))[-1]
                last.addnext(num)
        if is_in:
            nid.set(qn("w:val"), current)
        prev_in = is_in
    return groups


class DocxConverter:
    """
    Utility class to convert a Makalah data object into a formatted .docx document
    using Jinja2 templating and docxtpl.

    Example:
    --------
    converter = DocxConverter("template.docx", "output/makalah.docx")
    converter.convert(makalah_state)
    """

    def __init__(self, template_path: str, output_path: Optional[str] = None,
                 logo_path: Optional[str] = None, neutral_logo: bool = False,
                 template_mode: Optional[str] = None):
        """
        Parameters
        ----------
        template_path : str
            Path to the .docx template file.
        output_path : Optional[str]
            Path to save the rendered .docx file. If not provided, will auto-generate one.
        logo_path : Optional[str]
            PNG/JPEG logo kampus/sekolah untuk sampul (divalidasi dan dinormalkan oleh malas.logo).
        neutral_logo : bool
            Tanpa logo_path: True = ganti logo bawaan template dengan penanda netral "LOGO"; False = biarkan.
        template_mode : Optional[str]
            'indexed' (template lama: indeks sub-bab tetap) atau 'generic' (template v3: loop per sub-bab).
            None = dideteksi dari ISI template (`template_check.detect_template_mode`), bukan dari nama berkas,
            sehingga template yang diganti nama tetap dikenali.
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found at: {template_path}")

        self.template_path = template_path
        self.output_path = output_path or self._default_output_path()
        self.logo_path = logo_path
        self.neutral_logo = neutral_logo
        if template_mode not in (None, MODE_INDEXED, MODE_GENERIC):
            raise ValueError(f"template_mode tidak dikenal: {template_mode}")
        self.template_mode = template_mode or detect_template_mode(template_path)
        # True bila sampul memakai penanda netral "LOGO" atau logo bawaan template (tanpa logo pengguna);
        # diisi ulang oleh convert() dan dicatat main.py sebagai stats["logo_placeholder"].
        self.logo_placeholder = not logo_path
        self.jinja_env = Environment(trim_blocks=True, lstrip_blocks=True)


    def _default_output_path(self) -> str:
        """Generate a default output filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join("output", f"makalah_{timestamp}.docx")

    def _generate_context(self, makalah_state: Makalah) -> Dict[str, Any]:
        """Prepare the context dictionary for rendering."""
        context = makalah_state.model_dump(mode='python')

        # Urutan tampil APA (alfabet nama keluarga penulis pertama, tahun, judul); state tidak diubah.
        daftar_pustaka_asli = sorted(context.get('daftar_pustaka', []), key=apa_sort_key)
        segmen = [[[xml_safe(t), it] for t, it in format_apa7_segments(ref)] for ref in daftar_pustaka_asli]
        context['daftar_pustaka_formatted'] = ["".join(t for t, _ in seg) for seg in segmen]
        # teks utuh -> [[teks, italik], ...]: dipakai _ApaDocxTemplate; template polos mengabaikannya
        context['daftar_pustaka_segmen'] = {"".join(t for t, _ in seg): seg for seg in segmen}

        # Template memakai {{univ}} setelah kata "UNIVERSITAS" dan {{formatted_date}}
        # (juga "FAKULTAS"/"JURUSAN"), jadi awalan yang sama di data dibuang agar tidak dobel.
        for key, prefix in (("univ", "universitas"), ("fakultas", "fakultas"), ("jurusan", "jurusan")):
            sumber = context.get("universitas" if key == "univ" else key, "")
            context[key] = re.sub(rf"^\s*{prefix}\s+", "", sumber, flags=re.I)
        context["formatted_date"] = f"{context.get('kota', '')}, {_tanggal_indonesia(datetime.now())}"
        kp = str(context.get("kata_pengantar") or "")
        context["kata_pengantar_paragraf"] = [ln.strip() for ln in kp.split("\n") if ln.strip()]
        context["template_mode"] = self.template_mode
        normalize_for_template(context, self.template_mode)

        # Tambahkan daftar alfabet untuk enumerasi (a, b, c, ...)
        context["alphabet"] = [chr(ord("a") + i) for i in range(26)]
        return xml_safe(context)

    def _render(self, doc: DocxTemplate, context: Dict[str, Any]) -> None:
        """Render satu objek template. Mode generic: tabel -> fragmen XML sebelum render, lalu
        penomoran daftar dimulai ulang per sub-bab setelah render."""
        if self.template_mode == MODE_GENERIC:
            attach_table_subdocs(context)
        doc.render(context, jinja_env=self.jinja_env, autoescape=True)
        if self.template_mode == MODE_GENERIC:
            try:
                restart_daftar_numbering(doc.docx)
            except Exception as e:  # penomoran bersambung lebih baik daripada render gagal
                logger.warning("Penomoran ulang daftar dilewati: %s", e)

    def convert(self, makalah_state: Makalah) -> str:
        """
        Render the makalah into a .docx file.

        Returns
        -------
        str
            The path of the generated .docx file.
        """
        try:
            context = self._generate_context(makalah_state)
            try:
                doc = _ApaDocxTemplate(self.template_path)
                self._render(doc, context)
            except Exception as e:  # italik gagal -> render ulang teks polos (perilaku lama)
                logger.warning("Render daftar pustaka ber-italik gagal, kembali ke teks polos: %s", e)
                doc = DocxTemplate(self.template_path)
                self._render(doc, context)

            output_dir = os.path.dirname(self.output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            doc.save(self.output_path)

            logo_png = normalize_logo(Path(self.logo_path).read_bytes()) if self.logo_path else None
            apply_logo(self.output_path, logo_png, self.neutral_logo)
            self.logo_placeholder = logo_png is None

            return self.output_path

        except Exception as e:
            raise RuntimeError(f"Gagal merender makalah ke DOCX: {e}") from e

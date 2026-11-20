"""Konversi state Makalah menjadi file .docx via docxtpl (Jinja2 di dalam template Word)."""
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from docxtpl import DocxTemplate
from jinja2 import Environment

from malas.apa import apa_sort_key, format_apa7, format_apa7_segments  # noqa: F401  (format_apa7: re-export)
from malas.crews.models.TaskOutput import Makalah
from malas.logo import apply_logo, normalize_logo

logger = logging.getLogger(__name__)

_BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
          "Agustus", "September", "Oktober", "November", "Desember"]


def _tanggal_indonesia(d: datetime) -> str:
    return f"{d.day} {_BULAN[d.month - 1]} {d.year}"


def _as_text(contents: list) -> list:
    """Paksa semua item konten jadi tipe 'text' (list -> baris teks).

    Template memakai c['isi'] untuk bagian naratif (Latar Belakang, Kesimpulan),
    jadi item bertipe list dari LLM harus diratakan agar tidak merusak render.
    """
    out = []
    for c in contents:
        if c.get("type") == "list":
            lines = ([c["title_items"]] if c.get("title_items") else []) + [f"- {i}" for i in c.get("items", [])]
            out.append({"type": "text", "isi": "\n".join(lines)})
        else:
            out.append(c)
    return out


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


def normalize_for_template(context: Dict[str, Any]) -> Dict[str, Any]:
    """Samakan bentuk data LLM dengan asumsi template (Bab I: teks/list/list, Bab III: teks)."""
    bab = context.get("bab", {})

    def subs(key):
        return bab.get(key, {}).get("subbab", [])

    for key in bab:  # nomor hanya dihapus di tampilan; state/checkpoint/kunci refsearch tetap memakai judul bernomor
        for sub in subs(key):
            sub["judul"] = strip_heading_number(sub.get("judul", ""))
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
                 logo_path: Optional[str] = None, neutral_logo: bool = False):
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
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found at: {template_path}")

        self.template_path = template_path
        self.output_path = output_path or self._default_output_path()
        self.logo_path = logo_path
        self.neutral_logo = neutral_logo
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
        normalize_for_template(context)

        # Tambahkan daftar alfabet untuk enumerasi (a, b, c, ...)
        context["alphabet"] = [chr(ord("a") + i) for i in range(26)]
        return xml_safe(context)

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
                doc.render(context, jinja_env=self.jinja_env, autoescape=True)
            except Exception as e:  # italik gagal -> render ulang teks polos (perilaku lama)
                logger.warning("Render daftar pustaka ber-italik gagal, kembali ke teks polos: %s", e)
                doc = DocxTemplate(self.template_path)
                doc.render(context, jinja_env=self.jinja_env, autoescape=True)

            output_dir = os.path.dirname(self.output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            doc.save(self.output_path)

            logo_png = normalize_logo(Path(self.logo_path).read_bytes()) if self.logo_path else None
            apply_logo(self.output_path, logo_png, self.neutral_logo)

            return self.output_path

        except Exception as e:
            raise RuntimeError(f"Gagal merender makalah ke DOCX: {e}") from e

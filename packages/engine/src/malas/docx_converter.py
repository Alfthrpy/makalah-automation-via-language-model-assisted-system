"""Konversi state Makalah menjadi file .docx via docxtpl (Jinja2 di dalam template Word)."""
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from docxtpl import DocxTemplate
from jinja2 import Environment

from malas.citations import is_institution
from malas.crews.models.TaskOutput import Makalah
from malas.logo import apply_logo, normalize_logo

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


def _as_list(contents: list) -> list:
    """Paksa konten jadi satu item 'list' (template memakai content[0]['items']).

    Teks naratif dipecah per baris dan penanda butir ("- ", "1.", "a)") dibuang.
    """
    items: list = []
    for c in contents:
        if c.get("type") == "list":
            items.extend(c.get("items", []))
        else:
            for line in str(c.get("isi", "")).splitlines():
                line = re.sub(r"^\s*(?:[-*\u2022]|\d+[.)]|[a-zA-Z][.)])\s+", "", line).strip()
                if line:
                    items.append(line)
    return [{"type": "list", "title_items": None, "items": items}]


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

    for idx, sub in enumerate(subs("I")):
        sub["content"] = _as_text(sub["content"]) if idx == 0 else _as_list(sub["content"])
    for sub in subs("III"):
        sub["content"] = _as_text(sub["content"])
    return context


def format_apa7(ref):
    """
    Mengubah sebuah dictionary referensi menjadi string berformat APA 7.

    Args:
        ref (dict): Dictionary yang berisi 'authors', 'year', 'title', dan 'link'.

    Returns:
        str: String referensi yang sudah diformat.
    """
    
    # --- 1. Memformat Nama Penulis ---
    authors_list = ref.get('authors', [])
    formatted_authors = []
    for name in authors_list:
        parts = name.split()
        if not parts:
            continue
        if is_institution(name):  # lembaga ("Wikipedia", "Badan Pusat Statistik"): tulis utuh
            formatted_authors.append(" ".join(parts))
            continue
        last_name = parts[-1]
        # Membuat inisial dari nama depan/tengah; "JA" (inisial kapital dari sumber) -> "J. A."
        initials = " ".join(
            f"{ch}." for p in parts[:-1] for ch in (p if p.isalpha() and p.isupper() and len(p) <= 3 else p[0])
        )
        formatted_authors.append(f"{last_name}, {initials}")

    # Menggabungkan daftar penulis dengan koma dan ampersand (&)
    num_authors = len(formatted_authors)
    if num_authors == 0:
        authors_str = "Penulis tidak diketahui"
    elif num_authors == 1:
        authors_str = formatted_authors[0]
    elif num_authors == 2:
        authors_str = f"{formatted_authors[0]} & {formatted_authors[1]}"
    else:
        # Gabungkan semua kecuali yang terakhir dengan koma, lalu tambahkan '&'
        authors_str = ", ".join(formatted_authors[:-1]) + f", & {formatted_authors[-1]}"
    
    # --- 2. Memformat Tahun ---
    year = ref.get('year', 'n.d.') # 'n.d.' berarti 'no date'
    year_str = f"({year})."

    # --- 3. Memformat Judul ---
    # APA 7 menggunakan sentence case untuk judul artikel.
    title = ref.get('title', 'Judul tidak diketahui').strip()
    # Ini adalah cara sederhana untuk membuat sentence case
    title_str = title[0].upper() + title[1:] + "."

    # --- 4. Mengambil Link ---
    link = ref.get('link') or ''

    # --- 5. Menggabungkan Semua Bagian ---
    # Format: Penulis. (Tahun). Judul artikel. Link
    final_reference = f"{authors_str.rstrip('.')}. {year_str} {title_str} {link}"
    
    return final_reference


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

        daftar_pustaka_asli = context.get('daftar_pustaka', [])
        daftar_pustaka_terformat = [format_apa7(ref) for ref in daftar_pustaka_asli]
        context['daftar_pustaka_formatted'] = daftar_pustaka_terformat

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

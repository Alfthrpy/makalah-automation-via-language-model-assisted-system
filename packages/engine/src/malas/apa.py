"""Pemformat daftar pustaka APA 7 (S03): segmen teks + italik, sentence case tanpa LLM, kunci urut alfabet.

Contoh keluaran jurnal (nama jurnal dan volume italik)::

    Utami, R. (2024). Gamifikasi dalam pembelajaran bahasa Arab di lembaga pendidikan Indonesia.
    Nun: Journal of Arabic Studies, 4(2), 36–52. https://doi.org/10.56633/nun.v4i2.1634

Sumber tunggal: `format_apa7_segments(ref) -> [(teks, italik), ...]`; `format_apa7` = gabungan teksnya.
`ref` adalah dict hasil `ReferenceItem.model_dump()`; field baru (`volume`, `issue`, `pages`) opsional sehingga
data/checkpoint lama tetap bisa dirender dalam bentuk lama ``Penulis. (Tahun). Judul. Tautan``.
Nama penulis selalu dilewatkan ke `names.normalize_author` (idempoten) agar data lama "Given Family" benar.
"""
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping

from malas.names import family_of, is_institution, normalize_author

Segment = tuple[str, bool]

# Kata (huruf, boleh bersambung ' / ’ / -): "Qur'an", "Al-Qur'an", "e-learning". Angka bukan bagian kata.
_WORD = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_SENT_END = re.compile(r"[:.?!][\s\"'()\[\]“”‘’]*$")
_VOWELS = set("aeiouAEIOU")

# Nama diri umum (konteks makalah Indonesia) yang wajib berhuruf kapital walau tanpa sinyal data.
DEFAULT_PROTECTED: set[str] = {
    "Indonesia", "Indonesian", "Islam", "Islamic", "Arab", "Arabic", "Qur'an", "Al-Qur'an", "Alquran", "Quran",
    "Quranic", "Allah", "Muhammad", "Muslim", "Muslims", "Jawa", "Javanese", "Sunda", "Melayu", "Malay", "Malaysia",
    "Madura", "Bali", "Sumatera", "Kalimantan", "Sulawesi", "Papua", "Aceh", "Jakarta", "Nusantara", "Pancasila",
    "Inggris", "English", "Eropa", "Europe", "Asia", "Asian", "Kristen", "Katolik", "Hindu", "Buddha", "Ramadan",
    "Ramadhan", "COVID", "PAI", "PBA", "SD", "SMP", "SMA", "SMK", "MI", "MTs", "UIN", "IAIN", "STEM",
    "TIK", "ICT", "AI", "IPA", "IPS",
}
# Kata umum yang sering dikapitalkan di abstrak/nama lembaga tetapi bukan nama diri di judul.
_STOP = {
    "bahasa", "pendidikan", "agama", "pembelajaran", "penelitian", "studi", "jurnal", "journal", "kajian",
    "universitas", "university", "sekolah", "the", "of", "and", "in", "dan", "di", "ke", "dari", "yang",
}


def _key(tok: str) -> str:
    return tok.replace("’", "'").casefold()


def _mode(text: str, protected: Mapping[str, str]) -> str | None:
    """'caps' (≥60% huruf kapital), 'title' (≥70% kata ≥4 huruf berawal kapital), atau None (biarkan)."""
    words = _WORD.findall(text)
    if len(words) < 3:
        return None
    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) >= 0.6:
        return "caps"
    long_ = [w for w in words if len(w) >= 4 and _key(w) not in protected]  # nama diri tidak dihitung
    if len(long_) >= 3 and sum(w[0].isupper() for w in long_) / len(long_) >= 0.7:
        return "title"
    return None


def _protected_map(protected: Iterable[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in list(DEFAULT_PROTECTED) + [p for p in protected if p]:
        out[_key(p)] = p  # sinyal data (urutan belakang) menang atas daftar bawaan
    return out


def _case_token(tok: str, start: bool, mode: str, in_paren: bool, prot: Mapping[str, str]) -> str:
    hit = prot.get(_key(tok))
    if hit:
        return hit
    if "-" in tok:  # "E-LEARNING" -> "e-learning"; tiap bagian dicek terpisah ("Meta-Analysis", "Pasca-COVID")
        parts = tok.split("-")
        return "-".join(_case_token(p, start and i == 0, mode, False, prot) for i, p in enumerate(parts))
    if any(c.isupper() for c in tok[1:]) and any(c.islower() for c in tok):  # "iPhone", "YouTube", "MTs"
        return tok
    letters = [c for c in tok if c.isalpha()]
    if tok.isupper():
        if mode == "title" and 2 <= len(letters) <= 5:  # akronim di judul Title-Case
            return tok
        if mode == "caps" and ((in_paren and len(letters) <= 6) or (len(letters) <= 4 and not _VOWELS & set(tok))):
            return tok  # judul KAPITAL: akronim hanya bila dalam kurung "(PAI)" atau tanpa vokal "SMP"
    low = tok.lower()
    return low[:1].upper() + low[1:] if start else low


def to_sentence_case(title: str, protected: set[str] | None = None) -> str:
    """Ubah judul KAPITAL / Title-Case menjadi sentence case (APA 7). Judul lain dikembalikan apa adanya.

    Dipertahankan: huruf pertama, huruf setelah titik dua, akronim (KAPITAL ≤5 huruf pada judul Title-Case;
    dalam kurung atau tanpa vokal pada judul KAPITAL), token berkapital di tengah ("iPhone"), serta nama diri
    dari `protected` + `DEFAULT_PROTECTED` (bentuk tulisan diambil dari daftar, mis. "Al-Qur'an").
    """
    if not title:
        return title
    prot = _protected_map(protected or ())
    mode = _mode(title, prot)
    if not mode:
        return title
    out, pos = [], 0
    for i, m in enumerate(_WORD.finditer(title)):
        seg = title[pos:m.start()]
        start = i == 0 or bool(_SENT_END.search(seg))
        in_paren = seg.endswith("(") and title[m.end():m.end() + 1] == ")"
        out.append(seg)
        out.append(_case_token(m.group(0), start, mode, in_paren, prot))
        pos = m.end()
    out.append(title[pos:])
    return "".join(out)


def protected_from(ref: Mapping) -> set[str]:
    """Sinyal nama diri dari data referensi (tanpa LLM).

    - abstrak (`excerpt`): kata berkapital di TENGAH kalimat lebih sering daripada huruf kecil ("Arab", "PAI");
      abstrak yang sendirinya KAPITAL diabaikan.
    - `venue`: hanya akronim/kata ber-kapital-tengah ("JIPI"); kata lain di nama jurnal selalu Title-Case.
    - penulis: nama keluarga (bukan lembaga).
    """
    out: set[str] = set()
    excerpt = str(ref.get("excerpt") or "")
    if excerpt and _mode(excerpt, {}) != "caps":
        cap: dict[str, int] = {}
        low: dict[str, int] = {}
        form: dict[str, str] = {}
        pos = 0
        for i, m in enumerate(_WORD.finditer(excerpt)):
            tok, seg = m.group(0), excerpt[pos:m.start()]
            pos = m.end()
            if i == 0 or _SENT_END.search(seg):
                continue
            k = _key(tok)
            if tok[0].isupper():
                cap[k] = cap.get(k, 0) + 1
                form[k] = tok
            else:
                low[k] = low.get(k, 0) + 1
        out |= {form[k] for k, n in cap.items() if n > low.get(k, 0) and k not in _STOP and len(k) >= 2}
    for tok in _WORD.findall(str(ref.get("venue") or "")):
        if (tok.isupper() and len(tok) >= 2) or (any(c.isupper() for c in tok[1:]) and any(c.islower() for c in tok)):
            out.add(tok)
    for a in ref.get("authors") or []:
        a = str(a or "")
        if a and not is_institution(a):
            out |= {t for t in _WORD.findall(family_of(a)) if len(t) >= 3 and t[0].isupper() and _key(t) not in _STOP}
    return out


def sentence_case_enabled() -> bool:
    return os.getenv("MALAS_APA_SENTENCECASE", "1").strip().lower() not in ("0", "false", "off", "no")


# --------------------------------------------------------------------------- pemformat
def _clean(v) -> str:
    return " ".join(str(v).split()) if v is not None else ""


def _end(s: str) -> str:
    """Akhiri dengan titik kecuali sudah berakhir . ? ! (hindari "..")."""
    s = s.rstrip()
    return s if not s or s[-1] in ".?!" else s + "."


def join_authors(authors: list[str]) -> str:
    """1: "A, X." · 2: "A, X. & B, Y." · ≥3: "A, X., B, Y., & C, Z." (perilaku lama dipertahankan)."""
    if not authors:
        return ""
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} & {authors[1]}"
    return ", ".join(authors[:-1]) + f", & {authors[-1]}"


def _authors(ref: Mapping) -> list[str]:
    return [a for a in (normalize_author(_clean(x)) for x in (ref.get("authors") or [])) if a]


def _pages(p: str) -> str:
    return re.sub(r"(?<=\w)\s*[-‐-‒—]+\s*(?=\w)", "–", p)


def _doi_link(doi: str) -> str:
    d = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi.strip(), flags=re.IGNORECASE)
    return f"https://doi.org/{d}" if d else ""


def format_apa7_segments(ref: Mapping) -> list[Segment]:
    """Referensi -> daftar (teks, italik). Gabungan teksnya = `format_apa7(ref)`.

    Italik APA 7: nama jurnal + volume (bukan issue); bila tidak ada jurnal (buku/laman), judul yang italik.
    Tanpa penulis: judul menggantikan posisi penulis (sebelum tahun).
    """
    authors = _authors(ref)
    year = ref.get("year")
    year_s = _clean(year) if year not in (None, "", 0, "0") else "n.d."
    title = _clean(ref.get("title")) or "Judul tidak diketahui"
    if sentence_case_enabled():
        title = to_sentence_case(title, protected_from(ref))
    title = _end(title[:1].upper() + title[1:])
    venue = _clean(ref.get("venue")).rstrip(" .,")
    volume, issue = _clean(ref.get("volume")), _clean(ref.get("issue"))
    pages = _pages(_clean(ref.get("pages")))
    link = _doi_link(_clean(ref.get("doi"))) if ref.get("doi") else _clean(ref.get("link"))

    segs: list[Segment] = []

    def add(text: str, italic: bool = False) -> None:
        if not text:
            return
        if segs and segs[-1][1] == italic:
            segs[-1] = (segs[-1][0] + text, italic)
        else:
            segs.append((text, italic))

    title_italic = not venue
    if authors:
        add(f"{_end(join_authors(authors))} ({year_s}). ")
        add(title, title_italic)
    else:
        add(title, title_italic)
        add(f" ({year_s}).")
    if venue:
        add(" ")
        add(venue + (f", {volume}" if volume else ""), True)
        tail = f"({issue})" if issue and volume else ""
        add(_end(tail + (f", {pages}" if pages else "")) if (tail or pages) else ".")
    if link:
        add(" " + link)
    return segs


def format_apa7(ref: Mapping) -> str:
    """Referensi (dict `ReferenceItem`) -> string APA 7 (teks polos, kompatibel mundur)."""
    return "".join(t for t, _ in format_apa7_segments(ref))


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"^[\W_]+", "", s).casefold()


def apa_sort_key(ref: Mapping) -> tuple[str, int, str]:
    """Kunci urut daftar pustaka: (nama keluarga penulis pertama | judul, tahun, judul), tanpa diakritik."""
    authors = _authors(ref)
    title = _clean(ref.get("title"))
    try:
        year = int(str(ref.get("year") or 0)[:4])
    except ValueError:
        year = 0
    first = family_of(authors[0]) if authors else title
    return _fold(first), year, _fold(title)

"""Rencana query per sub-bab. Heuristik murni kode; opsional diperkaya SATU panggilan LLM murah."""
import json
import re
from typing import Callable, Dict, List, Optional, Tuple

from malas.refsearch.models import SectionQuery

BIDANG = ("medis", "teknik", "sains", "sosial", "hukum", "agama", "ekonomi", "humaniora", "pendidikan", "umum")

# Judul sub-bab generik tidak membawa topik: dibuang dari query, topik diambil dari judul makalah.
_GENERIC = re.compile(
    r"\b(latar belakang|pendahuluan|pembahasan|landasan teori|tinjauan pustaka|kajian teori|analisis|interpretasi|"
    r"data|informasi|studi kasus|contoh|implikasi|penelitian|tantangan|keterbatasan|potensi|lanjutan|kesimpulan|"
    r"saran|tujuan|penulisan|rumusan masalah|dan|serta|atau|di|ke|dari|yang|untuk)\b", re.I)
# Penanda topik LOKAL Indonesia. Kata sambung (dan/yang/di/untuk/...) sengaja TIDAK di sini: kata sambung hanya
# menandakan judul berbahasa Indonesia, bukan topik khas Indonesia (RC-05: hampir semua judul jadi indo=True).
_ID_LOKAL = re.compile(
    r"\b(indonesia|indonesian|nasional|daerah|islam|islami|syariah|syariat|hukum|pancasila|undang|perda|kuhp|kuhap|"
    r"desa|adat|pesantren|madrasah|nusantara|aceh|sumatera|sumatra|riau|jambi|bengkulu|lampung|bangka|jawa|jakarta|"
    r"banten|bandung|bogor|depok|bekasi|tangerang|yogyakarta|jogja|semarang|surabaya|malang|surakarta|bali|lombok|"
    r"kalimantan|pontianak|banjarmasin|samarinda|balikpapan|sulawesi|makassar|manado|gorontalo|maluku|ambon|papua|"
    r"medan|padang|palembang|pekanbaru|kupang|mataram|ntb|ntt)\b", re.I)
# Sub-bab bertipe konsep/teori -> pass karya dasar (landmark) dan k lebih besar.
_KONSEP_SUB = re.compile(r"\b(konsep|teori|teoritis|teoretis|landasan|tinjauan|kerangka|definisi|dasar|pengertian)\b",
                         re.I)
_STOP = {"untuk", "dan", "di", "terhadap", "pada", "dalam", "dengan", "yang", "sebagai", "oleh", "dari", "ke", "serta",
         "atau", "melalui", "berbasis", "bagi", "antara", "tentang", "era", "secara", "studi", "kasus"}

# Glosarium kasar ID -> EN untuk rencana TANPA LLM (fallback). Nilai: (teks Inggris untuk query, konsep landmark
# atau None). Teks kosong = kata dibuang dari query Inggris (kata kerja/penanda generik). Frasa panjang didahulukan.
_K = "konsep"
_GLOSARIUM: Dict[str, Tuple[str, Optional[str]]] = {
    # konsep/teori (dipakai juga sebagai query landmark)
    "gamifikasi": ("gamification", _K), "motivasi belajar": ("learning motivation", "motivation"),
    "motivasi": ("motivation", _K), "media sosial": ("social media", _K), "kesehatan mental": ("mental health", _K),
    "tindak pidana korupsi": ("corruption", _K), "korupsi": ("corruption", _K), "hukum pidana": ("criminal law", _K),
    "machine learning": ("machine learning", _K), "pembelajaran mesin": ("machine learning", _K),
    "deep learning": ("deep learning", _K), "kecerdasan buatan": ("artificial intelligence", _K),
    "deteksi penipuan": ("fraud detection", _K), "penipuan": ("fraud", _K),
    "pemasaran digital": ("digital marketing", _K), "ekonomi syariah": ("islamic economics", _K),
    "ekonomi islam": ("islamic economics", _K), "perbankan syariah": ("islamic banking", _K),
    "akuntansi syariah": ("islamic accounting", _K), "kepuasan kerja": ("job satisfaction", _K),
    "kinerja karyawan": ("employee performance", _K), "kepemimpinan": ("leadership", _K),
    "literasi digital": ("digital literacy", _K), "literasi keuangan": ("financial literacy", _K),
    "pendidikan karakter": ("character education", _K), "efikasi diri": ("self-efficacy", _K),
    "kecemasan": ("anxiety", _K), "depresi": ("depression", _K), "stres": ("stress", _K),
    "perilaku konsumen": ("consumer behavior", _K), "loyalitas pelanggan": ("customer loyalty", _K),
    "kepuasan pelanggan": ("customer satisfaction", _K), "keputusan pembelian": ("purchase decision", _K),
    "e-commerce": ("e-commerce", _K), "perubahan iklim": ("climate change", _K),
    "pembangunan berkelanjutan": ("sustainable development", _K), "tata kelola": ("governance", _K),
    "kewirausahaan": ("entrepreneurship", _K), "inovasi": ("innovation", _K),
    "pembelajaran daring": ("online learning", _K), "pembelajaran berbasis proyek": ("project-based learning", _K),
    "blockchain": ("blockchain", _K), "internet of things": ("internet of things", _K), "big data": ("big data", _K),
    "jaringan saraf": ("neural network", _K), "stunting": ("stunting", _K), "diabetes": ("diabetes", _K),
    "hipertensi": ("hypertension", _K), "stroke": ("stroke", _K), "fisioterapi": ("physiotherapy", _K),
    "gizi": ("nutrition", _K), "pajak": ("taxation", _K), "akuntansi": ("accounting", _K),
    "tafsir": ("quranic exegesis", _K), "pariwisata": ("tourism", _K), "kemiskinan": ("poverty", _K),
    # kata biasa (hanya query Inggris)
    "bahasa arab": ("arabic language", None), "bahasa inggris": ("english language", None),
    "transaksi keuangan": ("financial transactions", None), "usaha mikro kecil dan menengah": ("MSMEs", None),
    "pelayanan publik": ("public service", None), "remaja": ("adolescents", None), "belajar": ("learning", None),
    "pembelajaran": ("learning", None), "pendidikan": ("education", None), "siswa": ("students", None),
    "mahasiswa": ("university students", None), "guru": ("teachers", None), "sekolah": ("school", None),
    "anak": ("children", None), "kesehatan": ("health", None), "hukum": ("law", None), "pidana": ("criminal", None),
    "tindak": ("", None), "transaksi": ("transactions", None), "keuangan": ("finance", None),
    "deteksi": ("detection", None), "sistem": ("system", None), "informasi": ("information", None),
    "teknologi": ("technology", None), "digital": ("digital", None), "pemasaran": ("marketing", None),
    "strategi": ("strategy", None), "ekonomi": ("economy", None), "umkm": ("MSMEs", None),
    "sejarah": ("history", None), "kerajaan": ("kingdom", None), "pengaruh": ("", None), "pengaruhnya": ("", None),
    "dampak": ("impact", None), "peran": ("role", None), "efektivitas": ("effectiveness", None),
    "implementasi": ("", None), "penerapan": ("", None), "meningkatkan": ("", None), "peningkatan": ("", None),
    "analisis": ("", None), "kajian": ("", None), "tinjauan": ("", None), "perusahaan": ("company", None),
    "bank": ("bank", None), "kebijakan": ("policy", None), "pemerintah": ("government", None),
    "masyarakat": ("society", None), "budaya": ("culture", None), "agama": ("religion", None),
    "perempuan": ("women", None), "karyawan": ("employees", None), "kinerja": ("performance", None),
    "kualitas": ("quality", None), "layanan": ("service", None), "pasien": ("patients", None),
    "lingkungan": ("environment", None), "energi": ("energy", None), "produk": ("product", None),
    "konsumen": ("consumer", None), "penjualan": ("sales", None), "model": ("model", None),
    "metode": ("method", None), "algoritma": ("algorithm", None), "klasifikasi": ("classification", None),
    "prediksi": ("prediction", None), "keamanan": ("security", None), "data": ("data", None),
    "learning": ("learning", None), "machine": ("machine", None),
    # penanda tipe sub-bab: tidak membawa topik
    "konsep": ("", None), "teori": ("", None), "landasan": ("", None), "definisi": ("", None), "dasar": ("", None),
    "pengertian": ("", None), "kerangka": ("", None), "terdahulu": ("", None),
}
_GLOS_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in sorted(_GLOSARIUM, key=len, reverse=True)) + r")\b",
                      re.I)


def strip_number(section: str) -> str:
    # angka ("2.1") atau romawi BERTANDA BACA ("II." / "IV)"); jangan memotong kata biasa ("Implementasi")
    return re.sub(r"^\s*(?i:bab\s+)?(?:\d+(?:\.\d+)*[.)]?|[IVX]+[.)])\s*", "", section).strip()


def is_indo(teks: str) -> bool:
    """Topik khas Indonesia? Hanya dari penanda topik lokal, BUKAN dari kata sambung berbahasa Indonesia."""
    return bool(_ID_LOKAL.search(teks or ""))


def section_role(section: str) -> str:
    """'landmark' untuk sub-bab konsep/teori dan 1.1 (latar belakang butuh karya dasar), selain itu 'recent'."""
    if re.match(r"^\s*1\.1\b", section) or _KONSEP_SUB.search(strip_number(section)):
        return "landmark"
    return "recent"


def translate_rough(teks: str, min_cover: float = 0.6) -> Tuple[str, List[str]]:
    """Terjemahan kasar berbasis glosarium -> (query Inggris, konsep landmark). Kosong bila cakupan < min_cover.

    Kata yang tak dikenal (nama diri: Majapahit, Nusantara) dipertahankan apa adanya.
    """
    words: List[str] = []
    konsep: List[str] = []
    total = known = 0
    pos = 0
    for m in list(_GLOS_RE.finditer(teks)) + [None]:
        gap = teks[pos:m.start()] if m else teks[pos:]
        for w in re.findall(r"[\w\-']+", gap):
            if w.lower() in _STOP or w.isdigit() or not re.search(r"[^\W\d_]", w):
                continue
            total += 1
            words.append(w)
        if m is None:
            break
        en, kon = _GLOSARIUM[m.group(1).lower()]
        n = len([w for w in m.group(1).split() if w.lower() not in _STOP])
        total += n
        known += n
        if en:
            words.append(en)
        if kon:
            k = en if kon == _K else kon
            if k.lower() not in (x.lower() for x in konsep):
                konsep.append(k)
        pos = m.end()
    if not total or known / total < min_cover:
        return "", []
    q = " ".join(dict.fromkeys(" ".join(words).split()))  # buang kata ganda, urutan tetap
    return q, konsep


def heuristic_plan(judul: str, sections: List[str]) -> List[SectionQuery]:
    indo = is_indo(judul)
    judul_en, judul_kon = translate_rough(judul)
    out = []
    for s in sections:
        sub = " ".join(_GENERIC.sub(" ", strip_number(s)).split())
        q = " ".join(f"{judul} {sub}".split())
        sub_en, sub_kon = translate_rough(sub) if sub else ("", [])
        q_en = " ".join(dict.fromkeys(f"{judul_en} {sub_en}".split())) if judul_en else ""
        role = section_role(s)
        terms = list(dict.fromkeys(sub_kon + judul_kon)) if role == "landmark" else []
        out.append(SectionQuery(section=s, q_en=q_en, q_id=q, bidang="umum", indo=indo or is_indo(sub),
                                role=role, landmark_terms=terms))
    return out


def _prompt(judul: str, mata_kuliah: str, sections: List[str]) -> str:
    listing = "\n".join(f"- {s}" for s in sections)
    return (
        "Anda membantu mencari literatur akademik untuk sebuah makalah mahasiswa Indonesia.\n"
        f'Judul makalah: "{judul}"\nMata kuliah: "{mata_kuliah}"\nSub-bab yang butuh referensi:\n{listing}\n\n'
        "Untuk SETIAP sub-bab buat query pencarian jurnal. Jawab HANYA JSON valid (tanpa teks lain) berbentuk:\n"
        '{"<judul sub-bab persis seperti di atas>": {"q_en": "<=8 kata kunci bahasa Inggris", '
        '"q_id": "<=8 kata kunci bahasa Indonesia", '
        f'"bidang": "salah satu dari {"|".join(BIDANG)}", "indo": true jika topik spesifik Indonesia (hukum/budaya/kebijakan/'
        'sejarah/agama lokal) selain itu false, "konsep": ["<=2 konsep/teori inti dalam bahasa Inggris, 1-3 kata, '
        "mis. gamification, self-determination theory\"]}}\n"
        "Query harus spesifik pada topik sub-bab DAN judul makalah, bukan kata generik seperti 'latar belakang'."
    )


def _parse_json(text: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, dict) else None
    except ValueError:
        return None


def _konsep(v) -> List[str]:
    """Daftar konsep dari LLM: hanya string pendek (1-4 kata), maks 2."""
    if isinstance(v, str):
        v = [v]
    if not isinstance(v, list):
        return []
    out = [" ".join(str(x).split())[:60] for x in v if isinstance(x, str) and 0 < len(str(x).split()) <= 4]
    return out[:2]


def llm_plan(judul: str, mata_kuliah: str, sections: List[str], call: Callable[[str], str]) -> List[SectionQuery]:
    """Satu panggilan LLM -> query EN+ID per sub-bab. Gagal/tak lengkap -> bagian itu jatuh ke heuristik."""
    base = heuristic_plan(judul, sections)
    try:
        prompt = _prompt(judul, mata_kuliah, sections)
        data = _parse_json(call(prompt)) or {}
    except Exception:
        return base
    norm: Dict[str, dict] = {strip_number(k).lower(): v for k, v in data.items() if isinstance(v, dict)}
    out = []
    for sq in base:
        d = norm.get(strip_number(sq.section).lower()) or {}
        q_en, q_id = str(d.get("q_en") or "").strip(), str(d.get("q_id") or "").strip()
        bidang = str(d.get("bidang") or "").lower()
        terms = (_konsep(d.get("konsep")) or sq.landmark_terms) if sq.role == "landmark" else []
        out.append(SectionQuery(
            section=sq.section,
            q_en=(q_en or sq.q_en)[:120],
            q_id=(q_id or sq.q_id)[:120],
            bidang=bidang if bidang in BIDANG else sq.bidang,
            indo=bool(d["indo"]) if isinstance(d.get("indo"), bool) else sq.indo,
            role=sq.role,
            landmark_terms=terms,
        ))
    return out

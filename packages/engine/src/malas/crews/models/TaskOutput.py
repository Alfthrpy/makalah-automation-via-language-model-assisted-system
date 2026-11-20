from typing import List, Dict, Union, Literal, Optional
from pydantic import BaseModel, Field

from malas.enhance.models import Blueprint, EvidenceCard, Finding

# Model untuk struktur outline sederhana (seperti yang kita gunakan sebelumnya)
class SimpleSubbab(BaseModel):
    sections: List[str] = []

class Outline(BaseModel):
    subbabs: Dict[str, SimpleSubbab] = {}


# Model untuk struktur referensi
class ReferenceItem(BaseModel):
    title: str
    authors: List[str]
    year: int
    link: Optional[str] = None
    excerpt: Optional[str] = Field(
        default=None,
        description="Abstract/ringkasan singkat dari sumber, diambil langsung dari hasil pencarian (bukan full-text).",
    )
    # --- metadata dari pencarian deterministik (refsearch); semua opsional agar checkpoint lama tetap valid ---
    doi: Optional[str] = None
    source: Optional[str] = None  # openalex | crossref | europepmc | arxiv | doaj | ...
    source_id: Optional[str] = None
    oa_pdf_url: Optional[str] = None  # URL PDF open-access bila sudah diketahui dari sumber
    venue: Optional[str] = None
    volume: Optional[str] = None  # nomor volume jurnal (string apa adanya dari sumber, mis. "4")
    issue: Optional[str] = None  # nomor terbitan, mis. "2"
    pages: Optional[str] = None  # rentang halaman dengan en dash, mis. "36–52"
    sections: List[str] = Field(default_factory=list, description="Judul sub-bab yang memakai referensi ini.")

class References(BaseModel):
    references: List[ReferenceItem] = []


# Model untuk struktur konten yang kompleks di dalam makalah
class ContentText(BaseModel):
    type: Literal["text"] = 'text'
    isi: str = Field(description="Isi teks dari konten.")

class ContentList(BaseModel):
    type: Literal["list"] = 'list'
    title_items: Optional[str] = None
    items: List[str] = Field(description="List of items.")

class ContentTable(BaseModel):
    """Tabel (mis. sintesis studi). Dirakit KODE dari kartu bukti, bukan ditulis LLM penulis."""
    type: Literal["table"] = 'table'
    caption: str = ""
    header: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)

# Union type untuk konten
ContentItem = Union[ContentText, ContentList, ContentTable]

class KataPengantar(BaseModel):
    isi: str = Field(description="Teks kata pengantar lengkap; paragraf dipisah baris baru.")


# Model untuk struktur Makalah yang detail
class Penyusun(BaseModel):
    nama: str = "PetaniHandal"
    nim: str = "1234567890"

class SubBab(BaseModel):
    judul: str
    content: List[ContentItem] = Field(default_factory=list, description="List of content items.")
    # narasi = paragraf; daftar = butir bernomor (Rumusan Masalah/Tujuan/Manfaat/Saran). Kosong = tebak dari judul.
    kind: Literal["narasi", "daftar"] = "narasi"

class Bab(BaseModel):
    judul: str = ''
    subbab: List[SubBab] = Field(default_factory=list) # Menggunakan SubBab yang kompleks

class Makalah(BaseModel):
    judul: str = "Judul Makalah"
    mata_kuliah: str = "Nama Mata Kuliah"
    dosen_pengampu: str = "Nama Dosen"
    penyusun: List[Penyusun] = []
    kelas: str = "Kelas"
    universitas: str = "Nama Universitas"
    fakultas: str = "Nama Fakultas"
    jurusan: str =  "Nama Jurusan"
    kota: str = "Kota"
    tahun: str = "2024"
    # lingkup (opsional; diisi pengguna atau diinferensi): mencegah subjek melenceng (siswa vs mahasiswa)
    jenis_makalah: str = "kajian_pustaka"
    subjek: str = ""
    jenjang: str = ""
    kata_pengantar: str = "Kata Pengantar"
    bab: Dict[str, Bab] = Field(default_factory=dict)
    daftar_pustaka: List[ReferenceItem] = [] # Sebaiknya gunakan ReferenceItem agar lebih terstruktur
    # Enhancing Engine (semua opsional agar checkpoint lama tetap valid)
    blueprint: Optional[Blueprint] = None
    evidence: Dict[str, EvidenceCard] = Field(default_factory=dict)  # kunci = ref_key
    quality: List[Finding] = Field(default_factory=list)
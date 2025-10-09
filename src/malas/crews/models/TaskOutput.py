from typing import List, Dict, Union, Literal, Optional
from pydantic import BaseModel, Field

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

# Union type untuk konten
ContentItem = Union[ContentText, ContentList]

# Model untuk struktur Makalah yang detail
class Penyusun(BaseModel):
    nama: str = "PetaniHandal"
    nim: str = "1234567890"

class SubBab(BaseModel):
    judul: str
    content: List[ContentItem] = Field(default_factory=list, description="List of content items.")

class Bab(BaseModel):
    judul: str = ''
    subbab: List[SubBab] = Field(default_factory=list) # Menggunakan SubBab yang kompleks
    kesimpulan: Optional[str] = None

class Makalah(BaseModel):
    judul_makalah: str = "Judul Makalah"
    mata_kuliah: str = "Nama Mata Kuliah"
    dosen_pengampu: str = "Nama Dosen"
    penyusun: List[Penyusun] = []
    kelas: str = "Kelas"
    universitas: str = "Nama Universitas"
    fakultas: str = "Nama Fakultas"
    jurusan: str =  "Nama Jurusan"
    kota: str = "Kota"
    tahun: str = "2024"
    kata_pengantar: str = "Kata Pengantar"
    bab: Dict[str, Bab] = Field(default_factory=dict)
    daftar_pustaka: List[ReferenceItem] = [] # Sebaiknya gunakan ReferenceItem agar lebih terstruktur
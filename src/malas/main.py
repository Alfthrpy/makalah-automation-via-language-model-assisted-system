#!/usr/bin/env python
from random import randint
from pydantic import BaseModel
from crewai.flow import Flow, listen, start
from malas.crews.planner_crew.planner_crew import PlannerCrew


from pydantic import BaseModel, Field
from typing import List, Dict, Union, Literal, Optional




# Model dari pertanyaan sebelumnya
class Penyusun(BaseModel):
    nama: str = "PetaniHandal"
    nim: str = "1234567890"

# Model untuk konten di dalam sub-bab (bisa teks atau list)
class ContentText(BaseModel):
    type: Literal["text"]
    isi: str = Field(description="Isi teks dari konten.")

class ContentList(BaseModel):
    type: Literal["list"]
    title_items: Optional[str] = None
    items: List[str] = Field(description="List of items.")

# Union type untuk memperbolehkan beberapa jenis model dalam satu field
ContentItem = Union[ContentText, ContentList]

# Model untuk setiap Sub-bab
class SubBab(BaseModel):
    judul: str
    content: List[ContentItem] = Field(default_factory=list,description="List of content items, can be text or a list.")

# Model untuk setiap Bab
class Bab(BaseModel):
    judul: str = 'Bab 1'
    latar_belakang: Optional[str] = None
    rumusan_masalah: Optional[List[str]] = None
    tujuan: Optional[List[str]] = None
    subbab: Optional[List[SubBab]] = None
    kesimpulan: Optional[str] = None

# Model Utama untuk keseluruhan Makalah
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
    bab: Dict[str, Bab] = {}
    daftar_pustaka: List[str] = []


def debugState(state):
    print("Current State:")
    for key, value in state.dict().items():
        print(f"{key}: {value}")


class MalasFlow(Flow[Makalah]):

    @start()
    def inputDataMakalah(self):
        self.state.judul_makalah = "Sistem Rekomendasi Berbasis Machine Learning"
        self.state.mata_kuliah = "Kecerdasan Buatan"
        self.state.dosen_pengampu = "Dr. Budi Santoso"
        self.state.penyusun = [
            Penyusun(nama="Aldilla Ulinnaja", nim="123456789"),
            Penyusun(nama="Muhammad Rizki", nim="987654321"),
        ]
        self.state.kelas = "IF-4"
        self.state.universitas = "Universitas Teknologi Nusantara"
        self.state.fakultas = "Fakultas Teknik"
        self.state.jurusan = "Teknik Informatika"
        self.state.kota = "Bandung"
        self.state.tahun = 2025
        print("Data berhasil disimpan.")


    @listen(inputDataMakalah)
    def generate_outline(self):
        print("Generating outline...")
        planner = PlannerCrew()
        planner.use_mockup = True  # aktifkan mode mock
        crew_instance = planner.crew()

        # Jalankan flow (tidak akan call LLM)
        crew_instance.kickoff()

        # Akses output
        outline_output = planner.tasks[0].output
        references_output = planner.tasks[1].output

        roman_numerals = ["I", "II", "III", "IV", "V"]


        for i, (bab_title, simple_subbab_data) in enumerate(outline_output.pydantic.subbabs.items()):
            # Buat Bab baru
            bab_baru = Bab(judul=bab_title)

            # Buat list untuk menampung semua SubBab baru
            subbab_list = []

            # Untuk SETIAP baris di sections, buat satu objek SubBab
            for section_title in simple_subbab_data.sections:
                cleaned_title = section_title.strip()
                if cleaned_title: # Pastikan tidak memproses baris kosong
                    new_subbab = SubBab(judul=cleaned_title) # Content otomatis kosong
                    subbab_list.append(new_subbab)

            # Masukkan list SubBab yang sudah jadi ke dalam Bab
            bab_baru.subbab = subbab_list

            # Tambahkan Bab ke dalam makalah
            bab_key = roman_numerals[i]
            self.state.bab[bab_key] = bab_baru

        debugState(self.state)  # Debug state setelah menambahkan setiap bab




def kickoff():
    malas_flow = MalasFlow()
    malas_flow.kickoff()


def plot():
    malas_flow = MalasFlow()
    malas_flow.plot()


if __name__ == "__main__":
    kickoff()

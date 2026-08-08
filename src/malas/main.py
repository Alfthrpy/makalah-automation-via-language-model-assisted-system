#!/usr/bin/env python
import os
import re
import sys
from typing import Dict, List

# Windows console default (cp1252) tidak bisa encode emoji yang dipakai di print()
# statement di seluruh flow ini - tanpa ini proses crash begitu print emoji pertama jalan.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
from crewai.flow import Flow, listen, start
import logging
from pydantic import BaseModel
from malas.crews.planner_crew.planner_crew import PlannerCrew
from malas.crews.models.TaskOutput import (
    Penyusun, 
    ContentText, 
    ContentList,
    ReferenceItem, 
    SubBab, 
    Bab, 
    Makalah
)
from malas.crews.write_format_crew.write_format_crew import WriteFormatCrew
from tests.utils import DocxConverter

# Diasumsikan semua import yang dibutuhkan sudah ada di atas
# import os, re, logging, etc.

class MalasFlow(Flow[Makalah]):
    """
    Flow untuk mengotomatisasi proses pembuatan makalah, mulai dari
    input data awal, pembuatan outline, pengisian konten, hingga finalisasi.
    """


    @start()
    def inputDataMakalah(self):
        """Langkah awal: Mengisi data dasar untuk makalah."""
        self.state.judul = "Sistem Rekomendasi Berbasis Machine Learning"
        self.state.mata_kuliah = "Kecerdasan Buatan"
        self.state.dosen_pengampu = "Dr. Budi Santoso"
        self.state.penyusun = [
            Penyusun(nama="Al-Fathir", nim="123456789"),
            Penyusun(nama="Muhammad Rizki", nim="987654321"),
        ]
        self.state.kelas = "IF-4"
        self.state.universitas = "Universitas Teknologi Nusantara"
        self.state.fakultas = "Fakultas Teknik"
        self.state.jurusan = "Teknik Informatika"
        self.state.kota = "Bandung"
        self.state.tahun = 2025
        print("✅ Data awal makalah berhasil disimpan.")

    @listen(inputDataMakalah)
    def generate_outline(self):
        """Membuat struktur Bab dan Sub-bab berdasarkan judul makalah."""
        planner = PlannerCrew()
        crew_instance = planner.crew()

        crew_instance.kickoff(inputs={
            "judul_makalah": self.state.judul,
            "mata_kuliah": self.state.mata_kuliah,
        })

        outline_output = planner.tasks[0].output
        references_output = planner.tasks[1].output
        
        # Proses output menjadi struktur Bab dan SubBab
        roman_numerals = ["I", "II", "III", "IV", "V"]
        for i, (bab_title, subbab_data) in enumerate(outline_output.pydantic.subbabs.items()):
            bab_baru = Bab(judul=bab_title)
            list_subbab = []
            
            for section_title in subbab_data.sections:
                cleaned_title = section_title.strip()
                if cleaned_title:
                    list_subbab.append(SubBab(judul=cleaned_title))
            
            bab_baru.subbab = list_subbab
            self.state.bab[roman_numerals[i]] = bab_baru
            
        self.state.daftar_pustaka = references_output.pydantic.references
        print("🗺️ Outline dan daftar pustaka berhasil dibuat.")

    @listen(generate_outline)
    def fill_subbab_content(self):
        """Mengisi konten untuk setiap sub-bab secara sekuensial."""
        writer = WriteFormatCrew()
        crew_instance = writer.crew()
        generated_contents = {}

        for bab_key, bab in self.state.bab.items():
            for subbab_index, subbab in enumerate(bab.subbab):
                print(f"\n✍️ Mengerjakan: {bab.judul} - {subbab.judul}")

                # 1. Siapkan konteks dari konten sub-bab sebelumnya
                formatted_previous_content = ""
                if subbab_index > 0:
                    previous_subbab = bab.subbab[subbab_index - 1]
                    if previous_subbab.judul in generated_contents:
                        content_objects = generated_contents[previous_subbab.judul]
                        header = f"Konten dari Sub-Bab sebelumnya '{previous_subbab.judul}':"
                        content_parts = []
                        for item in content_objects:
                            if isinstance(item, ContentText):
                                content_parts.append(item.isi)
                            elif isinstance(item, ContentList):
                                if item.title_items:
                                    content_parts.append(item.title_items)
                                formatted_items = "\n".join([f"- {li}" for li in item.items])
                                content_parts.append(formatted_items)
                        
                        full_content_str = "\n".join(content_parts)
                        formatted_previous_content = f"{header}\n{full_content_str}"

                # 2. Jalankan crew untuk menghasilkan konten sub-bab saat ini
                inputs = {
                    "bab_now": bab.judul,
                    "subbab_now": subbab.judul,
                    "previous_subab_contents": formatted_previous_content,
                    "references": [
                        {
                            "title": ref.title,
                            "authors": ref.authors,
                            "year": ref.year,
                            "link": ref.link,
                            "excerpt": ref.excerpt,
                        }
                        for ref in self.state.daftar_pustaka if ref.link
                    ],
                    "judul_makalah": self.state.judul,
                    "mata_kuliah": self.state.mata_kuliah,
                }
                crew_instance.kickoff(inputs=inputs)

                # 3. Simpan output ke state utama dan state sementara
                subbab_output = writer.tasks[0].output
                if subbab_output and subbab_output.pydantic:
                    new_content = subbab_output.pydantic.content
                    subbab.content = new_content
                    generated_contents[subbab.judul] = new_content

        print("\n✅ Semua konten sub-bab telah diisi.")

    @listen(fill_subbab_content)
    def finalize_and_save(self):
        """Langkah akhir: Konversi state akhir ke format DOCX."""
        print("\n🏁 Finalisasi flow, menyimpan hasil ke file DOCX...")
        docx_converter = DocxConverter("template_and_output/template makalah.docx",hardcoded=False)
        docx_converter.convert(self.state)
        print("🎉 Makalah berhasil dibuat!")


def kickoff():
    malas_flow = MalasFlow()
    malas_flow.kickoff()


if __name__ == "__main__":
    kickoff()

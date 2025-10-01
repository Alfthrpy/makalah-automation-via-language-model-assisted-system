#!/usr/bin/env python
from random import randint
from pydantic import BaseModel
from crewai.flow import Flow, listen, start
from malas.crews.planner_crew.planner_crew import PlannerCrew


from pydantic import BaseModel, Field
from malas.crews.models.TaskOutput import (
    Penyusun, 
    ContentText, 
    ContentList, 
    ContentItem, 
    SubBab, 
    Bab, 
    Makalah
)
from malas.crews.write_format_crew.write_format_crew import WriteFormatCrew



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
        planner = PlannerCrew()
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

        self.state.daftar_pustaka = references_output.pydantic.references

    @listen(generate_outline)
    def fill_subbab_content(self):
        writer = WriteFormatCrew()
        crew_instance = writer.crew()
        generated_contents = {}

        for bab_key, bab in self.state.bab.items():
            for subbab_index, subbab in enumerate(bab.subbab):
                
                formatted_previous_content = ""
                
                if subbab_index > 0:
                    previous_subbab = bab.subbab[subbab_index - 1]
                    
                    # <<< 2. BACA DARI PENYIMPANAN SEMENTARA
                    # Cek apakah konten untuk sub-bab sebelumnya ada di 'generated_contents'
                    if previous_subbab.judul in generated_contents:
                        previous_content_objects = generated_contents[previous_subbab.judul]
                        print(previous_content_objects)
                        
                        header = f"Konten dari Sub-Bab sebelumnya'{previous_subbab.judul}':"
                        content_parts = []
                        for item in previous_content_objects:
                            if isinstance(item, ContentText):
                                content_parts.append(item.isi)
                            elif isinstance(item, ContentList):
                                if item.title_items:
                                    content_parts.append(item.title_items)
                                formatted_items = "\n".join([f"- {li}" for li in item.items])
                                content_parts.append(formatted_items)
                        
                        full_content_str = "\n".join(content_parts)
                        formatted_previous_content = f"{header}\n{full_content_str}"

                print(f"\n>>>> Mengerjakan: {bab.judul} - {subbab.judul}")
                # print(f"Menggunakan Konteks:\n{formatted_previous_content}\n<<<<\n")

                crew_instance.kickoff(inputs={
                    "bab_now": bab.judul,
                    "subbab_now": subbab.judul,
                    "previous_subab_contents": formatted_previous_content,
                    "references": [getattr(ref, 'title', str(ref)) for ref in self.state.daftar_pustaka]
                })
                
                subbab_output = writer.tasks[0].output
                
                if subbab_output and subbab_output.pydantic:
                    # <<< 3. SIMPAN KE STATE UTAMA DAN PENYIMPANAN SEMENTARA
                    new_content = subbab_output.pydantic.content
                    subbab.content = new_content  # Update state utama
                    generated_contents[subbab.judul] = new_content # Update penyimpanan sementara
                
        debugState(self.state)




def kickoff():
    malas_flow = MalasFlow()
    malas_flow.kickoff()


def plot():
    malas_flow = MalasFlow()
    malas_flow.plot()


if __name__ == "__main__":
    kickoff()

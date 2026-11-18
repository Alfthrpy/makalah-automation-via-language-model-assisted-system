#!/usr/bin/env python
import argparse
import os
import sys
from pathlib import Path

import yaml

# Windows console default (cp1252) tidak bisa encode emoji yang dipakai di print()
# statement di seluruh flow ini - tanpa ini proses crash begitu print emoji pertama jalan.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
# Matikan prompt interaktif 'view execution traces' bawaan CrewAI.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
from crewai.flow import Flow, listen, start
from malas.crews.planner_crew.planner_crew import PlannerCrew
from malas.crews.models.TaskOutput import (
    Penyusun, 
    SubBab, 
    Bab, 
    Makalah
)
from malas.crews.write_format_crew.write_format_crew import WriteFormatCrew
from malas.citations import (
    check_citations, citation_label, content_text, prune_unused_references,
)
from malas.crews.finishing_crew.finishing_crews import run_citation_fix, run_kata_pengantar
from malas.docx_converter import DocxConverter
from malas.fulltext import FullTextStore

DEFAULT_INPUT = "input/contoh.yaml"
DEFAULT_TEMPLATE = "template_and_output/template makalah.docx"
FULLTEXT_CACHE = Path(".cache/fulltext")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def load_input(path: str) -> dict:
    """Baca data makalah (judul, penyusun, kampus, ...) dari file YAML."""
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(f"File input tidak ditemukan: {path}")
    return yaml.safe_load(file.read_text(encoding="utf-8")) or {}


class MalasFlow(Flow[Makalah]):
    """
    Flow untuk mengotomatisasi proses pembuatan makalah, mulai dari
    input data awal, pembuatan outline, pengisian konten, hingga finalisasi.
    """


    input_path: str = DEFAULT_INPUT
    template_path: str = DEFAULT_TEMPLATE
    output_path: str | None = None

    @start()
    def inputDataMakalah(self):
        """Langkah awal: muat data dasar makalah dari file YAML."""
        data = load_input(self.input_path)
        if not data.get("judul"):
            raise ValueError(f"Field 'judul' wajib diisi di {self.input_path}")
        penyusun = [Penyusun(**p) for p in data.pop("penyusun", [])]
        data["tahun"] = str(data.get("tahun", self.state.tahun))
        for key, value in {**data, "penyusun": penyusun}.items():
            setattr(self.state, key, value)
        print(f"✅ Data makalah dimuat dari {self.input_path}")

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

    def _references_for(self, subbab_judul: str) -> list[dict]:
        """Referensi untuk prompt Writer: abstrak + (jika ada) beberapa kutipan full-text relevan.

        Total kutipan dibatasi MALAS_FULLTEXT_CHARS (default 3000 karakter ~ 750 token) per sub-bab.
        """
        store = self.fulltext
        punya_teks = [i for i, r in enumerate(self.state.daftar_pustaka) if r.link and i in store.texts]
        jatah = _env_int("MALAS_FULLTEXT_CHARS", 3000) // max(len(punya_teks), 1)
        hasil = []
        for i, ref in enumerate(self.state.daftar_pustaka):
            if not ref.link:
                continue
            item = {
                "sitasi": citation_label(ref),
                "title": ref.title,
                "authors": ref.authors,
                "year": ref.year,
                "link": ref.link,
                "excerpt": ref.excerpt,
            }
            kutipan = store.passages(i, ref, f"{subbab_judul} {self.state.judul}", jatah) if i in store.texts else []
            if kutipan:
                item["kutipan"] = kutipan
            hasil.append(item)
        return hasil

    @listen(generate_outline)
    def fetch_fulltexts(self):
        """Unduh full-text referensi open-access (tanpa LLM). Gagal = lanjut hanya dengan abstrak."""
        self.fulltext = FullTextStore()
        if os.getenv("MALAS_FULLTEXT", "1") == "0":
            print("⏭️  Full-text referensi dimatikan (MALAS_FULLTEXT=0).")
            return
        total = len(self.state.daftar_pustaka)
        berhasil = self.fulltext.load(self.state.daftar_pustaka, FULLTEXT_CACHE)
        print(f"📄 Full-text berhasil diambil: {berhasil}/{total} referensi (sisanya memakai abstrak).")

    @listen(fetch_fulltexts)
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
                        header = f"Konten dari Sub-Bab sebelumnya '{previous_subbab.judul}':"
                        full_content_str = content_text(generated_contents[previous_subbab.judul])
                        formatted_previous_content = f"{header}\n{full_content_str}"

                # 2. Jalankan crew untuk menghasilkan konten sub-bab saat ini
                inputs = {
                    "bab_now": bab.judul,
                    "subbab_now": subbab.judul,
                    "previous_subab_contents": formatted_previous_content,
                    "references": self._references_for(subbab.judul),
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
    def verify_citations(self):
        """Cek sitasi in-text vs daftar pustaka; perbaiki sub-bab bermasalah (1x), buang pustaka tak terpakai."""
        report = check_citations(self.state)
        print(f"\n🔎 Sitasi ditemukan: {report.total_citations}; "
              f"sub-bab dengan sitasi tidak sah: {len(report.invalid)}")

        if report.invalid:
            refs = [
                {"sitasi": citation_label(r), "title": r.title, "authors": r.authors, "year": r.year}
                for r in self.state.daftar_pustaka
            ]
            subbab_by_title = {sb.judul: sb for bab in self.state.bab.values() for sb in bab.subbab}
            for judul, tidak_valid in report.invalid.items():
                print(f"🛠️  Memperbaiki sitasi di {judul}: {tidak_valid}")
                perbaikan = run_citation_fix({
                    "judul_makalah": self.state.judul,
                    "subbab_now": judul,
                    "sitasi_tidak_valid": ", ".join(tidak_valid),
                    "references": refs,
                    "konten": content_text(subbab_by_title[judul].content),
                })
                if perbaikan and perbaikan.content:
                    subbab_by_title[judul].content = perbaikan.content

            report = check_citations(self.state)
            for judul, tidak_valid in report.invalid.items():
                print(f"⚠️  Masih ada sitasi tidak sah di {judul}: {tidak_valid} (periksa manual)")

        dibuang = prune_unused_references(self.state, report)
        if dibuang:
            print(f"🧹 {dibuang} referensi tidak dikutip dibuang dari daftar pustaka.")

    @listen(verify_citations)
    def write_kata_pengantar(self):
        """Tulis Kata Pengantar dari data makalah."""
        isi = run_kata_pengantar({
            "judul_makalah": self.state.judul,
            "mata_kuliah": self.state.mata_kuliah,
            "dosen_pengampu": self.state.dosen_pengampu,
            "penyusun": ", ".join(p.nama for p in self.state.penyusun),
            "kota": self.state.kota,
            "tahun": self.state.tahun,
        })
        if isi:
            self.state.kata_pengantar = isi
            print("📝 Kata pengantar berhasil dibuat.")
        else:
            print("⚠️  Kata pengantar gagal dibuat; memakai teks default.")

    @listen(write_kata_pengantar)
    def finalize_and_save(self):
        """Langkah akhir: Konversi state akhir ke format DOCX."""
        print("\n🏁 Finalisasi flow, menyimpan hasil ke file DOCX...")
        converter = DocxConverter(self.template_path, self.output_path)
        hasil = converter.convert(self.state)
        print(f"🎉 Makalah berhasil dibuat: {hasil}")


def kickoff():
    parser = argparse.ArgumentParser(description="MALAS - generator makalah otomatis")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="File YAML data makalah")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="Template .docx")
    parser.add_argument("--output", default=None, help="Path file .docx hasil (default: output/makalah_<waktu>.docx)")
    args = parser.parse_args()

    flow = MalasFlow()
    flow.input_path, flow.template_path, flow.output_path = args.input, args.template, args.output
    flow.kickoff()


if __name__ == "__main__":
    kickoff()

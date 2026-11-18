#!/usr/bin/env python
import argparse
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Optional

import yaml

# Windows console default (cp1252) tidak bisa encode emoji yang dipakai di print()
# statement di seluruh flow ini - tanpa ini proses crash begitu print emoji pertama jalan.
for _stream in (sys.stdout, sys.stderr):
    _enc = getattr(_stream, "encoding", None)
    if _enc and _enc.lower() != "utf-8" and hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")
# Matikan prompt interaktif 'view execution traces' bawaan CrewAI.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")  # telemetry CrewAI: tanpa ini ada error koneksi berisik saat offline
from crewai.flow import Flow, listen, start

from malas import checkpoint
from malas.citations import (
    check_citations, citation_label, content_text, prune_unused_references,
)
from malas.crews.finishing_crew.finishing_crews import run_citation_fix, run_kata_pengantar
from malas.crews.models.TaskOutput import Bab, Makalah, Penyusun, SubBab
from malas.crews.planner_crew.planner_crew import PlannerCrew
from malas.crews.write_format_crew.write_format_crew import WriteFormatCrew
from malas.docx_converter import DocxConverter
from malas.fulltext import FullTextStore

DEFAULT_INPUT = "input/contoh.yaml"
DEFAULT_TEMPLATE = "template_and_output/template makalah.docx"
FULLTEXT_CACHE = Path(".cache/fulltext")

# Callback progres: (kunci_tahap, status, detail). status: running | done | skipped | error | info
ProgressCallback = Callable[[str, str, str], None]

# Galat yang tidak ada gunanya diulang (key salah, saldo habis, model tidak ada, akses ditolak).
_FATAL = ("api key", "api_key", "authentication", "unauthorized", "invalid_argument", "no auth", "401", "403",
          "forbidden", "insufficient", "credit", "402", "payment", "model not found", "does not exist", "no endpoints")


def is_fatal_error(e: Exception) -> bool:
    low = str(e).lower()
    return any(k in low for k in _FATAL)


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

    Atribut yang bisa diatur sebelum kickoff():
      input_data    dict data makalah (menggantikan input_path)
      input_path    file YAML data makalah
      template_path template .docx
      output_path   path .docx hasil
      progress      callback (tahap, status, detail) untuk UI
    Setelah selesai: `usage` (token) dan `stats` (ringkasan) terisi.
    """

    input_data: Optional[dict] = None
    input_path: str = DEFAULT_INPUT
    template_path: str = DEFAULT_TEMPLATE
    output_path: str | None = None
    progress: Optional[ProgressCallback] = None
    checkpoint_path: Optional[Path] = None  # tulis checkpoint di sini (None = nonaktif)
    resume: bool = False  # True = pakai checkpoint yang sudah ada

    # --- pelaporan -----------------------------------------------------------------
    def _emit(self, step: str, status: str, detail: str = "") -> None:
        if self.progress:
            self.progress(step, status, detail)

    @contextmanager
    def _stage(self, step: str):
        self._emit(step, "running")
        try:
            yield
        except Exception as e:
            # Detail di UI cukup nama jenis error; pesan ramah dibuat web/jobs.py, traceback ada di konsol server.
            self._emit(step, "error", e.__class__.__name__)
            raise
        self._emit(step, "done")

    def _ensure_counters(self) -> None:
        if not hasattr(self, "usage"):
            self.usage = {"calls": 0, "prompt": 0, "completion": 0, "total": 0}
            self.stats: dict = {}

    def _save_checkpoint(self) -> None:
        if self.checkpoint_path:
            try:
                checkpoint.save(self.checkpoint_path, self.state, self.usage, self.stats)
            except OSError:
                pass  # checkpoint hanya optimasi; jangan menggagalkan job

    def _resume_data(self) -> Optional[dict]:
        return checkpoint.load(self.checkpoint_path) if (self.resume and self.checkpoint_path) else None

    def _add_usage(self, crew_output) -> None:
        self._ensure_counters()
        u = getattr(crew_output, "token_usage", None)
        if u is None:
            return
        self.usage["calls"] += int(getattr(u, "successful_requests", 0) or 0)
        self.usage["prompt"] += int(getattr(u, "prompt_tokens", 0) or 0)
        self.usage["completion"] += int(getattr(u, "completion_tokens", 0) or 0)
        self.usage["total"] += int(getattr(u, "total_tokens", 0) or 0)

    # --- tahap ---------------------------------------------------------------------
    @start()
    def inputDataMakalah(self):
        """Langkah awal: muat data dasar makalah (dict dari UI atau file YAML)."""
        self._ensure_counters()
        with self._stage("input"):
            data = dict(self.input_data) if self.input_data is not None else load_input(self.input_path)
            if not data.get("judul"):
                raise ValueError("Field 'judul' wajib diisi")
            penyusun = [Penyusun(**p) for p in data.pop("penyusun", [])]
            data["tahun"] = str(data.get("tahun", self.state.tahun))
            for key, value in {**data, "penyusun": penyusun}.items():
                setattr(self.state, key, value)
            print("✅ Data makalah dimuat.")

    @listen(inputDataMakalah)
    def generate_outline(self):
        """Membuat struktur Bab dan Sub-bab berdasarkan judul makalah."""
        with self._stage("outline"):
            ck = self._resume_data()
            if ck and ck["meta"]["outline"]:
                restored = Makalah.model_validate(ck["state"])
                self.state.bab = restored.bab
                self.state.daftar_pustaka = restored.daftar_pustaka
                self.usage.update(ck.get("usage") or {})
                self.stats.update(ck.get("stats") or {})
                m = ck["meta"]
                print("♻️ Melanjutkan dari checkpoint.")
                self._emit("outline", "info",
                           f"memakai hasil sebelumnya ({m['done']}/{m['total']} sub-bab sudah ditulis)")
                return
            planner = PlannerCrew()
            crew_instance = planner.crew()

            hasil = crew_instance.kickoff(inputs={
                "judul_makalah": self.state.judul,
                "mata_kuliah": self.state.mata_kuliah,
            })
            self._add_usage(hasil)

            outline_output = planner.tasks[0].output
            references_output = planner.tasks[1].output
            if not (outline_output and outline_output.pydantic and references_output and references_output.pydantic):
                raise RuntimeError("Planner tidak menghasilkan outline/referensi yang valid (output bukan JSON sesuai skema)")

            # Proses output menjadi struktur Bab dan SubBab
            roman_numerals = ["I", "II", "III", "IV", "V"]
            for i, (bab_title, subbab_data) in enumerate(outline_output.pydantic.subbabs.items()):
                if i >= len(roman_numerals):
                    break
                bab_baru = Bab(judul=bab_title)
                bab_baru.subbab = [SubBab(judul=t.strip()) for t in subbab_data.sections if t.strip()]
                self.state.bab[roman_numerals[i]] = bab_baru

            self.state.daftar_pustaka = references_output.pydantic.references
            self.stats["subbab_count"] = sum(len(b.subbab) for b in self.state.bab.values())
            self.stats["refs_found"] = len(self.state.daftar_pustaka)
            print("🗺️ Outline dan daftar pustaka berhasil dibuat.")
            self._emit("outline", "info",
                       f"{self.stats['subbab_count']} sub-bab, {self.stats['refs_found']} referensi")
            self._save_checkpoint()  # outline = ± 5 menit kerja; jangan sampai hilang bila tahap berikutnya gagal

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

    def _write_subbab(self, crew, writer, inputs: dict, judul: str):
        """Jalankan Writer untuk satu sub-bab; ulangi 1x untuk galat sementara/keluaran kosong.

        Galat fatal (key salah, saldo habis, model tidak ada) langsung dilempar. Bila tetap gagal,
        job berhenti dengan checkpoint utuh sehingga bisa dilanjutkan tanpa mengulang yang sudah jadi.
        """
        last: Exception = RuntimeError(f"Sub-bab '{judul}' tidak menghasilkan isi yang valid")
        for attempt in (1, 2):
            try:
                self._add_usage(crew.kickoff(inputs=inputs))
                out = writer.tasks[0].output
                content = out.pydantic.content if out and out.pydantic else None
                if content:
                    return content
                last = RuntimeError(f"Sub-bab '{judul}' tidak menghasilkan isi yang valid")
            except Exception as e:  # noqa: BLE001
                if is_fatal_error(e):
                    raise
                last = e
            if attempt == 1:
                self._emit("tulis", "info", f"{judul}: percobaan pertama gagal, mengulang sekali…")
                time.sleep(3)
        raise last

    @listen(generate_outline)
    def fetch_fulltexts(self):
        """Unduh full-text referensi open-access (tanpa LLM). Gagal = lanjut hanya dengan abstrak."""
        self.fulltext = FullTextStore()
        if os.getenv("MALAS_FULLTEXT", "1") == "0":
            print("⏭️  Full-text referensi dimatikan (MALAS_FULLTEXT=0).")
            self._emit("fulltext", "skipped", "dimatikan (MALAS_FULLTEXT=0)")
            return
        with self._stage("fulltext"):
            total = len(self.state.daftar_pustaka)
            berhasil = self.fulltext.load(self.state.daftar_pustaka, FULLTEXT_CACHE)
            self.stats["fulltext_ok"], self.stats["fulltext_total"] = berhasil, total
            print(f"📄 Full-text berhasil diambil: {berhasil}/{total} referensi (sisanya memakai abstrak).")
            self._emit("fulltext", "info", f"{berhasil}/{total} referensi berhasil (sisanya memakai abstrak)")

    @listen(fetch_fulltexts)
    def fill_subbab_content(self):
        """Mengisi konten untuk setiap sub-bab secara sekuensial."""
        with self._stage("tulis"):
            writer = WriteFormatCrew()
            crew_instance = writer.crew()
            generated_contents = {}
            total = sum(len(b.subbab) for b in self.state.bab.values())
            nomor = 0

            for bab_key, bab in self.state.bab.items():
                for subbab_index, subbab in enumerate(bab.subbab):
                    nomor += 1
                    if subbab.content:  # sudah ditulis pada percobaan sebelumnya (checkpoint)
                        generated_contents[subbab.judul] = subbab.content
                        self._emit("tulis", "info", f"{nomor}/{total} · {subbab.judul} (sudah ada, dilewati)")
                        continue
                    print(f"\n✍️ Mengerjakan: {bab.judul} - {subbab.judul}")
                    self._emit("tulis", "info", f"{nomor}/{total} · {subbab.judul}")

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
                    # 3. Tulis (dengan 1x ulang bila gagal/kosong), lalu simpan checkpoint
                    new_content = self._write_subbab(crew_instance, writer, inputs, subbab.judul)
                    subbab.content = new_content
                    generated_contents[subbab.judul] = new_content
                    self._save_checkpoint()

            print("\n✅ Semua konten sub-bab telah diisi.")

    @listen(fill_subbab_content)
    def verify_citations(self):
        """Cek sitasi in-text vs daftar pustaka; perbaiki sub-bab bermasalah (1x), buang pustaka tak terpakai."""
        with self._stage("sitasi"):
            report = check_citations(self.state)
            awal = len(report.invalid)
            print(f"\n🔎 Sitasi ditemukan: {report.total_citations}; sub-bab dengan sitasi tidak sah: {awal}")

            if report.invalid:
                refs = [
                    {"sitasi": citation_label(r), "title": r.title, "authors": r.authors, "year": r.year}
                    for r in self.state.daftar_pustaka
                ]
                subbab_by_title = {sb.judul: sb for bab in self.state.bab.values() for sb in bab.subbab}
                for judul, tidak_valid in report.invalid.items():
                    print(f"🛠️  Memperbaiki sitasi di {judul}: {tidak_valid}")
                    self._emit("sitasi", "info", f"memperbaiki sitasi di {judul}")
                    perbaikan = run_citation_fix({
                        "judul_makalah": self.state.judul,
                        "subbab_now": judul,
                        "sitasi_tidak_valid": ", ".join(tidak_valid),
                        "references": refs,
                        "konten": content_text(subbab_by_title[judul].content),
                    }, on_usage=self._add_usage)
                    if perbaikan and perbaikan.content:
                        subbab_by_title[judul].content = perbaikan.content

                report = check_citations(self.state)
                for judul, tidak_valid in report.invalid.items():
                    print(f"⚠️  Masih ada sitasi tidak sah di {judul}: {tidak_valid} (periksa manual)")

            dibuang = prune_unused_references(self.state, report)
            if dibuang:
                print(f"🧹 {dibuang} referensi tidak dikutip dibuang dari daftar pustaka.")
            self.stats.update(
                citations_total=report.total_citations,
                citations_invalid_before=awal,
                citations_invalid_after=len(report.invalid),
                refs_final=len(self.state.daftar_pustaka),
                refs_pruned=dibuang,
            )
            self._emit("sitasi", "info",
                       f"{report.total_citations} sitasi · {len(report.invalid)} sub-bab masih bermasalah · "
                       f"{dibuang} referensi tak terpakai dibuang")

    @listen(verify_citations)
    def write_kata_pengantar(self):
        """Tulis Kata Pengantar dari data makalah."""
        with self._stage("pengantar"):
            isi = run_kata_pengantar({
                "judul_makalah": self.state.judul,
                "mata_kuliah": self.state.mata_kuliah,
                "dosen_pengampu": self.state.dosen_pengampu,
                "penyusun": ", ".join(p.nama for p in self.state.penyusun),
                "kota": self.state.kota,
                "tahun": self.state.tahun,
            }, on_usage=self._add_usage)
            if isi:
                self.state.kata_pengantar = isi
                print("📝 Kata pengantar berhasil dibuat.")
            else:
                print("⚠️  Kata pengantar gagal dibuat; memakai teks default.")
                self._emit("pengantar", "info", "gagal dibuat, memakai teks default")

    @listen(write_kata_pengantar)
    def finalize_and_save(self):
        """Langkah akhir: Konversi state akhir ke format DOCX."""
        with self._stage("docx"):
            print("\n🏁 Finalisasi flow, menyimpan hasil ke file DOCX...")
            converter = DocxConverter(self.template_path, self.output_path)
            self.result_path = converter.convert(self.state)
            print(f"🎉 Makalah berhasil dibuat: {self.result_path}")


def kickoff():
    parser = argparse.ArgumentParser(description="MALAS - generator makalah otomatis")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="File YAML data makalah")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="Template .docx")
    parser.add_argument("--output", default=None, help="Path file .docx hasil (default: output/makalah_<waktu>.docx)")
    args = parser.parse_args()

    flow = MalasFlow()
    flow.input_path, flow.template_path, flow.output_path = args.input, args.template, args.output
    flow.kickoff()
    u = getattr(flow, "usage", None)
    if u and u["total"]:
        print(f"📊 Token: {u['total']:,} (prompt {u['prompt']:,} / output {u['completion']:,}) dalam {u['calls']} panggilan.")


if __name__ == "__main__":
    kickoff()

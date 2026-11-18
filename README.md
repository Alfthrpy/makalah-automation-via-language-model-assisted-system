# Makalah Automation via Language-model Assisted System (MALAS)
MALAS (Makalah Automation via Language-model Assisted System) is a project designed to automate the process of writing academic papers ("makalah" in Indonesian). By leveraging a multi-agent system built with the `crewAI` framework, MALAS streamlines the entire workflow from research and content generation to final formatting. This system aims to assist users in producing well-structured and comprehensive academic documents efficiently.

## Fitur

- **Riset Otomatis**: Mengumpulkan informasi relevan dari web berdasarkan topik yang diberikan.
- **Penulisan Konten**: Menghasilkan draf konten untuk setiap bagian makalah (Pendahuluan, Pembahasan, Kesimpulan).
- **Struktur Dokumen**: Menyusun hasil akhir dalam format Markdown yang terstruktur.
- **Sistem Multi-Agen**: Menggunakan agen-agen khusus (Peneliti, Penulis, Peninjau) untuk menangani tugas-tugas spesifik.

## Instalasi

Prasyarat: Python 3.10–3.13, [uv](https://docs.astral.sh/uv/), dan API key penyedia LLM (default: Gemini).

```bash
git clone https://github.com/Alfthrpy/makalah-automation-via-language-model-assisted-system.git
cd makalah-automation-via-language-model-assisted-system
uv sync
```

Buat file `.env`:

```env
GEMINI_API_KEY="isi_api_key_anda"

# Opsional
# MALAS_MODEL=gemini/gemini-2.5-flash       # model untuk semua peran
# MALAS_MODEL_WRITER=...                    # override per peran (PLANNER / WRITER)
# MALAS_MOCK=1                              # LLM palsu, tanpa API call (uji alur)
```

## Cara pakai

1. Salin `input/contoh.yaml` dan isi judul, mata kuliah, penyusun, kampus.
2. Jalankan:

```bash
uv run kickoff --input input/makalah-saya.yaml
```

Opsi lain: `--template "path/template.docx"` dan `--output hasil.docx`.
Default hasil ada di `output/makalah_<waktu>.docx`.

Uji alur tanpa biaya API: `MALAS_MOCK=1 uv run kickoff`.

## Cara kerja

`PlannerCrew` membuat outline + mencari referensi (Arxiv, Semantic Scholar, CrossRef,
DuckDuckGo) -> `WriteFormatCrew` menulis tiap sub-bab dengan konteks referensi ->
`DocxConverter` merender ke template Word (`docxtpl`/Jinja2). Template per kampus dapat
diganti dengan `--template`.

## Tes

```bash
uv run pytest
```

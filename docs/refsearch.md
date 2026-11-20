# Pencarian referensi deterministik (`malas.refsearch`)

Pengganti agen LLM bertool (Arxiv / Semantic Scholar / CrossRef / DuckDuckGo) untuk tahap "cari referensi".
**Default MATI** (jalur lama tetap utuh) sampai terbukti di mesin ber-internet. Aktifkan dengan `MALAS_REFSEARCH=1`.

Titik kembali: tag git `pre-refsearch-2026-11-20` (kondisi sebelum fitur ini). Rollback cepat tanpa git: hapus `MALAS_REFSEARCH`.

## Alur
```
outline (LLM, OutlineCrew)  ->  rencana query per sub-bab (1 panggilan LLM murah; gagal = heuristik)
  -> paralel per sub-bab: OpenAlex + Crossref (+ Europe PMC | arXiv | DOAJ sesuai bidang/indonesia)
  -> dedupe (DOI / judul / kemiripan) -> skor (BM25 + RRF + prior) -> 2 referensi per sub-bab (maks dipakai 2 sub-bab)
  -> fallback: longgarkan tahun -> query judul makalah -> kosong (tanpa crash)
  -> full-text: PDF OA dari sumber -> arXiv -> Unpaywall -> Semantic Scholar -> meta citation_pdf_url (OJS) -> HTML
Writer hanya menerima referensi milik sub-bab-nya (sebelumnya: semua referensi ke tiap sub-bab).
```
LLM tidak pernah menulis judul/penulis/tahun/DOI: semuanya berasal dari respons API.

## Env
| Variabel | Fungsi |
|---|---|
| `MALAS_REFSEARCH=1` | aktifkan jalur baru |
| `MALAS_CONTACT_EMAIL` | email kontak: Crossref polite pool, Unpaywall, User-Agent. **Sangat disarankan** |
| `MALAS_OPENALEX_API_KEY` | key OpenAlex (diwajibkan sejak ±Feb 2026 menurut riset; belum diverifikasi langsung) |
| `MALAS_REF_YEAR_MIN` | tahun terlama (default: tahun ini − 10) |
| `MALAS_REFSEARCH_CACHE` | folder cache sqlite (default `.cache/refsearch`, TTL 14 hari) |

## Membuktikan bahwa pendekatan ini jalan (butuh internet)
1. Tanpa LLM, 8 topik lintas bidang, ukur semua metrik pencarian + full-text:
   ```bash
   MALAS_CONTACT_EMAIL=anda@mail.com MALAS_OPENALEX_API_KEY=... \
     uv run python -m malas.refsearch --fulltext --no-cache --json hasil.json
   ```
2. Bandingkan dengan jalur lama pada topik yang sama (butuh API key LLM). `stats` job memuat `refs_found`,
   `fulltext_ok/total`, `subbab_without_refs`, token `usage`:
   ```bash
   MALAS_REFSEARCH=0 uv run kickoff --input contoh.yaml   # lama
   MALAS_REFSEARCH=1 uv run kickoff --input contoh.yaml   # baru
   ```
   Bandingkan: token total, durasi, jumlah referensi nyata (klik DOI), hit-rate full-text, relevansi (baca manual).

## Belum terverifikasi (tes memakai fixture, bukan API sungguhan)
Bentuk respons tiap provider ditulis dari dokumentasi publik. Nama parameter key OpenAlex (`api_key`), filter
`language:id`, dan limit tiap layanan perlu dicek dengan menjalankan perintah no. 1 di atas.

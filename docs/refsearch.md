# Pencarian referensi deterministik (`malas.refsearch`)

Pengganti agen LLM bertool (Arxiv / Semantic Scholar / CrossRef / DuckDuckGo) untuk tahap "cari referensi".
**Default MATI** (jalur lama tetap utuh) sampai terbukti di mesin ber-internet. Aktifkan dengan `MALAS_REFSEARCH=1`.

Titik kembali: tag git `pre-refsearch-2026-11-20` (kondisi sebelum fitur ini). Rollback cepat tanpa git: hapus `MALAS_REFSEARCH`.

## Alur
```
outline (LLM, OutlineCrew)  ->  rencana query per sub-bab (1 panggilan LLM murah; gagal = heuristik)
  -> paralel per sub-bab: OpenAlex + Crossref (+ Europe PMC | arXiv | DOAJ sesuai bidang/indonesia)
  -> dedupe (DOI / judul / kemiripan) -> skor (BM25 + RRF + prior) -> 2 referensi per sub-bab (maks dipakai 2 sub-bab)
  -> fallback: longgarkan tahun -> query judul makalah -> Wikipedia (id/en) + Open Library (hanya bila masih kurang) -> kosong (tanpa crash)
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
| `MALAS_REF_LLM_RERANK=1` | (opsional, default mati) 1 panggilan LLM murah per sub-bab: LLM hanya memilih ID dari 6 kandidat teratas; gagal/tak terbaca = urutan deterministik. ±800 token masuk per sub-bab. Belum diuji dengan LLM sungguhan |
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

## Belum ada (rencana)
Pencarian web umum (ddgs/Brave) dengan allowlist domain, regulasi (JDIH BPK), CORE, embedding lokal. (Rerank LLM berbasis ID sudah ada, default mati.)

## Hasil uji NYATA (GitHub Actions, 2026-11-20, tanpa key & tanpa LLM; rencana query dari heuristik)
Dijalankan lewat workflow CI sementara `refsearch-probe.yml` (sudah dihapus; ada di riwayat git commit `b3d7aea`, bisa dipulihkan: `git show b3d7aea:.github/workflows/refsearch-probe.yml`).
- 8 topik lintas bidang (hukum pidana, tafsir, fisioterapi, akuntansi syariah, Majapahit, K-pop, ML, pajak UMKM):
  **32/32 sub-bab mendapat >=2 referensi**, abstrak 100%, PDF open-access diketahui 97%, **full-text berhasil 78%**.
- ~9-11 request HTTP dan 2-7 detik per topik (pencarian saja). Semua 7 API terjangkau tanpa key.
- OpenAlex tanpa key: kuota gratis bersama US$0,10/hari per IP; key gratis US$1/hari (param `api_key` terkonfirmasi).
- Bug yang ditemukan lewat uji nyata dan sudah diperbaiki: Crossref menolak `select=...language...` (HTTP 400) dan kena 429
  tanpa jeda cukup; hasil berupa `Cover.pdf` repositori kampus.
- Latensi: Crossref 4-6 dtk, Europe PMC sampai ~29 dtk (timeout bacanya dinaikkan ke 40 dtk).

## Belum terverifikasi / keterbatasan
- Rencana query dari LLM (`llm_plan`, EN+ID, bidang) belum diuji nyata; hasil di atas adalah batas bawah (heuristik).
- Relevansi bukan 100%: mis. topik Majapahit masih menyertakan 1 artikel Sriwijaya. Tanpa query Inggris, topik teknis
  (ML) hanya mendapat jurnal berbahasa Indonesia.
- Europe PMC/arXiv/Wikipedia/Open Library belum terpakai di uji karena topik uji tidak memicunya (butuh `bidang` dari LLM
  atau kasus tanpa hasil akademik).
- Perbandingan langsung dengan jalur lama (agen LLM) butuh API key LLM; belum dijalankan.

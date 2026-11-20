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
uv sync --all-packages
```

## Struktur monorepo

```
apps/api          FastAPI + antrean job (paket Python `malas_api`)
packages/engine   engine crewAI, konverter .docx, CLI `kickoff` (paket Python `malas`)
                  template .docx di src/malas/templates, contoh input di src/malas/examples
```

Roadmap SaaS (frontend React di Netlify, Neon Postgres, Clerk, backend di HF Space): lihat `HANDOFF.md`.

Buat file `.env`:

```env
GEMINI_API_KEY="isi_api_key_anda"

# Opsional
# MALAS_MODEL=gemini/gemini-2.5-flash       # model untuk semua peran
# MALAS_MODEL_WRITER=...                    # override per peran (PLANNER / WRITER / REVIEWER)
#
# Contoh OpenRouter (murah): isi OPENROUTER_API_KEY lalu
# MALAS_MODEL_PLANNER=openrouter/deepseek/deepseek-v3.2
# MALAS_MODEL_WRITER=openrouter/google/gemini-2.5-flash
# MALAS_MOCK=1                              # LLM palsu, tanpa API call (uji alur)
# MALAS_FULLTEXT=0                          # matikan pengambilan full-text referensi
# MALAS_FULLTEXT_CHARS=3000                 # batas kutipan full-text per sub-bab (~750 token)
```

## Cara pakai

### Antarmuka web (disarankan)

Backend (API) dan web dijalankan terpisah; web mem-proxy `/api` ke backend:

```bash
uv run malas-web                 # API di http://127.0.0.1:8000
pnpm install && pnpm dev:web     # web di http://localhost:5173 (VITE_AUTH_MODE=dev = tanpa Clerk)
```

Buka <http://localhost:5173>, isi formulir, lalu tekan **Buat makalah**. Halaman menampilkan
progres tiap tahap, ringkasan hasil (jumlah sub-bab, referensi, sitasi, token), tombol unduh
`.docx`, dan riwayat. Riwayat dan hasil tersimpan di database (SQLite `output/malas.db` bila `DATABASE_URL` kosong), sehingga selamat dari restart.

- **Mode uji**: centang untuk mencoba alur tanpa memanggil LLM (isi berupa teks contoh).
- **API key sendiri (BYOK)**: pengguna memilih penyedia (**OpenRouter** atau **Kenari**), menempel key,
  dan (opsional) memilih model. Kenari: `https://kenari.id/v1`, key berawalan `kn-`, model gratis
  berakhiran `:free`; id model diketik pengguna sesuai [katalog Kenari](https://kenari.id/en/docs).
  Base URL dikunci di server (bukan input pengguna) agar key tidak bisa diarahkan ke host lain.
- **Satu makalah sekaligus**: job berikutnya mengantre agar kuota API tidak berebut. Job yang
  sedang berjalan tidak bisa dihentikan di tengah jalan (CrewAI tidak mendukungnya); job yang
  masih mengantre bisa dibatalkan.
- Env opsional: `MALAS_WEB_HOST`, `MALAS_WEB_PORT`, `MALAS_OUTPUT_DIR`, `MALAS_WEB_ALLOWED_HOSTS`,
  `MALAS_DEBUG_LOGS=1` (tulis log crew ke `logs/`; default mati agar tidak ada jejak).

### Database, antrean, dan key tersimpan (opsional)

Status job, progres, checkpoint, dan hasil `.docx` disimpan di database, bukan di disk, jadi riwayat selamat dari
restart/tidurnya host. Disk hanya dipakai sebagai folder kerja sementara. Detail variabel: `apps/api/.env.example`.

| Env | Fungsi |
|---|---|
| `DATABASE_URL` | Kosong = SQLite di `MALAS_OUTPUT_DIR` (lokal). Produksi: Neon Postgres, URL **pooled** (`postgres://…-pooler…`) |
| `DATABASE_URL_DIRECT` | URL **direct** (tanpa `-pooler`) khusus migrasi skema saat server naik (disarankan di Neon) |
| `MALAS_SECRET_KEY` | Rahasia ≥ 32 karakter. Tanpa ini, fitur **simpan API key** mati. Rotasi: `MALAS_SECRET_KEY_OLD` |

- Skema dikelola Alembic dan dimigrasi otomatis saat server naik (aman dijalankan dua instance sekaligus).
- Antrean = tabel `jobs`; pekerja mengambil job dengan claim atomik (`FOR UPDATE SKIP LOCKED` di Postgres) dan mengirim
  heartbeat. Job `running` yang heartbeat-nya basi (proses mati) ditandai **Terhenti** dan bisa dilanjutkan dari checkpoint.
- **API key tersimpan (opsional, atas pilihan pengguna)**: kirim `save_key: true` bersama `api_key`; key dienkripsi (Fernet)
  dan hanya didekripsi saat job jalan. Job berikutnya cukup `use_saved_key: true`. Dengan key tersimpan, job yang terputus
  **dilanjutkan otomatis** dari checkpoint sekali. `GET /api/keys` hanya menampilkan daftar penyedia (nilai key tidak pernah
  dikembalikan); `DELETE /api/keys/{provider}` menghapus. Tanpa memilih menyimpan, key tetap hanya di memori selama job.
- Tes: `uv run pytest` (SQLite). Untuk Postgres: `MALAS_TEST_DATABASE_URL=postgresql://… uv run pytest apps/api`
  (database itu **dikosongkan** tiap tes; pakai database khusus tes).

### Login (Clerk) dan kuota

Isi `CLERK_ISSUER` (atau `CLERK_JWKS_URL`) agar semua `/api/*` (kecuali `/api/config`, `/healthz`, halaman) mewajibkan
token sesi Clerk: `Authorization: Bearer <JWT>`. Server memverifikasi tanda tangan RS256 lewat JWKS (di-cache), `iss`, `exp`,
dan (opsional) `azp` dari `CLERK_AUTHORIZED_PARTIES`. Pemilik data = `sub` token, jadi riwayat, key tersimpan, dan kuota
terpisah per akun. Cookie `__session` hanya diterima untuk `GET` (tautan unduh); `POST`/`DELETE` wajib header (anti-CSRF).
Tanpa konfigurasi Clerk server tetap berjalan dalam mode anonim (cookie acak), cocok untuk lokal. Produksi: `MALAS_AUTH_REQUIRED=1`.

- `MALAS_DAILY_QUOTA=N`: maks N makalah nyata per akun per hari (reset tengah malam `MALAS_QUOTA_TZ`, default Asia/Jakarta).
  Mode uji dan "lanjutkan dari titik terakhir" tidak dihitung; job antre yang dibatalkan mengembalikan kuota. `GET /api/me`
  menampilkan sisa kuota dan waktu reset.

### Hosting publik tanpa login (mode BYOK)

> Deploy langkah demi langkah (Netlify + Hugging Face Space + Neon + Clerk + R2): lihat **[DEPLOY.md](DEPLOY.md)**.

```bash
MALAS_WEB_REQUIRE_KEY=1 MALAS_WEB_HOST=0.0.0.0 MALAS_WEB_ALLOWED_HOSTS="api.domain-anda.com" uv run malas-web
```

Dengan `MALAS_WEB_REQUIRE_KEY=1` setiap pengguna **wajib** membawa key sendiri (kecuali Mode uji);
key di `.env` server tidak pernah dipakai, jadi server tidak perlu menyimpan key apa pun. Jaminan:

| Hal | Perilaku |
|---|---|
| Penyimpanan key | Hanya di memori proses selama job berjalan, lalu dibuang (selesai, gagal, batal, hapus, shutdown). Tidak masuk `job.json`, cache, log, env, URL, maupun localStorage/sessionStorage browser. Kolom key dikosongkan setelah dikirim dan saat halaman ditinggalkan. |
| Kebocoran lewat error/log | Pesan error, log Python (termasuk litellm), dan traceback dibersihkan dari key; respons validasi tidak memantulkan input. Pesan ke pengguna berupa kalimat ramah, bukan JSON mentah penyedia. |
| Jejak di host | stdout/stderr dibungkam saat job; telemetry CrewAI dimatikan; log crew mati kecuali `MALAS_DEBUG_LOGS=1`; riwayat dan berkas dihapus otomatis setelah `MALAS_WEB_RETENTION_HOURS` (default 6). |
| Privasi antar pengguna | Tiap browser mendapat cookie sesi acak (HttpOnly, SameSite=Lax, Secure bila HTTPS); riwayat, status, dan unduhan hanya terlihat oleh pemiliknya (selain itu 404). |
| Penyalahgunaan | Maks. 1 job aktif per pengguna dan `MALAS_WEB_MAX_QUEUE` (default 5) job aktif total; body dibatasi 100 KB; Host asing ditolak. |
| Transport | Wajib HTTPS di internet (Netlify dan Hugging Face menyediakannya). UI menolak mengisi key bila halaman dibuka lewat HTTP non-localhost. |

Batas yang jujur: Python tidak bisa menghapus string dari memori secara pasti, sehingga key bisa
tersisa di RAM sampai di-garbage-collect; operator server dengan akses ke proses/RAM tetap bisa
melihatnya. Karena itu pengguna disarankan memakai key khusus dengan batas kredit kecil. Di free tier
yang tidur/restart, riwayat hilang (disk sementara); unduh segera setelah selesai.

### Baris perintah

1. Salin `packages/engine/src/malas/examples/contoh.yaml` dan isi judul, mata kuliah, penyusun, kampus.
2. Jalankan:

```bash
uv run kickoff --input makalah-saya.yaml
```

Opsi lain: `--template "path/template.docx"` dan `--output hasil.docx`.
Default hasil ada di `output/makalah_<waktu>.docx`. Uji tanpa biaya API: `MALAS_MOCK=1 uv run kickoff`.

## Cara kerja

1. `PlannerCrew`: outline + pencarian referensi (Arxiv, Semantic Scholar, CrossRef, DuckDuckGo).
2. **Full-text hemat token** (`malas/fulltext.py`, tanpa LLM): PDF open-access referensi (arXiv,
   Semantic Scholar/DOI open-access, atau halaman web) diunduh dan di-cache di `.cache/fulltext/`.
   Per sub-bab hanya beberapa potongan paling relevan (BM25 kata kunci, bukan embedding) yang
   dikirim ke Writer, dibatasi `MALAS_FULLTEXT_CHARS` dan tidak diulang antar sub-bab. Bila gagal
   diunduh, referensi tetap dipakai lewat abstraknya.
3. `WriteFormatCrew`: menulis tiap sub-bab dengan konteks referensi. Setiap referensi diberi
   bentuk sitasi siap-salin (mis. `(Smith & Lee, 2024)`) agar LLM tidak mengarang sitasi.
4. **Verifikasi sitasi** (`malas/citations.py`, tanpa LLM): sitasi in-text dicocokkan dengan
   daftar pustaka. Sub-bab dengan sitasi tidak sah diperbaiki satu kali oleh `citation_editor`;
   referensi yang tidak pernah dikutip dibuang dari daftar pustaka (aturan APA).
5. Kata Pengantar ditulis otomatis dari data makalah.
6. `DocxConverter` merender ke template Word (`docxtpl`/Jinja2). Template per kampus dapat
   diganti dengan `--template`.

### Ketahanan terhadap galat

- **Keluaran LLM tidak sesuai skema** (bukan JSON, dibungkus markdown, kunci berbeda): dirapikan secara
  lokal oleh `malas/tolerant.py`, tanpa panggilan LLM tambahan. Sebelumnya CrewAI meminta LLM "memformat
  ulang" sampai 3 kali (boros token) dan pada jalur tertentu crash dengan
  *"Agent must be provided if converter_cls is not specified"*.
- **Coba ulang**: tiap sub-bab diulang sekali bila gagal/kosong; galat yang pasti gagal lagi
  (key salah, saldo habis, model tidak ada) langsung berhenti.
- **Checkpoint & lanjutkan**: setelah outline selesai dan setiap sub-bab jadi, hasilnya disimpan di folder job.
  Bila job gagal/terhenti, tombol **Lanjutkan dari titik terakhir** membuat job baru yang memakai ulang outline,
  referensi, dan sub-bab yang sudah jadi (API key diminta lagi; key tidak pernah disimpan). Checkpoint dihapus
  saat job selesai dan ikut terhapus oleh masa simpan otomatis.

## Tes

```bash
uv run pytest
```

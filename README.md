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

```bash
uv run malas-web
```

Buka <http://127.0.0.1:8000>, isi formulir, lalu tekan **Buat makalah**. Halaman menampilkan
progres tiap tahap, ringkasan hasil (jumlah sub-bab, referensi, sitasi, token), tombol unduh
`.docx`, dan riwayat. Hasil tersimpan di `output/jobs/<id>/` sehingga selamat dari restart.

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

### Hosting publik tanpa login (mode BYOK)

```bash
MALAS_WEB_REQUIRE_KEY=1 MALAS_WEB_HOST=0.0.0.0 MALAS_WEB_ALLOWED_HOSTS="app-anda.onrender.com" uv run malas-web
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
| Transport | Wajib HTTPS di internet (Render dll. menyediakannya). UI menolak mengisi key bila halaman dibuka lewat HTTP non-localhost. |

Batas yang jujur: Python tidak bisa menghapus string dari memori secara pasti, sehingga key bisa
tersisa di RAM sampai di-garbage-collect; operator server dengan akses ke proses/RAM tetap bisa
melihatnya. Karena itu pengguna disarankan memakai key khusus dengan batas kredit kecil. Di free tier
yang tidur/restart, riwayat hilang (disk sementara); unduh segera setelah selesai.

### Baris perintah

1. Salin `input/contoh.yaml` dan isi judul, mata kuliah, penyusun, kampus.
2. Jalankan:

```bash
uv run kickoff --input input/makalah-saya.yaml
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

## Tes

```bash
uv run pytest
```

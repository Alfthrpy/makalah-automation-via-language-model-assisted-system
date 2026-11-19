# Deploy MALAS ke Render

Panduan ini men-deploy MALAS sebagai **web service publik tanpa login**. Setiap pengguna membawa
API key sendiri (OpenRouter atau Kenari), jadi server tidak menyimpan dan tidak perlu secret apa pun.

> Ringkasnya: **Blueprint → Apply → buka URL**. Seluruh konfigurasi sudah ada di `render.yaml`.

## 0. Yang sudah disiapkan di repo

| File | Fungsi |
|---|---|
| `apps/api/Dockerfile` | Image produksi (build context = root repo) (Python 3.13, dependensi dari `uv.lock` workspace, tanpa dependensi dev, jalan sebagai non-root) |
| `.dockerignore` | Menjaga image kecil dan tidak ikut membawa `.env`, `output/`, `tests/`, dsb. |
| `render.yaml` | Blueprint Render: layanan, region, health check, dan semua env var |
| `GET /healthz` | Health check ringan (tidak memeriksa Host, tidak memasang cookie) |

## 1. Prasyarat
- Akun [Render](https://render.com) yang sudah terhubung ke GitHub dan diberi akses ke repo ini.
- Branch `main` berisi `apps/api/Dockerfile` dan `render.yaml` (sudah, setelah merge).

## 2. Cara A: Blueprint (disarankan)
1. Dashboard Render → **New** → **Blueprint**.
2. Pilih repo `Alfthrpy/makalah-automation-via-language-model-assisted-system`, branch **main**.
3. Render membaca `render.yaml` dan menampilkan layanan `malas`. Klik **Apply**.
4. Tunggu build (build pertama beberapa menit karena mengunduh dependensi; berikutnya lebih cepat berkat cache lapisan).
5. Buka URL `https://<nama-layanan>.onrender.com` yang tertera di dashboard.

## 3. Cara B: manual (bila tidak memakai Blueprint)
**New → Web Service** → pilih repo → isi:

| Kolom | Nilai |
|---|---|
| Language / Runtime | **Docker** |
| Branch | `main` |
| Region | Singapore (terdekat dari Indonesia) |
| Instance Type | Free |
| Health Check Path | `/healthz` |
| Environment | tabel di bawah |

*(Nama menu bisa berubah antar versi dashboard Render.)*

## 4. Environment variable

| Key | Nilai | Keterangan |
|---|---|---|
| `MALAS_WEB_REQUIRE_KEY` | `1` | **Wajib.** Pengguna harus membawa API key sendiri; key server tidak pernah dipakai |
| `MALAS_WEB_RETENTION_HOURS` | `6` | Riwayat & berkas dihapus otomatis setelah N jam |
| `MALAS_WEB_MAX_QUEUE` | `5` | Batas total job aktif; 1 job aktif per pengguna |
| `MALAS_FULLTEXT` | `0` | Matikan pengunduhan PDF paper (hemat memori di free tier). Ubah ke `1` bila RAM lebih besar |
| `MALAS_WEB_HOST` | `0.0.0.0` | Agar bisa diakses dari luar kontainer |
| `MALAS_OUTPUT_DIR` | `/tmp/malas-output` | Folder hasil (sementara) |
| `PORT` | *(otomatis dari Render)* | Dibaca aplikasi; tidak perlu diisi |
| `RENDER_EXTERNAL_HOSTNAME` | *(otomatis dari Render)* | Otomatis diizinkan sebagai Host |
| `MALAS_WEB_ALLOWED_HOSTS` | *(opsional)* | Hanya bila memakai domain sendiri: `domain-anda.com` (koma bila lebih dari satu) |

**Jangan** menambahkan `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, dan sejenisnya di Render. Di mode ini
key itu tidak dipakai, dan menyimpannya hanya menambah risiko.

## 5. Verifikasi setelah deploy
1. `https://<url>/healthz` → `ok`.
2. `https://<url>/api/config` → memuat `"hosted": true` dan `"models": null`.
3. Di halaman, centang **Mode uji**, isi data, **Buat makalah** → harus selesai dan bisa diunduh (tanpa key, tanpa biaya).
4. Coba sungguhan: matikan Mode uji, pilih OpenRouter, tempel key khusus dengan kredit kecil, biarkan model kosong
   (memakai saran: riset `deepseek/deepseek-v3.2`, penulis `google/gemini-2.5-flash`).

## 6. Batasan free tier (baca sebelum dibagikan)
Sumber: [dokumentasi Render](https://render.com/docs/free).

| Batasan | Dampak pada MALAS |
|---|---|
| **Tidur setelah 15 menit tanpa trafik**; bangun lagi sampai sekitar 1 menit | Pengunjung pertama menunggu. Selama tab terbuka, polling progres menjaga layanan tetap hidup; bila tab ditutup di tengah job, layanan bisa tidur dan job hilang. |
| **Disk sementara** | Riwayat dan berkas hilang saat restart, deploy ulang, atau tidur. Unduh segera setelah selesai. |
| **Bisa di-restart kapan saja** | Job yang sedang berjalan bisa terputus (tampil sebagai "Terhenti"). Cukup ulangi. |
| **750 jam/bulan per workspace** | Cukup untuk satu layanan; waktu tidur tidak dihitung. |
| **RAM 512 MB** (angka dari sumber pihak ketiga; cek halaman Render) | Lihat bagian di bawah. |

### Memori: margin tipis
Hasil ukur saya di lingkungan yang meniru Render: server idle ± 70 MB; setelah job pertama (CrewAI dimuat) ± **340–365 MB**,
dan memori itu tetap terpakai setelahnya. Job dengan LLM sungguhan menambah sedikit lagi. Artinya muat di 512 MB,
tapi tidak longgar. Itulah sebabnya `MALAS_FULLTEXT=0` di Blueprint: mengurai PDF besar bisa melonjakkan RAM.
Bila log menunjukkan *out of memory* / layanan sering restart saat job berjalan:
1. Pastikan `MALAS_FULLTEXT=0`.
2. Pilih paket berbayar dengan RAM lebih besar (cek halaman harga Render), lalu baru pertimbangkan `MALAS_FULLTEXT=1`.

## 7. Keamanan (ringkas; rincian di README)
- HTTPS otomatis di `onrender.com`; cookie sesi bertanda `Secure`, `HttpOnly`, `SameSite=Lax`.
- API key pengguna hanya di memori selama job, tidak ditulis ke disk/log, dan dibersihkan dari pesan error.
- stdout dibungkam saat job, jadi log Render tidak memuat judul/isi makalah. Hanya log start-up server yang tampil.
- Riwayat antar pengguna terpisah (cookie acak); data dihapus otomatis setelah `MALAS_WEB_RETENTION_HOURS`.
- Tanpa login, siapa pun yang tahu URL bisa memakai layanan, tapi hanya dengan key mereka sendiri.
  Batas 1 job aktif per pengguna dan antrean total mencegah satu orang memenuhi layanan.
- Batas yang jujur: Python tidak bisa menghapus string dari RAM dengan pasti. Sarankan pengguna memakai key
  khusus dengan batas kredit kecil dan mencabutnya setelah selesai.

## 8. Domain sendiri
1. Render → layanan → **Settings → Custom Domains** → tambahkan domain dan ikuti instruksi DNS.
2. Tambahkan env `MALAS_WEB_ALLOWED_HOSTS=domain-anda.com`.
3. Health check tidak terpengaruh (`/healthz` selalu lolos).

## 9. Update dan rollback
- Push ke `main` → Render membangun dan men-deploy otomatis (perilaku bawaan layanan).
- Rollback: Render → layanan → **Deploys** → pilih deploy sebelumnya → **Rollback**.

## 10. Uji lokal dengan Docker (opsional)
```bash
docker build -f apps/api/Dockerfile -t malas .
docker run --rm -p 10000:10000 -e PORT=10000 malas
# buka http://localhost:10000
```
Host `localhost` diizinkan secara bawaan. Catatan: image ini belum pernah saya build (tidak ada Docker daemon di
lingkungan pengembangan). Yang sudah saya uji adalah langkah yang sama secara manual: instalasi bersih dari
`uv.lock` tanpa dependensi dev, server dijalankan dengan env mirip Render, health check dengan Host internal,
job mode uji sampai unduhan, dan pengukuran memori.

## 11. Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| Deploy gagal di tahap *health check* | Pastikan *Health Check Path* `/healthz`. Lihat log: server harus mencetak "MALAS web UI -> …" |
| Halaman menampilkan **Invalid host header** (400) | Memakai domain sendiri tanpa `MALAS_WEB_ALLOWED_HOSTS`. Tambahkan domain tersebut |
| Build gagal saat `uv sync` | Pastikan `uv.lock` ikut ter-commit dan sinkron dengan `pyproject.toml` (`uv lock`) |
| Layanan restart saat job berjalan | Kemungkinan kehabisan memori (bagian 6) |
| Job gagal di tengah jalan | Buka job tersebut → **Lanjutkan dari titik terakhir** (butuh API key lagi). Outline dan sub-bab yang sudah jadi dipakai ulang. Di free tier, checkpoint ikut hilang bila layanan restart/tidur karena disk sementara |
| Job selalu "Antre" | Ada job lain yang sedang berjalan; antrean satu pekerja. Tunggu atau coba lagi |
| "Anda masih punya makalah yang sedang diproses" (429) | Aturan 1 job aktif per pengguna. Tunggu selesai |
| "Antrean penuh" (429) | `MALAS_WEB_MAX_QUEUE` tercapai; coba lagi sebentar lagi |
| "API key ditolak penyedia" | Key salah/dicabut/tanpa saldo, atau model tidak tersedia untuk key tersebut |
| Riwayat/berkas hilang | Normal di free tier (disk sementara) dan retensi otomatis. Unduh segera |
| Pembukaan pertama lambat sekali | Layanan sedang bangun dari tidur (sampai ± 1 menit) |

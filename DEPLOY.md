# Deploy MALAS (gratis): Netlify + Hugging Face Space + Neon + Clerk (+ R2)

```
Browser ──> Netlify (apps/web, statis)
              │  /api/*  (proxy, satu origin, tanpa CORS)
              ▼
         Hugging Face Space (Docker, apps/api, port 7860)
              │                │
              ▼                ▼
        Neon Postgres     Cloudflare R2 (opsional; tanpa R2 = .docx disimpan di Neon)
   Login: Clerk (JWT diverifikasi backend lewat JWKS)
```

> **Status uji (jujur):** image Docker, bundel Space, dan seluruh tes berjalan di sandbox pengembangan. Yang BELUM pernah dicoba
> dengan layanan asli (tidak ada akun/kredensial di sandbox): Neon (latensi cold-start, PgBouncer), Clerk (format `iss`/`azp`
> instance nyata, CSP), R2 (hanya diuji dengan klien S3 palsu), Netlify, dan HF Space. Ikuti bagian **Verifikasi** di tiap langkah.
> Batas free tier semua layanan berubah-ubah: cek halaman harga masing-masing sebelum mengandalkannya.

## 0. Yang sudah ada di repo

| Berkas | Fungsi |
|---|---|
| `apps/api/Dockerfile` | Image backend (Python 3.13, dependensi dari `uv.lock`, non-root uid 1000, port 7860). Build context = root repo |
| `deploy/hf-space/` | `README.md` (front-matter HF) + `bundle.sh` yang menyusun isi Space dari repo ini |
| `.github/workflows/ci.yml` | CI: pytest (SQLite & Postgres 16), typecheck + tes + build web, build image + smoke test |
| `.github/workflows/deploy-hf.yml` | Push bundel ke Space (butuh secret `HF_TOKEN` + variable `HF_SPACE`) |
| `netlify.toml` | Build web, proxy `/api/*` ke Space, fallback SPA, header keamanan/CSP |
| `apps/api/.env.example` | Semua env backend |
| `GET /healthz` | Health check ringan (tanpa cookie, tanpa pemeriksaan Host) |

## 1. Neon (database)
1. Buat project di [neon.tech](https://neon.tech) (region terdekat, mis. Singapore).
2. Salin **dua** connection string: **pooled** (host berakhiran `-pooler`) → `DATABASE_URL`; **direct** → `DATABASE_URL_DIRECT` (dipakai migrasi Alembic saat server naik).
3. Skema dibuat otomatis oleh server saat start (`malas_api.db.migrate()`).

## 2. Clerk (login)
1. Buat aplikasi di [clerk.com](https://clerk.com) (instance development dulu).
2. Dari **API keys**: **Publishable key** (→ web) dan **Frontend API URL** (→ `CLERK_ISSUER`, mis. `https://xxxx.clerk.accounts.dev`).
3. `CLERK_AUTHORIZED_PARTIES` = origin web yang sah, mis. `https://malas.netlify.app` (klaim `azp`).

## 3. Hugging Face Space (backend)
1. Buat **Space** baru: SDK **Docker**, visibilitas **Public** (Netlify perlu menjangkaunya; API dilindungi login Clerk). Catat nama `pemilik/nama-space`.
2. **Settings > Variables and secrets** di Space:

| Nama | Jenis | Nilai |
|---|---|---|
| `DATABASE_URL` | Secret | Neon pooled |
| `DATABASE_URL_DIRECT` | Secret | Neon direct |
| `MALAS_SECRET_KEY` | Secret | acak ≥ 32 karakter (`python -c "import secrets;print(secrets.token_urlsafe(48))"`). Aktifkan hanya bila fitur "simpan API key" dipakai; **jangan diganti sembarangan** (key tersimpan jadi tak terbaca; rotasi lewat `MALAS_SECRET_KEY_OLD`) |
| `CLERK_ISSUER` | Variable | Frontend API URL Clerk |
| `CLERK_AUTHORIZED_PARTIES` | Variable | `https://<situs-netlify>` |
| `MALAS_AUTH_REQUIRED` | Variable | `1` (server menolak start tanpa Clerk) |
| `MALAS_DAILY_QUOTA` | Variable | mis. `3` |
| `R2_*` | Secret | opsional, lihat bagian 6 |

   Bawaan dari Dockerfile (tidak perlu diisi): `MALAS_WEB_REQUIRE_KEY=1`, `MALAS_FULLTEXT=1`, `PORT=7860`. `MALAS_WEB_RETENTION_HOURS` (6) dan `MALAS_WEB_MAX_QUEUE` (5) bisa ditimpa.
   `SPACE_HOST` diisi otomatis oleh HF dan sudah diizinkan sebagai Host.
3. **Mengisi kode Space**, pilih salah satu:
   - **Otomatis (disarankan):** di repo GitHub: *Settings > Secrets and variables > Actions*: secret `HF_TOKEN` (token HF izin *write*), variable `HF_SPACE` (`pemilik/nama-space`). Jalankan workflow **Deploy backend ke Hugging Face Space** (atau push ke `main`).
   - **Manual:** `deploy/hf-space/bundle.sh /tmp/space && cd /tmp/space && git init -b main && git add -A && git commit -m deploy && git push --force https://huggingface.co/spaces/<pemilik>/<nama> main`.
4. **Verifikasi:** `https://<pemilik>-<nama>.hf.space/healthz` → `ok`; `/api/config` → `"hosted": true`, `"auth": {"mode": "clerk", ...}`; `/api/jobs` tanpa token → 401.

Catatan HF Space: Space gratis **tidur** setelah tidak aktif (bangun ± puluhan detik), disk **ephemeral** (itulah mengapa riwayat dan hasil ada di Neon/R2), dan job yang sedang berjalan terputus bila Space restart: statusnya jadi "Terhenti" dan bisa dilanjutkan dari checkpoint (otomatis bila pengguna memilih menyimpan key).

## 4. Netlify (web)
1. Edit `netlify.toml`: ganti `GANTI-SPACE.hf.space` dengan host Space (bentuk `<pemilik>-<nama>.hf.space`), commit.
2. Netlify: **Add new site > Import from Git**, pilih repo/branch. Build command dan folder publish sudah di `netlify.toml`.
3. **Site configuration > Environment variables**: `VITE_CLERK_PUBLISHABLE_KEY` = publishable key Clerk. (`VITE_AUTH_MODE=clerk` sudah di `netlify.toml`.) **Jangan** menaruh secret di variabel `VITE_*`: semuanya terbaca publik.
4. Setelah URL situs diketahui, isi `CLERK_AUTHORIZED_PARTIES` di Space dengan URL itu, dan tambahkan domain situs di dashboard Clerk bila diminta.
5. **Verifikasi:** landing tampil → *Masuk* → Clerk → dasbor → buat makalah **Mode uji** → selesai → unduh `.docx`. Buka DevTools > Console: tidak boleh ada pelanggaran CSP. Bila ada (mis. Clerk memerlukan host tambahan), perbarui header `Content-Security-Policy` di `netlify.toml`; untuk instance produksi Clerk tambahkan domain Frontend API kamu (mis. `https://clerk.domainmu.com`) ke `script-src` dan `connect-src`.

Hal yang perlu dicek karena belum teruji dengan layanan asli: (a) Netlify meneruskan header `Authorization` pada proxy `/api/*` (seharusnya ya); (b) header `Host` yang sampai ke Space diterima (Space mengizinkan `SPACE_HOST`; bila ada 400 "Invalid host header", isi `MALAS_WEB_ALLOWED_HOSTS` dengan host yang tertera di pesan/log).

## 5. Pengujian lokal
```bash
docker build -f apps/api/Dockerfile -t malas .
docker run --rm -p 7860:7860 malas          # http://localhost:7860/healthz
```
Backend + web tanpa Docker/Clerk: lihat README (`uv run malas-web` dan `pnpm dev:web`).

## 6. File hasil di Cloudflare R2 (opsional)
Tanpa R2, `.docx` disimpan sebagai `bytea` di Neon (cukup untuk MVP; retensi otomatis membersihkannya). Untuk memindahkannya:
1. Cloudflare > R2: buat bucket **privat** (jangan aktifkan akses publik; unduhan selalu lewat API yang memeriksa pemilik).
2. Buat **API token R2** dengan izin *Object Read & Write* terbatas pada bucket itu.
3. Isi secret Space: `R2_ENDPOINT_URL` (`https://<account_id>.r2.cloudflarestorage.com`), `R2_BUCKET`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`. Keempatnya harus terisi (terisi sebagian = server menolak start dengan pesan jelas).
4. Job lama yang `.docx`-nya ada di Neon tidak otomatis pindah; setelah masa retensi, riwayat itu hilang sendiri.

## 7. Keamanan (ringkas; rincian di README)
- API key pengguna hanya di memori selama job (kecuali pengguna memilih menyimpannya: terenkripsi Fernet di DB, tidak pernah dikembalikan lewat API). Tidak ditulis ke disk/log; pesan error dibersihkan.
- Login Clerk wajib di semua `/api/*` (kecuali `/api/config`); pemilik data = `sub` JWT; kuota harian per akun.
- stdout dibungkam saat job, jadi log Space tidak memuat judul/isi makalah.
- Batas yang jujur: Python tidak bisa menghapus string dari RAM dengan pasti; sarankan pengguna memakai key khusus dengan batas kredit kecil.

## 8. Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| Space *Build error* | Lihat tab Logs. Pastikan `uv.lock` sinkron (`uv lock`) dan ikut ter-commit |
| Space start lalu langsung berhenti | Log: `MALAS_AUTH_REQUIRED=1 tetapi CLERK_ISSUER...` → isi `CLERK_ISSUER`; atau "Konfigurasi R2 tidak lengkap" → lengkapi keempat `R2_*` |
| `/api/*` 401 padahal sudah login | `CLERK_ISSUER`/`CLERK_AUTHORIZED_PARTIES` tidak cocok dengan instance/origin. Cek `iss` dan `azp` di JWT (jwt.io; jangan tempel token ke situs yang tidak kamu percaya) |
| 400 "Invalid host header" | Host proxy belum diizinkan: set `MALAS_WEB_ALLOWED_HOSTS` |
| Halaman Clerk kosong / error CSP di Console | Perbarui `Content-Security-Policy` di `netlify.toml` (bagian 4, langkah 5) |
| Pembukaan pertama lambat | Space gratis sedang bangun dari tidur |
| Job "Terhenti" | Space restart saat job berjalan. Buka job → **Lanjutkan** (outline dan sub-bab yang sudah jadi dipakai ulang) |
| "Anda masih punya makalah yang sedang diproses" (429) | Aturan 1 job aktif per pengguna |
| "Kuota harian habis" (429) | `MALAS_DAILY_QUOTA` tercapai; reset tengah malam `MALAS_QUOTA_TZ` |
| "API key ditolak penyedia" | Key salah/dicabut/tanpa saldo, atau model tidak tersedia untuk key itu |

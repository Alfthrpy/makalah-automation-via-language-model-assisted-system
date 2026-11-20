# HANDOFF: MALAS (penulis makalah otomatis) sebagai SaaS gratis

> Dokumen aktif untuk sesi berikutnya. Terakhir diperbarui **2026-11-20**. Baca bagian 1-4 dulu (±5 menit), sisanya sebagai rujukan.
> Detail lengkap per fase dan riwayat revisi desain (v1-v5) ada di `docs/archive/HANDOFF-lengkap-2026-11-20.md`.
> Bahasa percakapan dan UI: **Indonesia**, nada santai ("kamu"), tapi lugas untuk privasi/error/hapus/kuota.

## 1. Ringkasan satu paragraf
MALAS = **M**akalah **A**utomation via **L**anguage-model **A**ssisted **S**ystem. Pengguna mengetik judul, menempel API key sendiri (BYOK, OpenRouter/Kenari) atau memakai **Mode uji** (tanpa LLM, teks contoh), lalu pipeline crewAI menyusun DRAF makalah `.docx` dengan template kampus. Monorepo: backend FastAPI + antrean di Postgres (`apps/api`), engine crewAI (`packages/engine`), web React (`apps/web`). **Sudah live**: web di Netlify, backend di Hugging Face Space, database di Neon, login Clerk. Semua kode, tes, CI, deploy, halaman hukum, logo kustom, dan video promo sudah selesai dan ter-merge. Yang belum: **bukti ujung-ke-ujung dengan akun/key nyata** (lihat bagian 3).

## 2. Yang live sekarang
| Komponen | Detail |
|---|---|
| Web | https://malas-app.netlify.app (Netlify, situs `malas-app`, id `f4f7ee2f-f459-4ce8-b20b-910fbb04b45b`; **tidak git-linked**, di-deploy lewat API; deploy terakhir `6affeb22`) |
| Backend | HF Space `PetaniHandal/stegano-f5-dmcss-api` → `https://petanihandal-stegano-f5-dmcss-api.hf.space` (Docker, RUNNING; commit `d76661cb`; **titik kembali** `29b5f2d4`). Nama Space salah kaprah: bekas proyek steganografi yang DITIMPA atas persetujuan pemilik (riwayat lama tetap di History Space) |
| Database | Neon project `malas` (`still-lab-16179546`), branch `production` (`br-snowy-bread-bedoe94t`), `aws-us-east-2`, Postgres 18, role `neondb_owner`, DB `neondb`. Migrasi 0001-0003 terpasang (tabel `user_logos` terverifikasi lewat API Neon) |
| Login | Clerk instance **dev** `moral-camel-3719` (`https://moral-camel-3719.clerk.accounts.dev`). Publishable key (publik) `pk_test_bW9yYWwtY2FtZWwtMzcxOS5jbGVyay5hY2NvdW50cy5kZXYk` |
| Repo | `Alfthrpy/makalah-automation-via-language-model-assisted-system`, branch kerja `claude/jolly-maxwell-xdh9bs` (disinkronkan ke `main` tiap selesai merge: `git fetch origin main && git checkout -B claude/jolly-maxwell-xdh9bs origin/main`). PR #1-#4 sudah ter-merge |
| Tes | pytest 163 lulus + 1 skip (Postgres: `apps/api` 125 lulus), web 41, e2e Playwright (`apps/web/e2e/{flow,states,logo}.cjs`), CI GitHub Actions 4 job hijau |

**Konfigurasi Space** (Settings → Variables and secrets). Variabel: `CLERK_ISSUER`, `MALAS_AUTH_REQUIRED=1`, `MALAS_DAILY_QUOTA=3`. Secret: `DATABASE_URL` (pooled), `DATABASE_URL_DIRECT`. Bawaan Dockerfile: `MALAS_WEB_REQUIRE_KEY=1`, `MALAS_FULLTEXT=1`, `PORT=7860`. **Belum diisi (disengaja)**: `CLERK_AUTHORIZED_PARTIES` (isi `https://malas-app.netlify.app` SETELAH login terbukti jalan; bila semua `/api/*` jadi 401, hapus), `MALAS_SECRET_KEY` (fitur simpan-API-key mati), `MALAS_WEB_RETENTION_HOURS` (default 48 jam), `R2_*` (file `.docx` disimpan sebagai bytea di Neon).

**Kredensial**: tidak ada yang ada di repo. Di sandbox Claude, token HF, Neon, dan Netlify tersimpan sebagai *network secret* pada environment sesi `makalah-malas` (`env_01BNncQLupktjSKUqfqiync5`); proxy menyuntikkannya, jadi skrip memakai placeholder `proxy-injected` (mis. `HF_TOKEN=proxy-injected`). Sesi di environment lain tidak punya akses itu: minta lagi lewat `request_credential` (formulir aman, tempel token di formulir, BUKAN di chat). Host yang diizinkan di environment itu: `moral-camel-3719.clerk.accounts.dev`, `huggingface.co`, `console.neon.tech`, `api.netlify.com`.

## 2b. Pencarian referensi baru (refsearch), status 2026-11-20
Pengganti agen LLM bertool untuk tahap "cari referensi": paket `packages/engine/src/malas/refsearch/` (OpenAlex + Crossref, +Europe PMC/arXiv/DOAJ
sesuai bidang, fallback Wikipedia/Open Library). Dokumen lengkap: **`docs/refsearch.md`**. Aktif lewat `MALAS_REFSEARCH=1`; jalur lama (agen) tetap ada dan jadi default bila variabel kosong.
- **Live di Space** sejak commit Space `b02dad45` (kode dari branch kerja; BELUM di-merge ke `main`, tidak ada PR). Variabel Space: `MALAS_REFSEARCH=1`; secret: `MALAS_OPENALEX_API_KEY` (diisi pemilik). `MALAS_CONTACT_EMAIL` belum diisi (opsional; Crossref lebih lambat tanpanya, Unpaywall mati).
- **Titik kembali:** Space ke `d76661cb` / `29b5f2d4` (push ulang bundel dari commit repo `8ff5161`), ATAU cukup hapus variabel `MALAS_REFSEARCH` di Space (tanpa deploy). Tag git lokal `pre-refsearch-2026-11-20` (push tag gagal; titik kembali yang berlaku `8ff5161`).
- **Terbukti nyata** (workflow CI sementara `.github/workflows/refsearch-probe.yml`, jalan otomatis saat file itu diubah; boleh dihapus): 8 topik lintas bidang, 32/32 sub-bab >=2 referensi, abstrak 100%, PDF-OA 97%, full-text 78%, tanpa key & tanpa LLM. Bug nyata yang ditemukan lewat uji ini sudah diperbaiki (Crossref `select=language` -> 400; file `Cover.pdf` repositori).
- **BELUM terbukti:** rencana query dari LLM (`llm_plan`, EN+ID+bidang) di produksi; perbandingan token/biaya vs jalur lama (butuh key LLM); relevansi sempurna (topik Majapahit masih menyertakan 1 artikel Sriwijaya; topik teknis tanpa query Inggris hanya dapat jurnal Indonesia); Europe PMC lambat (~29 dtk, timeout baca 40 dtk).
- **Keamanan izin:** deploy ke Space butuh persetujuan eksplisit pemilik (menimpa isi Space). Sesi ini mendapat kredensial `api.openalex.org` di environment lewat kartu `request_credential`.
- **Ide lanjutan** (belum dikerjakan): rerank LLM berbasis ID, pencarian web dengan allowlist domain, regulasi (JDIH BPK), CORE, embedding lokal.

## 3. Yang BELUM terbukti (jujur)
1. **Login/sign-up sampai tuntas di browser nyata.** `<SignIn/>`/`<SignUp/>` render dengan 0 pelanggaran CSP terhadap instance Clerk asli, dan JWKS + `Authenticator` terbukti. Tapi sign-up di browser headless sandbox kena `403 "For your security..."` (dugaan: bot protection Clerk karena `cdn.protect.clerk.com` diblokir proxy sandbox). Belum ada yang mencoba di HP. `getToken`, klaim `azp` pada token nyata, `openUserProfile` belum teruji.
2. **Satu makalah sungguhan dengan API key.** Seluruh pengujian memakai Mode uji. Kualitas isi, validitas sitasi, waktu 10-30 menit, dan biaya token nyata belum pernah diukur. Klaim di landing/video bergantung pada ini.
3. **`/api/*` lewat proxy Netlify ke Space** (header `Authorization`/`Host`) dan tampilan situs live: sandbox tidak bisa membuka `*.netlify.app` maupun `*.hf.space`.
4. R2 (hanya klien S3 palsu), workflow `deploy-hf.yml` (belum pernah jalan; deploy dilakukan lewat `deploy/hf-space/push.py`), panggilan lanjutan skrip Clerk Protect (bisa memicu pelanggaran `connect-src`; tambahkan host dari pesannya ke CSP di `netlify.toml`).
5. Audio video promo belum pernah didengar manusia (hanya diukur).

## 4. Prioritas berikutnya
**A. Butuh pemilik (HP/akun)**: tes alur lengkap di HP (daftar → masuk → Mode uji → unduh `.docx`; coba unggah logo; `/privasi` harus bilang 48 jam); satu makalah sungguhan dengan key khusus berkredit kecil (catat waktu, token, biaya); lalu isi `CLERK_AUTHORIZED_PARTIES`; setelan Clerk (verifikasi email, URL hukum di bagian Legal); cabut token yang sempat bocor (token HF lama yang tertempel di chat) dan hapus token HF/Neon/Netlify di environment `makalah-malas` bila tak dipakai; pasang "link di bio" sebelum unggah video; **tinjau Ketentuan/Privasi** (draf dari perilaku sistem, bukan nasihat hukum; pengelola ditulis "perorangan", kontak = GitHub issues).
**B. Keputusan pemilik yang menggantung**: (1) **template di repo (`packages/engine/src/malas/templates/*.docx`, `word/media/image1.png`) memuat logo institusi tertentu**; layanan web sudah memakai penanda netral/logo pengguna, tapi repo publik masih membawanya: ganti permanen dengan gambar netral? (2) rename Space (mis. `PetaniHandal/malas-api`; dampak: host berubah → edit `netlify.toml`, deploy ulang web, `HF_SPACE` di GitHub); (3) domain sendiri (ubah `og:*` di `apps/web/index.html`, `robots.txt`, `sitemap.xml`, `CLERK_AUTHORIZED_PARTIES`, Clerk); (4) logo per akun (sekarang) atau per makalah?
**C. Ide produk (diurutkan gue)**: set uji kualitas (±10 judul lintas jurusan dijalankan berkala dengan key sungguhan, nilai sitasi/struktur/panjang); edit/setujui outline sebelum penulisan; estimasi biaya sebelum kirim; notifikasi selesai (email Resend/push); gaya sitasi (APA/IEEE) dan opsi bahasa Inggris; laporan verifikasi sitasi di hasil; B6 label template ramah (`GET /api/config.templates` jadi objek); PWA; tombol umpan balik; pemantauan job gagal (Sentry perlu DSN + penyaringan agar body/key tak terkirim; bila analitik ditambah, UPDATE Kebijakan Privasi yang kini menyatakan tanpa pelacak pihak ketiga); tes komponen MSW; code-splitting.
**D. Fase 6 opsional**: admin, pembayaran, i18n.

Daftar peluncuran terperinci: `docs/LAUNCH-CHECKLIST.md`. Panduan setup layanan + troubleshooting: `DEPLOY.md`.

## 5. Keputusan arsitektur (sudah disepakati)
| # | Topik | Keputusan |
|---|---|---|
| 1 | Auth | **Clerk** (JWT RS256 diverifikasi backend lewat JWKS; `iss`, `exp`, `sub` wajib; `azp` bila `CLERK_AUTHORIZED_PARTIES`). Tanpa Clerk, backend jalan mode anonim (cookie acak) untuk lokal/tes |
| 2 | Frontend | **Vite + React + TS + react-router + TanStack Query + zod**, Tailwind v4 (utilitas berprefiks `tw:`, tanpa preflight), CSS prototipe di `src/styles/*`; deploy Netlify; `/api/*` di-proxy ke backend (satu origin, tanpa CORS) |
| 3 | API key (BYOK) | Default HANYA di memori selama job; opsional disimpan terenkripsi (Fernet) di DB bila `MALAS_SECRET_KEY` diisi dan pengguna memilihnya; tidak pernah dikembalikan lewat API |
| 4 | Backend host | **Hugging Face Space (Docker, port 7860)**; disk ephemeral, bisa tidur |
| 5 | Database | **Neon Postgres** (pooled untuk app, direct untuk migrasi Alembic) |
| 6 | File hasil | Antarmuka `Storage`: `DbStorage` (bytea, kini dipakai) atau `S3Storage` (R2, aktif bila keempat `R2_*` terisi) |
| 7 | Antrean | Tabel Postgres + `FOR UPDATE SKIP LOCKED`, 1 worker/proses, heartbeat, pemulihan job basi, auto-resume bila key tersimpan |
| 8 | Retensi | Riwayat/berkas dihapus 48 jam setelah selesai (mode hosting); tampil di `/api/config`; harus sama dengan teks hukum (ada tes) |
| 9 | Kuota | `MALAS_DAILY_QUOTA` makalah nyata/akun/hari (Mode uji dan lanjutan tidak dihitung); tabel `usage` persisten |
| 10 | Logo sampul | Satu logo/akun (`user_logos`), dinormalkan Pillow jadi PNG persegi; tanpa logo = penanda netral "LOGO" (hanya layanan web) |

## 6. Struktur repo
```
pyproject.toml, uv.lock      # uv workspace (apps/api, packages/engine) + dev group
package.json, pnpm-*.yaml    # pnpm workspace (apps/web, packages/*)
apps/api/                    # paket `malas_api`
  src/malas_api/app.py       # routes, middleware (Clerk/anonim, header keamanan), retention_from_env
  jobs.py repo.py db.py      # JobManager+worker; SATU-SATUNYA tempat SQL; model SQLAlchemy
  schemas.py                 # model respons Pydantic (sumber kontrak OpenAPI + penyaring keluaran)
  export_openapi.py          # `uv run malas-openapi` -> packages/api-types/openapi.json
  auth.py crypto.py vault.py storage.py
  migrations/versions/       # 0001 skema awal, 0002 usage, 0003 user_logos
  tests/                     # test_web, test_byok, test_resume, test_db, test_auth, test_openapi (drift), test_storage, test_logo
  Dockerfile                 # build context = ROOT repo
packages/engine/             # paket `malas`: crews, docx_converter, logo.py, citations, fulltext, providers, CLI `kickoff`
packages/api-types/          # @malas/api-types: openapi.json + schema.d.ts (hasil generate; JANGAN edit tangan)
apps/web/                    # React; src/{features,components,lib,copy,styles}; copy UI di src/copy/id.ts
  features/legal/content.ts  # teks Ketentuan/Privasi (dikunci tes terhadap fakta sistem)
  e2e/ og/ public/           # skrip Playwright, sumber gambar OG, aset publik (favicon, og.png, robots, sitemap)
deploy/{netlify,hf-space}/   # deploy.py, push.py, bundle.sh + README Space
.github/workflows/           # ci.yml (4 job), deploy-hf.yml (butuh HF_TOKEN + var HF_SPACE)
netlify.toml                 # build, proxy /api/* ke Space, SPA fallback, header + CSP (Clerk)
docs/                        # LAUNCH-CHECKLIST.md, design/ (prototipe + HANDOFF-frontend), archive/
marketing/video/             # video promo; v4 = final (lihat bagian 8)
```

## 7. Perintah penting
```bash
uv sync --all-packages && pnpm install            # setup
uv run pytest -q                                  # semua tes Python (SQLite); lalu:
MALAS_TEST_DATABASE_URL=postgresql://postgres@localhost:54329/malas_test uv run pytest apps/api   # Postgres (lihat catatan)
pnpm --filter web {typecheck,test,build}          # web
uv run malas-web  &  pnpm --filter web dev        # lokal: API :8000, web :5173 (VITE_AUTH_MODE=dev, tanpa Clerk)
NODE_PATH=$(npm root -g) node apps/web/e2e/{flow,states,logo}.cjs   # e2e (server di atas harus hidup)
MALAS_MOCK=1 uv run kickoff --output x.docx [--logo logo.png]       # pipeline mode uji via CLI
# Ubah model respons API -> regenerasi kontrak (tes drift gagal bila lupa):
uv run malas-openapi && (cd packages/api-types && pnpm exec openapi-typescript openapi.json -o schema.d.ts)
# Deploy web (build dengan key Clerk publik):
VITE_AUTH_MODE=clerk VITE_CLERK_PUBLISHABLE_KEY=pk_test_... pnpm --filter web build
NETLIFY_AUTH_TOKEN=... python3 deploy/netlify/deploy.py --site f4f7ee2f-f459-4ce8-b20b-910fbb04b45b
# Deploy backend (SATU commit, riwayat Space aman):
HF_TOKEN=... uv run --no-project --with huggingface_hub python deploy/hf-space/push.py PetaniHandal/stegano-f5-dmcss-api
```
Postgres lokal di sandbox: `/usr/lib/postgresql/16/bin`, jalankan sebagai user `postgres` dengan data dir milik `postgres` (mis. `/var/tmp/pgdata-malas`, port 54329, `initdb -A trust`, `createdb malas_test`); tidak aktif lagi di sesi baru; database DIKOSONGKAN tiap tes. Docker daemon bisa dijalankan manual (`dockerd &`); build di sandbox butuh CA proxy sandbox (`--build-context ca=/root/.ccr` + salinan Dockerfile yang menambah CA); di CI/HF tidak perlu.

## 8. Video marketing
`marketing/video/v4/` = final (30,7 dtk, 9:16, 1080×1920, musik+SFX orisinal sintesis, -14 LUFS, true peak ≤ -1 dBTP; CTA: "Coba gratis", "Mode uji gratis, tanpa API key", "Link di bio", `malas-app.netlify.app`). v1-v3 = versi lama (v1 tanpa aset asli, v2 tanpa audio, v3 sebelum CTA baru). Dibuat dari HTML deterministik (`window.renderFrame`) → Playwright → ffmpeg; `v4/build.sh` merender video + sintesis audio + mux + verifikasi; `soundtrack.wav` dan `verify/stems` tidak di-commit (dibuat ulang). Aset memakai tangkapan layar asli UI (Mode uji) dan halaman `.docx` asli dengan data generik dan placeholder logo. Pasang link di bio sebelum unggah; audio belum didengar manusia.

## 9. Aturan yang TIDAK boleh dilanggar
- **Keamanan**: API key tidak ke disk/log/error/localStorage/URL; stdout dibungkam saat job; telemetry CrewAI mati di mode web; respons validasi tidak memantulkan input; unggahan (logo) divalidasi ketat dan dikodekan ulang; secret hanya lewat env/formulir aman, tidak pernah di repo atau chat.
- **Kejujuran produk/marketing**: hasil = DRAF yang pengguna baca dan cek; sitasi dicocokkan dengan sumber asli tapi bisa keliru; aturan kampus/dosen soal AI = tanggung jawab pengguna. **DILARANG**: klaim lolos deteksi AI/plagiarisme, jaminan nilai, saran menyembunyikan penggunaan AI, testimoni/angka palsu, urgensi palsu. Layar yang berisi data Mode uji diberi label "Tampilan contoh".
- **Teks hukum mengikuti perilaku sistem**: ubah retensi/data/analitik → ubah `features/legal/content.ts` + `LEGAL_UPDATED` (tes akan mengingatkan).
- **Git**: jangan buat PR atau merge kecuali diminta pemilik; push hanya ke `claude/jolly-maxwell-xdh9bs`; hook penutup sesi akan meminta commit+push berkas yang belum terlacak (jangan commit hasil sementara/stems besar).

## 10. Jebakan yang sudah pernah memakan waktu
- **Sandbox**: hanya host yang di-allowlist yang terjangkau; `*.netlify.app` dan `*.hf.space` TIDAK. Playwright ke `localhost` harus pakai `proxy.bypass`. Python yang memuat paket pihak ketiga dari folder skrip: jalankan dengan `python -I` (folder scratchpad pernah memuat `copy.py` yang membayangi stdlib).
- **`openapi-typescript` butuh TypeScript 5** (workspace memakai TS 7 tanpa `ts.factory`): TS 5 di-pin hanya di `packages/api-types`. Skema `JobRequest` hasil generate menandai field ber-default sebagai wajib, jadi tipe INPUT form di `apps/web/src/lib/types.ts` tetap ditulis tangan; hanya tipe respons yang digenerasi.
- **Pool koneksi**: `JobManager.shutdown()` harus `db.dispose()` (dulu bocor → "too many clients" di Postgres CI).
- **Deploy Netlify lewat API tidak membaca `netlify.toml`**: `deploy.py` menurunkan `_redirects`/`_headers` darinya. Host proxy ke Space ditulis di `netlify.toml` (Netlify tak mengizinkan env di redirect).
- **CSP Clerk**: perlu `font-src data:` dan `script-src https://cdn.protect.clerk.com`; `@clerk/clerk-react` v5 ditolak Clerk saat sign-up → pakai `@clerk/react` v6 + `@clerk/localizations` (idID).
- **`ruff` hanya pada berkas baru** (daftar eksplisit di `ci.yml`; tambahkan berkas baru ke sana); kode lama belum dirapikan.
- Job CrewAI tidak bisa dihentikan di tengah jalan (hanya yang mengantre bisa dibatalkan); `malas-web` tidak mem-parse argumen CLI; HF Space gratis bisa tidur dan restart (job terputus jadi "Terhenti", bisa dilanjutkan dari checkpoint).
- Pemeriksa izin otomatis pernah menolak `merge_pull_request` saat PR memuat perubahan di luar yang diminta; berhasil setelah permintaan merge eksplisit dari pemilik.
- Batas free tier (Neon, HF, Netlify, Clerk) berubah-ubah; cek ulang sebelum promosi besar.

## 11. Riwayat fase (ringkas)
Fase 1 restrukturisasi monorepo → Fase 2 backend + Neon (antrean Postgres, checkpoint, key terenkripsi) → Fase 3 auth Clerk + kuota → Fase 4 frontend React (landing, dasbor, buat, job, pengaturan; B1-B5: ringkasan riwayat, posisi antrean, durasi tahap, response model + OpenAPI, hapus UI statis) → Fase 5 deploy + CI (Dockerfile HF, netlify.toml, GitHub Actions, S3Storage) → peluncuran: Clerk v6, Ketentuan/Privasi, pratinjau dibagikan, skrip deploy, checklist, video v1-v4, logo kustom, retensi 48 jam. Rincian setiap fase: arsip di atas.

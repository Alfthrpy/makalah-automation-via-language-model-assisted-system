# HANDOFF: MALAS → monorepo SaaS (free tier)

> Dokumen ini diperbarui setiap selesai satu fase atau saat sesi ditutup. Mulai sesi baru dengan membacanya
> dulu, lalu lanjut ke bagian "Langkah berikutnya". Branch kerja: `claude/jolly-maxwell-xdh9bs`.

## Tujuan
Mengubah MALAS (penulis makalah otomatis berbasis crewAI) menjadi monorepo frontend + backend ala SaaS,
memakai layanan gratis. Bahasa percakapan dan UI: Indonesia.

## Keputusan yang sudah disepakati
| # | Topik | Keputusan |
|---|---|---|
| 1 | Auth | **Clerk** (verifikasi JWT di backend lewat JWKS) |
| 2 | Frontend | **Vite + React + TypeScript + Tailwind**, deploy ke **Netlify**; `/api/*` di-proxy ke backend (satu origin, tanpa CORS) |
| 3 | API key BYOK | **Opsi (b)**: opsional disimpan **terenkripsi di DB** dengan secret server, supaya job terputus bisa dilanjut otomatis. Default tetap tidak menyimpan; pengguna memilih menyimpan |
| 4 | Backend host | **Hugging Face Space (Docker)**, bukan Render (RAM lebih besar, `MALAS_FULLTEXT=1` bisa nyala). Port HF = **7860** |
| 5 | Database | **Neon Postgres** (pooled URL untuk app, direct URL untuk migrasi Alembic) |
| 6 | File hasil | Antarmuka `Storage`; MVP boleh `bytea` di Neon, target **Cloudflare R2** |
| 7 | Antrean | Tabel Postgres + `FOR UPDATE SKIP LOCKED` (tanpa Redis) |

## Struktur repo sekarang (setelah Fase 2)
```
pyproject.toml            # root uv workspace (virtual) + dev group (pytest, httpx, ruff) + config pytest
pnpm-workspace.yaml / package.json   # skeleton JS (apps/web belum ada)
apps/api/                 # paket Python `malas_api`
  .env.example            # semua env backend (DATABASE_URL, DATABASE_URL_DIRECT, MALAS_SECRET_KEY, ...)
  alembic.ini             # hanya untuk CLI; runtime memakai malas_api.db.migrate() (script_location di dalam paket)
  src/malas_api/
    app.py                # FastAPI: routes, middleware sesi/header (auth Clerk bila CLERK_* diisi, selain itu cookie anonim)
    jobs.py               # JobManager: worker thread, claim antrean, heartbeat, pemulihan, key sesi/tersimpan
    repo.py               # SATU-SATUNYA tempat SQL: job/checkpoint/key; job <-> dict
    db.py                 # model SQLAlchemy 2, make_engine (Neon/SQLite), migrate(), Database
    migrations/           # Alembic: env.py, versions/0001_initial.py
    storage.py            # Storage Protocol + DbStorage (bytea). R2 = implementasi berikutnya
    auth.py               # Authenticator Clerk: JWT RS256 via PyJWKClient, azp, token_from_request (cookie hanya GET)
    crypto.py             # KeyCipher (Fernet+HKDF), cipher_from_env, rotasi lewat MALAS_SECRET_KEY_OLD
    vault.py              # key sesi di memori + redaksi log/error
    static/               # UI statis lama: AKAN DIHAPUS di Fase 4
  tests/                  # test_web, test_byok, test_resume, test_db (Fase 2), conftest (PG opsional)
  Dockerfile              # build context = ROOT: docker build -f apps/api/Dockerfile .
packages/engine/          # paket Python `malas`: crews, docx_converter, citations, fulltext, tolerant, CLI `kickoff`
  src/malas/{paths.py,templates/,examples/}
render.yaml               # Blueprint Render lama; diganti ke HF Space di Fase 5
```
Perintah penting: `uv sync --all-packages`, `uv run pytest -q` (133 lulus + 1 skip khusus Postgres), `uv run malas-web`,
`MALAS_MOCK=1 uv run kickoff --output x.docx`.
Tes ke Postgres: `MALAS_TEST_DATABASE_URL=postgresql://postgres@localhost:54329/malas_test uv run pytest apps/api`
(database DIKOSONGKAN tiap tes). Postgres 16 ada di sandbox: `/usr/lib/postgresql/16/bin`, jalankan sebagai user `postgres`
dengan data dir milik `postgres` (mis. `/var/tmp/pgdata-malas`, port 54329, `-A trust`); tidak aktif lagi di sesi baru.

## Status fase
- [x] **Fase 1: Restrukturisasi** (perilaku tidak berubah).
- [x] **Fase 2: Backend + Neon**. Selesai dan terverifikasi di SQLite dan Postgres 16 sungguhan.
  - Skema (Alembic 0001): `users`, `jobs` (kolom nyata + JSON `data`/`resume`), `job_checkpoints`, `job_files`, `user_api_keys`.
    Tabel `usage` SENGAJA ditunda ke Fase 3 (kuota).
  - Antrean di DB: `claim_next` (`FOR UPDATE SKIP LOCKED` + UPDATE bersyarat), 1 worker thread/proses, heartbeat
    (default tiap 20 dtk, basi 90 dtk), `recover_stale()` saat start + berkala, job zombie tidak menimpa job yang
    sudah dinyatakan mati (`_finish` hanya mengubah job `running`).
  - Checkpoint & `.docx` di DB (zlib / bytea); folder kerja per job di `<root>/work` dihapus setelah job.
  - Opsi 3b: `save_key`/`use_saved_key` di `POST /api/jobs`, `GET/DELETE /api/keys`, auto-resume sekali bila
    `key_source="saved"` + checkpoint ada. Key sesi (tanpa simpan) tetap hanya di memori; job antre yang kehilangan key
    karena restart gagal dengan pesan jelas.
  - Neon: `DATABASE_URL` (pooled) + `DATABASE_URL_DIRECT` (migrasi), `prepare_threshold=None` (PgBouncer), `pool_pre_ping`,
    `pg_advisory_xact_lock` saat migrasi.
  - Smoke test: server dari instalasi bersih (`--no-dev`) + Postgres: job mode uji selesai, restart server, riwayat & unduhan tetap ada.
  - BELUM dites terhadap Neon asli (tidak ada kredensial di sandbox). Yang berisiko: latensi cold-start Neon, perilaku PgBouncer.
- [x] **Fase 3: Auth + kuota**. Selesai; diverifikasi di SQLite (133 lulus) dan Postgres (108 api).
  - `auth.py`: `Authenticator` (RS256 saja; `iss`, `exp`, `sub` wajib; `azp` bila `CLERK_AUTHORIZED_PARTIES`), JWKS via
    `PyJWKClient`. Tes mencakup alg `none`, HS256-dengan-kunci-publik, issuer/azp salah, kunci lain, JWKS mati (-> 401),
    dan JWKS sungguhan lewat server HTTP lokal. Tes sudah dimutasi untuk memastikan ia benar-benar menjaga.
  - `app.py`: middleware: mode Clerk -> owner = `sub`, 401 untuk `/api/*` selain `/api/config`; tanpa Clerk -> cookie anonim
    (kompatibel mundur). `GET /api/me` (id, mode, kuota). `/api/config` kini memuat `auth` dan `daily_quota`. `SPACE_HOST`
    (HF) otomatis ke daftar Host yang diizinkan.
  - Kuota: tabel `usage` (migrasi 0002), `Repo.consume_quota` atomik (UPDATE bersyarat), refund bila batal sebelum jalan
    atau submit gagal; job lanjutan, auto-resume, dan Mode uji tidak dihitung. `MALAS_DAILY_QUOTA`, `MALAS_QUOTA_TZ`.
  - BELUM dites dengan Clerk asli (tidak ada akun). Risiko: format `azp`/`iss` instance nyata, dan cookie `__session` di
    belakang proxy Netlify (domain/SameSite). Verifikasi saat Fase 5.
- [ ] **Fase 4: Frontend React** (`apps/web`), port semua fitur `app.js` + UI simpan/hapus key tersimpan; `packages/api-types` dari OpenAPI
  (sekarang `openapi_url=None`, perlu dinyalakan untuk generasi tipe saat build); hapus `static/`.
- [ ] **Fase 5: Deploy + CI**: Dockerfile HF Space (port 7860, `PORT`), `netlify.toml`, GitHub Actions (pytest SQLite+Postgres service,
  ruff terbatas pada kode baru, typecheck + build web), `S3Storage` untuk R2, update DEPLOY.md. Ingat: HF Space bisa tidur; disk ephemeral.
- [ ] **Fase 6 (opsional)**: ToS/Privasi, email (Resend), Sentry, admin, pembayaran.

## Hal yang perlu diketahui
- Proteksi keamanan yang ada harus dipertahankan: key tidak ke disk/log/error, stdout dibungkam saat job,
  telemetry CrewAI mati di mode web, retensi otomatis. Dengan keputusan 3(b), key terenkripsi hanya boleh
  disimpan bila pengguna memilihnya, dan tidak pernah dikembalikan lewat API.
- Job CrewAI tidak bisa dihentikan di tengah jalan; yang bisa dibatalkan hanya yang masih mengantre.
- `malas-web` tidak mem-parse argumen CLI (`--help` langsung menyalakan server).
- Di sandbox tanpa internet, `kickoff` mencetak error ekspor telemetry OTel; tidak berbahaya.
- Batas free tier (Neon, HF, Netlify, Clerk, R2) berubah-ubah; cek ulang saat deploy.
- Jangan buat PR kecuali diminta. Push hanya ke `claude/jolly-maxwell-xdh9bs`.

## Desain UI Fase 4 (DRAFT, menunggu review pemilik)
Prototipe klik (satu berkas HTML, dibuat dengan Opus): `docs/design/malas-ui.html`.
Artifact (privat): https://claude.ai/artifact/Ab8P4YSww4WU7wKKAhgWfE. Routing hash: `#beranda #masuk #dasbor #buat #job #pengaturan #keadaan #catatan`.
Layar: landing, masuk (tiruan Clerk, diganti `<SignIn/>`/`<SignUp/>`), dasbor, buat makalah, detail job (6 status + simulasi progres),
pengaturan, state khusus (401/429/antrean penuh/offline/skeleton), catatan desain (token, komponen, peta rute ke API).
Keputusan desain: identitas "pulpen biru & stabilo" (biru tinta untuk aksi, kuning stabilo hanya untuk sitasi); font Bricolage
Grotesque (judul), Plus Jakarta Sans (teks), JetBrains Mono (id model/NIM/log); token di `:root` + mode gelap; form SATU halaman
bersegmen (bukan wizard); key tersimpan jadi pilihan bawaan bila ada, "Simpan key saya" default mati; aksi terlarang tetap tampil
tapi nonaktif + alasan; "Lanjutkan" lewat dialog (n/m sub-bab, tidak memakai kuota); status = ikon + teks (bukan warna saja);
container query + bottom nav 3 tab di ponsel.
Diverifikasi saya: tidak ada error JS di 8 layar x terang/gelap x desktop/ponsel. Masalah kecil yang tersisa (cuma di ponsel):
overflow horizontal 4px di Detail job (baris id model) dan 135px di Catatan desain (tabel); bukan bagian produk, boleh diabaikan atau
dirapikan saat porting.
Celah API yang ditemukan desain (kandidat tugas backend kecil): riwayat (`GET /api/jobs`) belum memuat `mata_kuliah` dan ringkasan
progres; belum ada posisi antrean; durasi per tahap belum dicatat; OpenAPI perlu dinyalakan untuk generasi tipe.
Pertanyaan terbuka untuk pemilik: (1) template tampil sebagai nama berkas atau label ramah + pratinjau (butuh metadata server);
(2) lama simpan riwayat/.docx dan hitung mundur penghapusan; (3) key tersimpan kedaluwarsa otomatis?; (4) notifikasi selesai
(email Resend / browser)?; (5) kuota final 3/hari dan selalu tampil di header?; (6) metode masuk Clerk & wajib verifikasi email?;
(7) estimasi biaya sebelum kirim atau cukup token sesudahnya?; (8) model OpenRouter diketik bebas atau daftar teruji?;
(9) Mode uji terlihat semua pengguna atau di "Opsi lanjutan"?; (10) siapa menulis ToS/Privasi + persetujuan eksplisit saat daftar?
### Revisi v2 (landing ditulis ulang atas masukan pemilik: "kurang pas, harusnya relate sama rasa males")
- Headline: "Males bikin makalah? Santai, biar MALAS yang bikinin drafnya." (alternatif: "Tugas makalah numpuk? Ketik judulnya, drafnya
  biar MALAS yang nyusun." / "Mager nulis? Kasih judulnya, MALAS yang nyusun drafnya."). Sub-judul: 3 langkah + "10-30 menit, tergantung model".
- Urutan landing: hero (coba ketik judul, pratinjau outline+sitasi tiruan) -> 3 langkah (mini-animasi, "Putar ulang") ->
  "Kamu lagi di mana?" (4 chip opsional) -> "Biar adil" (draf, cek sitasi, aturan kampus, waktu/biaya/kuota) -> privasi key -> FAQ (7) -> CTA -> footer.
- Aturan "tidak memaksa": tanpa popup/modal otomatis/scroll-jacking/suara/urgensi palsu/CTA lengket; animasi berhenti sendiri, ada tombol
  "Jeda animasi", `prefers-reduced-motion` = keadaan akhir statis. DILARANG: klaim lolos deteksi AI, jaminan nilai, saran menyembunyikan AI.
- Dua overflow ponsel (Detail job, Catatan desain) sudah diperbaiki. Panel "Landing v2" di Catatan desain memuat panduan suara (Pakai/Jangan).
- Verifikasi (agen + saya, Playwright): nol error konsol/pageerror dan nol overflow horizontal di semua layar x terang/gelap x 1280/390;
  keadaan reduced-motion benar. Belum: mode "Bingkai ponsel", pembaca layar asli, kontras AA dengan alat ukur.
- Polish kecil untuk porting: saat stabilo "menggores" kata MALAS di mode gelap, huruf yang belum tersorot sempat redup ~0,9 dtk karena
  `color` ikut dianimasikan (keyframe `swipe`); animasi landing mengulang tiap kembali ke #beranda; pratinjau hero berganti setelah judul selesai diketik.
- Pertanyaan terbuka baru: (a) nada santai ("kamu") dipakai di seluruh aplikasi atau landing saja? Saran agen: "kamu" di semua, candaan hanya
  di empty state/sapaan/toast sukses; error, privasi, hapus, kuota habis, sesi berakhir tetap lugas. (b) pilih headline final dari 3 opsi;
  (c) ganti sitasi tiruan di pratinjau ("Pratama, 2023") dengan penanda netral "(Penulis, Tahun)"?; (d) chip "Jam 2 pagi, deadline jam 8"
  dipertahankan atau dihapus (bisa terbaca mendorong kerja mepet)?

### Revisi v4 (ilustrasi manusia DITOLAK pemilik; diganti maskot geometris)
- v3 (tokoh manusia di bean bag) ditolak: "gak rapih, itu manusia atau apa". Dibuang total beserta token `--ill-skin`/`--ill-paper`.
- Sekarang: LEMBAR MAKALAH BERMUKA yang tidur (kertas sudut terlipat, garis margin merah, mata tertutup, senyum, pipi, stabilo, "zz"),
  ~12 elemen primitif, satu tebal garis, warna hanya dari token yang ada. Dua ukuran: besar (CTA, 200px) dan kompak (langkah 3, 136px).
  Progres: bar tipis + lencana centang saat selesai. Gerak: napas scale(1.03), "zz" 3x; `.calm`/reduced-motion = keadaan akhir. Hook skrip langkah 3 utuh.
- Dua alternatif kecil ada di Catatan desain (B: bantal bulat bermuka; C: stabilo tidur). Keduanya belum dipoles (B: lembar mengintip terpotong; C: terbaca seperti baterai).
- Tata letak dirapikan setelah saya lihat sendiri: CTA dibatasi 34em dan dipusatkan (sebelumnya ilustrasi terdorong ke tepi kanan dengan ruang kosong besar);
  ilustrasi langkah 3 dipusatkan (sebelumnya menempel kiri).
- Kekurangan yang diketahui: di mode gelap "kertas" = `--surface` (navy), bukan putih; detail kecil (pipi, baris teks) nyaris hilang di 64px;
  lencana centang dan chip .docx di langkah 3 sama-sama menandakan "selesai" (bisa hapus salah satu). Belum dicek: mode "Bingkai ponsel".

### Revisi v5 (hook dipadatkan + branding kepanjangan MALAS)
- MALAS = **M**akalah **A**utomation via **L**anguage-model **A**ssisted **S**ystem (akronim resmi; juga plesetan "malas"). Aturan tulis: "MALAS" selalu kapital;
  kepanjangan resmi berbahasa Inggris dengan "via" kecil dan "Language-model" bertanda hubung; gloss Indonesia hanya untuk nuansa di landing. Ada di Catatan desain > "Merek".
- Headline hero: **"Kamu mager, MALAS yang gerak."** (plesetan "mager" = malas gerak). Kandidat lain di Catatan desain: "Judul masuk, draf keluar." / "Males nulis? Biar MALAS." /
  "Rebahan dulu, drafnya nyusul." / "Ketik judul, terus rebahan." / "Tugas numpuk? MALAS-in aja." / "Mager boleh, draf tetap jadi." / "Kamu rebahan, draf jalan."
- Teks dipangkas: sub-judul "Ketik judul, tempel API key, rebahan. Drafnya jadi berkas .docx."; chip hero "±10-30 menit / Hasilnya draf / Pakai key-mu"; judul section pendek
  ("Tiga langkah, beres.", "Pilih situasimu.", "Yang perlu kamu tahu", "Yang sering ditanya"); CTA "Coba gratis" / "Masuk"; penutup "Tutup 14 tab jurnalnya.".
  Kejujuran tetap ada (draf, cek sitasi, aturan kampus, 10-30 menit, biaya dari key sendiri, kuota 3/hari, Mode uji) tetapi dipindah ke "Biar adil" dan FAQ.
- Strip "MALAS itu singkatan." tepat setelah 3 langkah: kalimat lengkap (huruf awal berstabilo) + 5 kartu (huruf, kata, gloss) selalu terbaca tanpa interaksi;
  hover/fokus/tap menyorot satu kartu (`aria-pressed`); animasi masuk sekali, mati di `.calm`. Footer memuat kepanjangan satu baris.
- Verifikasi (saya, Playwright, setelah perubahan terakhir): 0 error konsol/pageerror, 0 overflow di semua layar x terang/gelap x 1280/390; saya lihat landing penuh
  terang desktop dan gelap ponsel.
- Kekurangan yang diketahui: kartu langkah 1-2 punya ruang kosong di bawah (kartu 3 lebih tinggi); "3 makalah per hari" dan "Mode uji gratis" tidak lagi jadi chip hero
  (ada di "Biar adil" dan FAQ); gloss "AI yang nyusun drafnya" menyederhanakan; kolom FAQ hanya memakai separuh kiri lebar di desktop.
- Pertanyaan terbuka: CTA "Coba gratis" atau lebih berkarakter ("Gaskeun")?; kepanjangan perlu muncul juga di halaman Masuk/Daftar atau "Tentang"?;
  "Mode uji gratis" kembali jadi chip hero?

LANGKAH: jangan mulai coding `apps/web` sebelum pemilik menyetujui/merevisi desain ini.

## Langkah berikutnya (mulai di sini)
Fase 4: frontend `apps/web` (Vite + React + TS + Tailwind + `@clerk/clerk-react`).
1. Scaffold `apps/web`, proxy dev `/api` -> `http://127.0.0.1:8000`, `.env.example` (`VITE_CLERK_PUBLISHABLE_KEY`).
2. Nyalakan OpenAPI saat build (`openapi_url=None` sekarang; buat skrip yang membuat skema tanpa membuka endpoint publik,
   mis. `app.openapi()` dari `create_app`), generate `packages/api-types` (openapi-typescript) + klien fetch bertipe
   yang menyisipkan `Authorization: Bearer` dari `useAuth().getToken()`.
3. Halaman: landing, masuk/daftar (Clerk), dashboard riwayat (polling), form "Buat makalah" (port semua fitur `static/app.js`:
   mode uji, BYOK OpenRouter/Kenari + model, simpan key, template, penyusun dinamis), detail job (progres per tahap, unduh
   lewat fetch+blob dengan header, lanjutkan dari checkpoint, hapus), pengaturan (key tersimpan, sisa kuota dari `/api/me`).
4. Hapus `apps/api/src/malas_api/static/` dan rute `/` + mount `/static` (atau sisakan halaman kecil), perbarui tes yang menyentuhnya.
5. Pastikan CSP di `app.py` cocok dengan web (web di domain Netlify terpisah; API tidak menyajikan HTML lagi).

Yang saya butuhkan dari pengguna: Publishable key Clerk (aman dicantumkan di env web) dan, untuk uji penuh, akun Clerk
dev. Frontend bisa dibangun dan dites tanpa itu (mock Clerk di tes), tapi uji login nyata butuh instance.

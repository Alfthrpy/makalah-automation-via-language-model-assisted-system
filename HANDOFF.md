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

## Struktur repo sekarang (setelah Fase 1)
```
pyproject.toml            # root uv workspace (virtual) + dev group (pytest, httpx, ruff) + config pytest
uv.lock
pnpm-workspace.yaml / package.json   # skeleton JS (apps/web belum ada)
apps/api/                 # paket Python `malas_api`: app.py (FastAPI), jobs.py (JobManager berbasis file), vault.py (BYOK in-memory)
  src/malas_api/static/   # UI statis lama (index.html, app.js, app.css): AKAN DIHAPUS di Fase 4
  tests/                  # test_web, test_byok, test_resume
  Dockerfile              # build context = ROOT: docker build -f apps/api/Dockerfile .
packages/engine/          # paket Python `malas`: crews, docx_converter, citations, fulltext, tolerant, CLI `kickoff`
  src/malas/paths.py      # lokasi templates/examples terlepas dari cwd
  src/malas/templates/    # template makalah*.docx (dulu template_and_output/)
  src/malas/examples/     # contoh.yaml (dulu input/)
  tests/                  # test_docx_converter, citations, fulltext, tolerant, utils
render.yaml               # Blueprint Render lama; diganti pindah ke HF Space di Fase 5
```
Perintah penting: `uv sync --all-packages`, `uv run pytest -q` (90 tes), `uv run malas-web`,
`MALAS_MOCK=1 uv run kickoff --output x.docx`.

## Status fase
- [x] **Fase 1: Restrukturisasi** (perilaku tidak berubah). Selesai. 90 tes lulus; CLI mode uji jalan; server
  dari instalasi bersih `uv sync --frozen --no-dev --package malas-api` jalan (healthz/config/index/static OK).
  Dockerfile BELUM pernah di-build (tidak ada Docker daemon di sandbox); langkahnya divalidasi manual.
- [ ] **Fase 2: Backend + Neon**: SQLAlchemy 2 + psycopg 3 + Alembic; tabel `users`, `jobs`, `job_checkpoints`, `files`, `usage`;
  ganti JobManager berbasis file; worker `SKIP LOCKED` + heartbeat; `Storage`; enkripsi key BYOK (Fernet) opsional.
- [ ] **Fase 3: Auth + multi-tenant**: JWT Clerk, filter `user_id`, kuota, pertahankan proteksi lama (redaksi log/error, batas body, TrustedHost).
- [ ] **Fase 4: Frontend React** (`apps/web`), port semua fitur `app.js`; `packages/api-types` dari OpenAPI; hapus `static/`.
- [ ] **Fase 5: Deploy + CI**: Dockerfile untuk HF Space (port 7860), `netlify.toml`, GitHub Actions (pytest, ruff, typecheck, build web, cek tipe OpenAPI), update DEPLOY.md.
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

## Langkah berikutnya (mulai di sini)
Fase 2. Urutan yang disarankan:
1. Tambah dependensi (sqlalchemy, psycopg[binary], alembic, cryptography) di `apps/api/pyproject.toml`; `uv lock`.
2. Rancang skema + migrasi Alembic pertama; tes pakai Postgres lokal atau SQLite untuk unit, Postgres untuk integrasi bila tersedia.
3. Buat repository (`JobRepo`) dengan antarmuka yang sama dengan JobManager sekarang agar tes lama bisa dipakai ulang.
4. Pindahkan checkpoint (`malas.checkpoint`) ke DB lewat antarmuka, bukan file.
5. Worker + heartbeat + penandaan job basi.

Yang saya butuhkan dari pengguna sebelum/selama Fase 2: connection string Neon (pooled + direct), via env/secret,
**jangan ditempel di chat**.

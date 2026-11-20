# HANDOFF: implementasi desain MALAS menjadi frontend `apps/web`

> Untuk sesi yang membangun frontend. Baca file ini dulu, lalu `HANDOFF.md` (konteks proyek, Fase 1-3 backend sudah selesai).
> Branch kerja: `claude/jolly-maxwell-xdh9bs`. Jangan buat PR kecuali diminta.

## 0. Sumber kebenaran desain
- **Prototipe klik** (satu berkas HTML, ~2550 baris, vanilla JS): `docs/design/malas-ui.html`. Buka langsung di browser; routing pakai hash
  (`#beranda #masuk #dasbor #buat #job #pengaturan #keadaan #catatan`). Bilah gelap di atas ("Prototipe · data contoh") BUKAN bagian produk.
- Artifact (privat, versi 6 saat handoff ditulis): https://claude.ai/artifact/Ab8P4YSww4WU7wKKAhgWfE. Bila artifact dan berkas berbeda, **berkas di repo yang menang**.
- Layar `#catatan` (Catatan desain) memuat token, komponen, peta rute-API, keputusan UX, panduan suara. Layar `#keadaan` memuat semua state khusus (401/429/dll).
  Keduanya DOKUMENTASI: jangan dikirim ke produksi (boleh jadi rute dev-only `/_design`).
- Pemilik sudah menyetujui arah desain ("sip"). Pertanyaan terbuka di bagian 9 punya DEFAULT yang boleh dipakai sampai pemilik mengubahnya.

## 1. Keputusan stack (sudah final)
| Hal | Pilihan |
|---|---|
| Build | Vite + React 18/19 + TypeScript (strict) |
| Gaya | Tailwind (v4 `@theme` atau v3.4) **memetakan ke CSS variables token prototipe**; animasi landing yang rumit dipindah sebagai CSS biasa (bukan utility) |
| Auth | `@clerk/clerk-react`; token lewat `useAuth().getToken()` dipasang di header `Authorization: Bearer` |
| Router | react-router (path, bukan hash) |
| Data | TanStack Query (polling job) |
| Validasi | zod (cermin aturan backend, lihat 4.3) |
| Font | self-host `@fontsource` (Bricolage Grotesque, Plus Jakarta Sans, JetBrains Mono) |
| Tes | Vitest + Testing Library + MSW; e2e Playwright (sudah terpasang di sandbox: `require('playwright')`, jangan `playwright install`) |
| Deploy | Netlify (Fase 5), `/api/*` di-proxy ke backend (satu origin, tanpa CORS) |

Struktur yang disarankan:
```
apps/web/
  index.html, vite.config.ts (proxy /api -> http://127.0.0.1:8000), tailwind config, .env.example
  src/
    main.tsx, App.tsx, routes.tsx
    styles/{tokens.css, base.css, landing.css}      # token dari prototipe (bagian 2), terang+gelap
    copy/id.ts                                       # SEMUA teks UI di satu tempat (nada bisa diubah murah)
    lib/{api.ts, auth.tsx, validation.ts, format.ts, storage.ts}
    features/{landing, auth, dashboard, create, job, settings, states}/
    components/{ui/*, icons.tsx, Mascot.tsx}
packages/api-types/                                  # tipe dari OpenAPI (bagian 5)
```

## 2. Design tokens (salin dari `:root` prototipe; sumber: baris ~10-66)
Terang: `--bg #f4f5f8, --surface #fff, --surface-2 #eceef4, --ink #161a2c, --muted #545b73, --line #d9dce6, --line-strong #b9bed0,
--accent #2c3a9e (biru pulpen), --accent-hover #222e85, --accent-soft #e5e8fa, --on-accent #fff, --mark #ffe55c (stabilo), --mark-ink #1d1a05,
--margin-red #e0607a, --rule #cfd8f0, --ok #14703a/--ok-soft #e1f3e7, --warn #855400/--warn-soft #fcefd2, --bad #b3261e/--bad-soft #fbe6e4`.
Gelap (`prefers-color-scheme` + `[data-theme=dark]`; tombol tema Sistem/Terang/Gelap, simpan di localStorage dengan try/catch): `--bg #0f1220, --surface #171b2b,
--surface-2 #20253a, --ink #e8eaf5, --muted #a3a9c2, --line #2c3249, --accent #a3aeff, --accent-soft #262d55, --on-accent #10132a, --mark #e9cf3f, ...`.
Tipografi: display `Bricolage Grotesque`, teks `Plus Jakarta Sans`, mono `JetBrains Mono` (id model, NIM, log, kode). Skala `--fs-xs .78rem ... --fs-3xl clamp(2rem,1.4rem+2.6vw,3.1rem)`.
Spasi kelipatan 4 (`--sp-1..8` = 4,8,12,16,24,32,48,64), radius `8/12/18/999`, `--tap: 44px`, `--maxw: 1120px`.
Aturan pakai: biru = aksi + status berjalan; **kuning stabilo HANYA untuk sitasi dan satu kata di hero, tidak pernah untuk tombol**; status = ikon + teks (bukan warna saja).
Jangan menambah token warna baru tanpa alasan (ilustrasi hanya memakai token yang ada).

## 3. Layar -> rute -> komponen -> API
| Rute | Bagian prototipe | Data/API | Catatan |
|---|---|---|---|
| `/` | `#scr-beranda` (baris ~771) | `GET /api/config` (publik) | Pengguna yang sudah masuk diarahkan ke `/dasbor` |
| `/masuk`, `/daftar` | `#scr-auth` | Clerk | Ganti kartu tiruan dengan `<SignIn/>`/`<SignUp/>`, tema lewat prop `appearance` (variables dari token) |
| `/dasbor` | `#scr-dasbor` | `GET /api/me`, `GET /api/jobs`, `config.active_job` | Polling 5 dtk HANYA bila ada job aktif; skeleton, empty state, banner job aktif |
| `/buat` | `#scr-buat` | `GET /api/config`, `/api/me`, `/api/keys` -> `POST /api/jobs` | Form satu halaman bersegmen (5 segmen + ringkasan menempel); draf form di localStorage TANPA api key |
| `/job/:id` | `#scr-job` | `GET /api/jobs/:id` (polling 1,5 dtk saat aktif), `DELETE`, `/download` | Stepper, log, ringkasan, aksi per status, dialog Lanjutkan |
| `/pengaturan` | `#scr-pengaturan` | `GET /api/me`, `GET/DELETE /api/keys` | Akun dari Clerk, kuota, key tersimpan |
| `*` | state "tidak ditemukan" | - | 404 |
State khusus (komponen/overlay, bukan rute): kuota habis (429), antrean penuh (429), sesi kedaluwarsa (401 -> dialog "Masuk lagi"), koneksi putus saat polling
(banner + coba lagi), error validasi (ringkasan + inline), skeleton, job tidak ditemukan (404), server tidak bisa dihubungi.

### Inventaris komponen (lihat kelas CSS di prototipe)
Button (primary/secondary/ghost/danger, disabled DENGAN alasan tertulis `aria-disabled` + teks), Badge status (queued/running/done/error/interrupted/cancelled; ikon+teks;
`· uji` untuk mock), Field/Input/Textarea/Select/Radio-card, PenyusunList (dinamis 1-10, nama+NIM), Card, Banner (info/warn/bad), Stepper (7 tahap: pending/running/done/skipped/error,
detail teks, durasi bila ada), LogPanel (mono, 300 baris maks), QuotaPill (header: titik) + QuotaCard, Toast, Dialog konfirmasi (hapus/batal) + dialog Lanjutkan, Skeleton,
EmptyState, ThemeToggle, BottomNav (3 tab di ponsel), FAQ (`<details>`), Mascot (SVG lembar tidur), ikon (36 simbol `i-*` di sprite prototipe: ekstrak ke `icons.tsx`).
Responsif: prototipe memakai container query pada kerangka aplikasi; di Tailwind boleh breakpoint biasa (ponsel <= ~720px: bottom nav, tombol kirim menempel di bawah form).

## 4. Kontrak API backend (kondisi sekarang)
Semua `/api/*` kecuali `/api/config` wajib `Authorization: Bearer <JWT Clerk>` (mode anonim cookie hanya bila `CLERK_*` kosong: dipakai dev lokal/tes).
Kesalahan: `{"detail": "teks"}`; 422 = `{"detail":[{"loc":[...],"type","msg","ctx"?}]}` (input TIDAK dipantulkan). Kode: 401 belum masuk, 404 bukan milikmu/tidak ada, 409 tidak bisa dilanjutkan/penyimpanan key mati,
413 body > 100 KB, 422 validasi, 429 kuota habis / antrean penuh / sudah ada job aktif (mode hosting).
| Endpoint | Respons |
|---|---|
| `GET /api/config` | `{hosted, server_key_available, models, api_key_ok, mock_default, fulltext, providers:[{id,label,enabled,key_url,models[],default_planner,default_writer,needs_model}], templates:[nama], default_template, steps:[{key,label,hint}], active_job, key_storage, auth:{mode,required}, daily_quota, year}` |
| `GET /api/me` | `{id, mode:"clerk"|"anonymous", quota:{limit,used,remaining,resets_at}|null}` |
| `GET /api/jobs` | ringkasan: `[{id,status,title,created_at,finished_at,mock,byok,has_file,resume}]` |
| `GET /api/jobs/:id` | `{id,status,created_at,started_at,finished_at,title,mock,byok,key_source,provider,models,resume_from,resume:{available,done,total}|null,template,request,steps:{<key>:{status,detail}},log:[{t,msg}],error,error_step,usage:{calls,prompt,completion,total}|null,stats:{subbab_count,refs_found,fulltext_ok?,fulltext_total?,citations_total,citations_invalid_before,citations_invalid_after,refs_final,refs_pruned}|null (kunci opsional bisa tidak ada),has_file,quota_day,auto_resumed}` |
| `POST /api/jobs` -> 202 job | body: `judul(3-200), mata_kuliah(2-120), dosen_pengampu, penyusun[{nama(1-100),nim}](1-10), kelas, universitas, fakultas, jurusan, kota, tahun(19xx/20xx), template, mock, provider, api_key, model_planner, model_writer, resume_from, save_key, use_saved_key` |
| `DELETE /api/jobs/:id` | `{result:"deleted"|"cancelled"}`; 409 bila sedang berjalan |
| `GET /api/jobs/:id/download` | bytes `.docx`. Dari web: `fetch` + header + `blob` + tautan sementara (cookie `__session` hanya untuk GET, tapi jangan mengandalkannya) |
| `GET /api/keys` | `{enabled, keys:[{provider,saved_at}]}` (NILAI key tidak pernah dikembalikan) |
| `DELETE /api/keys/:provider` | `{result:"deleted"}` / 404 |
Status job: `queued running done error interrupted cancelled`. Status tahap: `pending running done skipped error`. Progres sub-bab ada di `steps.tulis.detail` (teks "3/11 · 2.1 Teori"):
parsing teks itu rapuh -> lihat tugas backend B1.

### 4.3 Validasi form (cermin backend)
`KEY_RE ^[\x21-\x7e]{8,300}$` (ASCII tercetak, tanpa spasi); Kenari: diawali `kn-`; model `^[A-Za-z0-9][A-Za-z0-9._:/\-]{0,99}$`; tahun `^(19|20)\d{2}$`; panjang sesuai tabel di atas;
backend membersihkan karakter XML-ilegal. Kenari WAJIB mengisi model (tidak ada default; saran `step-3-7-flash:free`); OpenRouter default planner `deepseek/deepseek-v3.2`, writer `google/gemini-2.5-flash`.

## 5. Tugas backend kecil yang disarankan SEBELUM/BERSAMA frontend
Semua kecil; kerjakan di `apps/api` dengan tes. Jalankan `uv run pytest -q` (+ Postgres bila perlu, lihat `HANDOFF.md`).
- **B1** `GET /api/jobs`: tambah `mata_kuliah`, `progress:{done,total}|null`, `current_step` (key tahap berjalan) supaya riwayat dan banner job aktif tidak perlu memanggil detail.
  Sumber data: simpan `mata_kuliah` ke kolom/`data`; hitung progres dari `steps`/checkpoint (jangan parsing teks bebas bila bisa disimpan terstruktur: `_progress` info "n/m").
- **B2** posisi antrean: `queue_position` (1 = berikutnya) + job aktif di depan, untuk status Antre.
- **B3** durasi per tahap: catat `started_at`/`finished_at` per tahap di `_progress` (stepper menampilkannya bila ada).
- **B4** response model Pydantic untuk semua endpoint (JobOut, JobSummary, MeOut, ConfigOut, KeysOut) + skrip ekspor OpenAPI (`app.openapi()` bekerja walau `openapi_url=None`;
  JANGAN membuka `/openapi.json` publik) -> `packages/api-types` (openapi-typescript). Bila belum sempat: tulis tipe TS manual dulu dari tabel 4, ganti nanti.
- **B5** (setelah web berjalan) hapus UI statis `apps/api/src/malas_api/static/` + rute `/` dan mount `/static`; sesuaikan tes yang menyentuhnya.
- **B6** (jika pemilik memilih label template ramah) `GET /api/config.templates` jadi objek `{file,label,description?}`.

## 6. Landing: perilaku yang HARUS dipertahankan (sumber: `initLanding` dkk, baris ~2368-2554)
Prinsip: animatif dan interaktif TAPI TIDAK MEMAKSA. Tanpa popup/modal otomatis, tanpa scroll-jacking, tanpa suara, tanpa timer/urgensi palsu, tanpa CTA lengket.
- Hero "coba ketik judul": pratinjau outline Bab I-III + 2 sitasi stabilo dibentuk lokal dari judul (fungsi `topicParts`/`renderPreview`); label jujur "Pratinjau tiruan...".
  Tanpa interaksi memutar `TRY_SAMPLES` 6 putaran lalu diam; berhenti begitu input difokus. Sitasi tiruan sudah berlabel tiruan (usulan: ganti ke "(Penulis, Tahun)" bila pemilik mau).
- 3 langkah: tiap kartu punya mini-animasi, main SEKALI saat terlihat (IntersectionObserver, bergiliran), tombol "Putar ulang". Langkah 3 menjalankan 7 tahap asli lalu `.docx` muncul; hook `data-s3-*` dan kelas `.play/.done` pada maskot.
- Chip "Kamu lagi di mana?" (`SITU`: baru dapet tugas / H-3 / H-1 / jam 2 pagi): blok inline "Tanpa MALAS / Pakai MALAS" + bar waktu; menyorot langkah relevan (cincin stabilo + label teks "Pas buat situasimu"); bukan modal.
- Strip "MALAS itu singkatan.": kalimat lengkap (huruf awal berstabilo) + 5 kartu (M/A/L/A/S, kata, gloss) SELALU terbaca; hover/fokus/tap menyorot satu kartu (`aria-pressed`); animasi masuk sekali. Footer: kepanjangan satu baris.
- Kontrol gerak: tombol "Jeda animasi"/"Putar animasi" terlihat di hero dan bagian langkah (langsung ke keadaan akhir); `prefers-reduced-motion` => kelas `calm`, semua statis di keadaan akhir.
- Maskot: lembar makalah bermuka yang tidur (SVG inline, ~12 bentuk, satu tebal garis, warna dari token); dua ukuran (CTA ~200px, langkah 3 ~136px); napas `scale(1.03)`, "zz" 3x; `aria-hidden`.
- Polish yang diketahui: saat stabilo "menggores" kata MALAS di mode gelap teks sempat redup ~0,9 dtk (keyframe `swipe` menganimasikan `color`); animasi landing mengulang tiap kembali ke beranda.
- **Teks jujur yang WAJIB tetap ada** (nada santai tapi tidak dihapus): hasil = DRAF yang dibaca dan dicek; sitasi dicocokkan dengan sumber asli; aturan kampus/dosen soal AI = tanggung jawab pengguna;
  waktu nyata 10-30 menit tergantung model; biaya ditagih penyedia ke key pengguna + Mode uji gratis + kuota harian; "Bisa langsung dikumpulin? Jangan.". DILARANG: klaim lolos deteksi AI, jaminan nilai, saran menyembunyikan penggunaan AI, urgensi palsu.
- Merek: **MALAS = Makalah Automation via Language-model Assisted System**. Selalu "MALAS" kapital; kepanjangan resmi bahasa Inggris dengan "via" kecil dan "Language-model" bertanda hubung; gloss Indonesia hanya di landing.
  Headline: "Kamu mager, MALAS yang gerak." CTA: "Coba gratis" / "Masuk".

## 7. Aturan keamanan di web (jangan dilanggar)
- API key HANYA di state komponen/form: tidak ke localStorage/sessionStorage/IndexedDB/URL/query/log/analytics/Sentry; `type="password" autocomplete="new-password"`; kosongkan setelah kirim dan saat `pagehide`/unmount. Draf form disimpan TANPA key.
- Jangan pernah menampilkan key tersimpan (hanya penyedia + tanggal simpan). Pesan privasi harus jujur: default TIDAK disimpan; "Simpan key saya (terenkripsi)" default mati; pilihan bawaan = "Pakai key tersimpan" bila ada.
- 401 di mana saja => dialog "Sesi Anda berakhir" + tombol masuk lagi (formulir tetap di perangkat kecuali key). Tangani 429 dengan pesan dari `detail`.
- Header keamanan/CSP untuk web diatur di Netlify (`_headers`/`netlify.toml`): `connect-src 'self'` + domain Clerk, `frame-ancestors 'none'`, dst. (Fase 5).
- Jangan menaruh secret apa pun di env `VITE_*` (publik). Hanya `VITE_CLERK_PUBLISHABLE_KEY` dan `VITE_AUTH_MODE`.

## 8. Rencana kerja bertahap (disarankan; commit per tonggak)
- **M0 Persiapan**: scaffold `apps/web`, Tailwind + token, font, router, `AuthProvider` abstrak (`clerk` vs `dev`; mode `dev` memakai cookie anonim backend supaya dev/tes tanpa Clerk), klien API + TanStack Query, MSW, Vitest. `pnpm install` di root workspace.
- **M1 Landing + merek** (paling berkarakter): port CSS + perilaku bagian 6 ke komponen React; uji reduced-motion, tombol jeda, aksesibilitas keyboard. Bandingkan screenshot dengan prototipe (Playwright, terang/gelap, 1280/390).
- **M2 Auth + shell aplikasi**: Clerk, rute terlindungi, header + QuotaPill + ThemeToggle + BottomNav, penanganan 401/offline global, toast, dialog.
- **M3 Dasbor + Detail job**: riwayat, banner job aktif, empty/skeleton, polling, stepper, log, unduh blob, hapus/batal, dialog Lanjutkan (key tersimpan atau isi key).
- **M4 Buat makalah**: form bersegmen + validasi zod + ringkasan biaya/kuota + penyusun dinamis + BYOK (OpenRouter/Kenari) + simpan key + Mode uji + draf localStorage.
- **M5 Pengaturan + state khusus** (429/401/404/offline/validasi).
- **M6 Hardening**: axe (kontras AA, fokus, label), e2e Playwright alur utama terhadap backend sungguhan (`uv run malas-web` mode anonim + Mode uji: landing -> dasbor -> buat (mock) -> job selesai -> unduh .docx valid "PK"),
  tes unit untuk validasi/format, bundle size, hapus UI statis backend (B5).
Backend B1-B4 sebaiknya masuk sebelum M3 agar dasbor tidak perlu workaround.

## 9. Keputusan terbuka (DEFAULT dipakai bila pemilik tidak menjawab)
| # | Pertanyaan | Default |
|---|---|---|
| 1 | Nada santai di seluruh aplikasi? | Pakai "kamu" di seluruh aplikasi; candaan hanya di empty state/sapaan/toast sukses; error, privasi, hapus, kuota habis, sesi berakhir tetap lugas. (Prototipe layar aplikasi masih "Anda": ubah saat porting; semua teks di `copy/id.ts` agar mudah dibalik) |
| 2 | CTA | "Coba gratis" |
| 3 | Sitasi tiruan di pratinjau hero | Ganti "(Penulis, Tahun)" |
| 4 | Chip "Jam 2 pagi, deadline jam 8" | Pertahankan (teksnya mengingatkan menyisihkan waktu mengecek) |
| 5 | "Mode uji gratis" jadi chip hero lagi? | Tidak; cukup di "Yang perlu kamu tahu" dan FAQ |
| 6 | Kepanjangan di halaman Masuk/Daftar | Tidak |
| 7 | Label template ramah + pratinjau | Tampilkan nama berkas dulu (B6 menyusul bila diminta) |
| 8 | Lama simpan riwayat/.docx | Ikuti `MALAS_WEB_RETENTION_HOURS` (48 jam di hosting sejak 2026-11-20; sebelumnya 6); tampilkan keterangan "dihapus otomatis" tanpa hitung mundur |
| 9 | Key tersimpan kedaluwarsa otomatis | Belum |
| 10 | Notifikasi selesai (email/browser) | Belum (Fase 6) |
| 11 | Kuota final | 3/hari (`MALAS_DAILY_QUOTA`), selalu tampil di header |
| 12 | Metode masuk Clerk/verifikasi email | Atur di dashboard Clerk (email + Google disarankan) |
| 13 | Estimasi biaya sebelum kirim | Tidak; tampilkan token sesudahnya (`usage.total`) |
| 14 | Model OpenRouter diketik bebas? | Saran + input bebas (validasi `MODEL_RE`) |
| 15 | ToS/Privasi | Placeholder halaman; teks dari pemilik, persetujuan eksplisit saat daftar (Fase 6) |

## 10. Cara menjalankan lokal
```bash
uv sync --all-packages
uv run malas-web                      # API di http://127.0.0.1:8000, SQLite di output/, mode anonim (cookie), tanpa Clerk
pnpm install && pnpm --filter web dev # web, proxy /api -> 8000, VITE_AUTH_MODE=dev
```
Mode Clerk lokal: isi `CLERK_ISSUER` (+ `CLERK_AUTHORIZED_PARTIES=http://localhost:5173`) untuk backend dan `VITE_CLERK_PUBLISHABLE_KEY` untuk web.
Uji penuh login nyata membutuhkan akun Clerk dev dari pemilik (kunci lewat env/secret, JANGAN ditempel di chat). Tanpa itu, uji dengan `AuthProvider` mode `dev` dan JWT palsu di tes backend (sudah ada di `apps/api/tests/test_auth.py`).

## 11. Verifikasi yang diharapkan di akhir (jujur soal yang belum)
Per tonggak: tes lulus, build bersih, tanpa error konsol, tanpa overflow horizontal (cek `scrollWidth` vs `clientWidth` di semua rute, terang/gelap, 1280/390), screenshot dibandingkan dengan prototipe.
Pernah lolos di prototipe (Playwright): 0 error konsol/pageerror, 0 overflow di semua layar. Belum pernah dicek: mode "Bingkai ponsel", pembaca layar asli, kontras AA dengan alat ukur, Clerk asli, Neon asli, HF Space/Netlify asli.
Catat setiap hal yang tidak teruji di `HANDOFF.md`. Bila menemukan celah desain, perbaiki di `docs/design/malas-ui.html` juga supaya acuan tetap sinkron.

## 12. Fase berikutnya (setelah web jalan): Fase 5
Dockerfile HF Space (port 7860, env `PORT`; `SPACE_HOST` sudah otomatis diizinkan oleh backend), `netlify.toml` (build `pnpm --filter web build`, publish `apps/web/dist`,
redirect `/api/*` -> `https://<space>.hf.space/api/:splat` status 200 force, fallback SPA `/* /index.html 200`), GitHub Actions (pytest SQLite + service Postgres, ruff terbatas, typecheck + build web, cek tipe OpenAPI),
`S3Storage` untuk R2, update `DEPLOY.md`. Perlu diverifikasi nyata: header Host yang diteruskan proxy Netlify ke HF (TrustedHost), cookie/`Authorization` melewati proxy, dan HF Space harus publik atau memakai token akses.

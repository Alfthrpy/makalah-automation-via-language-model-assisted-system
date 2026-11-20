# Checklist peluncuran MALAS

Status per 2026-11-20. Centang setelah **dibuktikan**, bukan setelah dikonfigurasi. Panduan setup layanan: `DEPLOY.md`.

## Deploy terakhir (2026-11-20)
- Backend (Space): commit `d76661cb` (logo kustom + retensi 48 jam; migrasi 0003 terbukti jalan di Neon: tabel `user_logos` ada). **Titik kembali** bila bermasalah: commit Space `29b5f2d4` (tab *Files* → History → revert, atau deploy ulang dari git commit lama).
- Web (Netlify): deploy `6affeb22`.

## Yang sudah live
- Web: <https://malas-app.netlify.app> (Netlify, situs `malas-app`, id `f4f7ee2f-f459-4ce8-b20b-910fbb04b45b`; di-deploy lewat API, tidak terhubung git).
- Backend: Hugging Face Space `PetaniHandal/stegano-f5-dmcss-api` (nama lama dari proyek sebelumnya; isinya MALAS), Docker, RUNNING.
- Database: Neon project `malas` (`still-lab-16179546`), branch `production`.
- Login: Clerk instance dev `moral-camel-3719` (`https://moral-camel-3719.clerk.accounts.dev`).

## A. Wajib sebelum dibuka ke publik
- [ ] **Tes alur lengkap di HP**: daftar → verifikasi → masuk → buat makalah **Mode uji** → unduh `.docx`. (Belum ada yang membuktikan Clerk + proxy Netlify + backend + Neon nyambung ujung ke ujung.)
- [ ] **Satu makalah sungguhan** dengan API key sendiri (key khusus, kredit kecil). Periksa: outline masuk akal, sitasi cocok dengan sumber, waktu 10-30 menit, dan catat token/biaya dari halaman job. Klaim di landing dan video bergantung pada ini.
- [ ] **Isi `CLERK_AUTHORIZED_PARTIES`** di Space = `https://malas-app.netlify.app` (persis, tanpa garis miring akhir), **setelah** login terbukti jalan. Jika setelahnya semua `/api/*` 401, hapus variabelnya (artinya klaim `azp` tidak cocok) dan kirim `azp` dari token.
- [ ] **Setelan Clerk** (Dashboard, nama menu bisa berbeda): wajibkan verifikasi email; batasi metode masuk yang diinginkan; biarkan bot protection aktif; isi URL Ketentuan (`/ketentuan`) dan Privasi (`/privasi`) di pengaturan *Legal* bila tersedia.
- [ ] **Tinjau Ketentuan dan Privasi** (`apps/web/src/features/legal/content.ts`). Ini draf yang ditulis dari perilaku sistem, **bukan nasihat hukum**. Cek: identitas pengelola ("perorangan, proyek pribadi"), kontak (kini GitHub issues; ganti `CONTACT_URL` bila punya email), retensi 48 jam, logo tersimpan sampai dihapus pengguna, daftar pihak penerima data. Bila ada pertanyaan hukum (mis. UU PDP), minta tinjauan ahli.
- [ ] **Cabut token yang sempat bocor/tersimpan**: token HF lama (tertempel di chat), serta token HF, Neon, dan Netlify yang disimpan di environment sesi Claude (`makalah-malas`) bila tidak dipakai lagi. Password database Neon sudah direset sekali; jangan tempel connection string ke chat lagi.
- [ ] **Link di bio**: video marketing menulis "Link di bio"; pasang `malas-app.netlify.app` di bio akun sebelum unggah.

## B. Disarankan
- [ ] **Template di repo masih memuat logo institusi tertentu** (`packages/engine/src/malas/templates/*.docx`, `word/media/image1.png`). Layanan web sudah memakai penanda netral atau logo pengguna, tapi berkas template di repo (publik) masih membawanya. Ganti dengan gambar netral bila bukan milikmu atau tanpa izin.
- [ ] **Rename Space** jadi mis. `PetaniHandal/malas-api`. Dampak: host berubah (`petanihandal-malas-api.hf.space`) → edit `netlify.toml` (redirect `/api/*`), deploy ulang web, ubah `HF_SPACE` di GitHub (variable) bila memakai workflow.
- [ ] **`MALAS_SECRET_KEY`** di Space bila ingin fitur "simpan API key" (acak ≥ 32 karakter, simpan di password manager; jika hilang/ganti, key tersimpan tak terbaca). Tanpa ini fitur mati dan teks privasi tetap benar.
- [ ] **Domain sendiri**: ubah `og:url`/`og:image` di `apps/web/index.html`, `public/robots.txt`, `public/sitemap.xml`, `netlify.toml` (bila perlu), `CLERK_AUTHORIZED_PARTIES`, dan domain di Clerk.
- [ ] **Pemantauan**: belum ada. Minimal: cek tab *Logs* Space setelah rilis; pertimbangkan Sentry (butuh DSN dan penyaringan agar body/key tidak terkirim) dan analitik ramah privasi (jika ditambah, perbarui Kebijakan Privasi: kini tertulis "tanpa pelacak pihak ketiga").
- [ ] **Cek ulang batas free tier** Neon, Hugging Face, Netlify, Clerk sebelum promosi besar-besaran (job 10-30 menit di Space gratis bisa terputus saat restart).

## C. Operasional
- **Deploy web ulang** (tanpa git-link): build lalu `NETLIFY_AUTH_TOKEN=... python3 deploy/netlify/deploy.py --site f4f7ee2f-f459-4ce8-b20b-910fbb04b45b`.
  ```bash
  VITE_AUTH_MODE=clerk VITE_CLERK_PUBLISHABLE_KEY=pk_test_bW9yYWwtY2FtZWwtMzcxOS5jbGVyay5hY2NvdW50cy5kZXYk pnpm --filter web build
  ```
  (Publishable key Clerk bersifat publik.) Alternatif: hubungkan situs ke GitHub di Netlify agar otomatis deploy dari `main` (build/env sudah di `netlify.toml`).
- **Deploy backend ulang**: workflow `deploy-hf.yml` (butuh secret `HF_TOKEN` dan variable `HF_SPACE`) atau `HF_TOKEN=... uv run --no-project --with huggingface_hub python deploy/hf-space/push.py PetaniHandal/stegano-f5-dmcss-api` (satu commit; riwayat lama aman).
- **Rollback web**: Netlify → Deploys → pilih deploy lama → *Publish deploy*. **Rollback backend**: tab *Files* → History di Space, atau deploy ulang dari commit lama.
- **Gejala umum**: lihat tabel *Troubleshooting* di `DEPLOY.md`.

## D. Ide pertumbuhan (setelah A selesai)
Contoh keluaran nyata (dengan label) di landing, notifikasi email saat job selesai, halaman "Tentang"/FAQ lebih lengkap, domain sendiri. Video promo ada di `marketing/video/v4/` (musik dan SFX orisinal).

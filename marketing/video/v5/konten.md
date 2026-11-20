# MALAS promo v5: "Referensi yang bisa kamu cek"

Video: `malas-promo-v5.mp4` (30,0 dtk, 9:16, 1080x1920, 30 fps, musik + SFX sintesis orisinal). Bangun ulang: `bash marketing/video/v5/build.sh`.

**Konsep.** Satu pertanyaan yang memang ada di kepala mahasiswa ("daftar pustaka dari AI, beneran ada?") dijawab dengan transparansi, bukan janji: referensi diambil dari database, ada DOI yang bisa kamu buka, ada angka uji internal, dan hasilnya tetap DRAF. Berbeda dari v4 (alur 3 langkah: 14 tab -> ketik judul -> .docx -> DRAF). Fokus v5 ada pada fitur yang baru live, yaitu pencarian referensi, dengan tanggung jawab tetap di tangan pengguna.

---

## (i) Naskah / storyboard per detik

Tempo musik 96 BPM (1 ketukan = 0,625 dtk), kunci D mayor. Semua waktu di bawah diambil dari `events.json`.

| Waktu (dtk) | Layar | Teks di layar | Audio |
|---|---|---|---|
| 0,00-0,63 | Halaman "DAFTAR PUSTAKA" dengan judul kabur dan `doi: ???` | **Daftar pustaka / dari AI… / beneran ada?** (hook langsung terbaca sejak bingkai 0) | pad + bas + arpeggio tipis |
| 0,63 | "beneran ada?" menghantam (skala) | | *thud* |
| 1,25 / 1,56 / 1,88 | Tanda tanya merah muncul di tiap `doi: ???` | | 3x *plop* |
| 3,75 | Pindah adegan | **Dari jurnal / sungguhan.** + "Datanya diambil dari database, bukan dikarang AI." | *whoosh*, beat ringan masuk |
| 3,9-8,7 | Potongan tangkapan layar ASLI tahap "Outline & referensi" (label **Tampilan contoh**) | | *swipe* halus (memindai) |
| 5,63 / 6,25 / 6,88 | 3 kartu hasil: judul + lencana DOI, Abstrak, PDF terbuka / B. Indonesia | | 3x *pop* |
| 8,75 | Halaman DAFTAR PUSTAKA format APA dengan DOI contoh `10.0000/contoh…` (label **Tampilan contoh**) | **Buka DOI-nya. / Cek sendiri.** | *whoosh*, beat penuh |
| 10,00 | Stabilo kuning menyapu DOI pertama | | *swipe* |
| 10,94 | Jari mengetuk DOI, halaman artikel naik | | *click* |
| 11,88 / 12,34 / 12,81 | Centang muncul: Judul, Penulis, Tahun | | 3x *tick* |
| 13,28 | | | *ding* |
| 15,00 | Uji internal | **Uji internal: / 8 topik.** | *whoosh* |
| 15,47-16,56 | 8 chip topik: Hukum, Tafsir, Fisioterapi, Akuntansi syariah, Sejarah, K-pop, Machine learning, Pajak | | 8 nada *blip* naik (pentatonik) |
| 16,88 / 17,50 / 18,13 | Tiga baris angka | **32/32** sub-bab dapat ≥2 referensi berabstrak; **±97%** punya PDF open-access yang diketahui; **±78%** teks lengkapnya berhasil diambil | 3x *pop* |
| 18,3-20,0 | | "Hasil uji internal, bukan jaminan. Jurnal berbahasa Indonesia ikut tercakup." | |
| 20,00 | Latar biru | **Tetap DRAF.** | *whoosh*, musik melunak |
| 20,47 | "DRAF." dicap | "Baca & cocokkan dengan sumbernya. Sitasi bisa keliru." / "Aturan AI kampus & dosenmu tetap tanggung jawabmu." | *stamp* |
| 24,38 | End card | Tombol **Coba gratis →**, "Mode uji gratis, tanpa API key", "Mode uji = teks & referensi contoh. Referensi nyata: pakai API key-mu.", **Link di bio**, `malas-app.netlify.app` | *whoosh*, beat penuh |
| 27,19 | | | nada A4 |
| 27,50 | Tombol ditekan (riak) | | *press* + nada D5, akor Dmaj9 mendarat |
| 29,50-30,00 | Hook masuk lagi (loop mulus) | | musik melingkar ke awal |

Zona aman: semua teks berada di y 270-1500 px dan x 84-1000 px (lihat `contact-sheet-safezone.png`: atas 250 px, bawah 380 px, kanan 120 px).

---

## (ii) Caption siap posting

**TikTok**
> Pernah dapet daftar pustaka dari AI terus bingung: ini beneran ada nggak sih?
> Di MALAS, referensi draf makalahmu diambil dari database jurnal, lengkap dengan DOI/tautan. Jadi kamu bisa buka dan cek sendiri: judul, penulis, tahun.
> Hasilnya tetap DRAF ya. Baca, cocokkan sama sumbernya, edit. Sitasi bisa keliru, dan aturan AI di kampus/dosenmu tetap kamu yang pegang.
> Mode uji gratis tanpa API key (isinya teks & referensi contoh). Link di bio.

**Instagram Reels**
> "Referensinya dari mana?" Pertanyaan dosen yang paling bikin deg-degan.
>
> MALAS sekarang nyari referensi dari database jurnal sungguhan, termasuk jurnal berbahasa Indonesia. Tiap referensi punya DOI atau tautan yang bisa kamu buka dan cek sendiri.
>
> Di uji internal kami (8 topik lintas bidang), semua sub-bab dapat minimal 2 referensi berabstrak. Itu hasil uji, bukan jaminan.
>
> Yang kamu dapat adalah DRAF .docx: tetap dibaca, dicocokkan, dan diedit. Ikuti aturan AI kampus & dosenmu.
>
> Coba gratis lewat Mode uji (tanpa API key, isinya contoh). Untuk referensi nyata, pakai API key-mu sendiri. Link di bio: malas-app.netlify.app

**X / Twitter**
> Daftar pustaka dari AI, beneran ada?
> Di MALAS, referensinya diambil dari database jurnal dan ada DOI/tautan yang bisa kamu klik & cek sendiri. Hasilnya tetap draf: baca, cocokkan, edit.
> Mode uji gratis tanpa API key (isi contoh): malas-app.netlify.app

---

## (iii) Hashtag (13)

#MALAS #makalah #tugaskuliah #mahasiswa #mahasiswaindonesia #skripsi #daftarpustaka #sitasiAPA #DOI #referensi #jurnalilmiah #tipskuliah #literasiakademik

(Hindari tagar yang menyiratkan "anti-plagiarisme", "lolos deteksi AI", atau "nilai A".)

---

## (iv) Tiga ide konten untuk minggu berikutnya

**1. "Cara cek DOI dalam 20 detik" (tutorial layar, 20-30 dtk, tanpa promosi berat)**
- Hook: "Referensi di makalahmu beneran ada? Cek pakai ini."
- Langkah 1: salin DOI dari daftar pustaka (contoh generik, label "Tampilan contoh").
- Langkah 2: tempel ke `https://doi.org/` di peramban.
- Langkah 3: cocokkan judul, penulis, tahun, nama jurnal. Kalau tidak terbuka atau tidak cocok, jangan dipakai.
- Penutup: "Di MALAS, DOI-nya sudah ada di daftar pustaka. Tetap kamu yang cek." + Link di bio.

**2. "Sitasi APA 7: 4 kesalahan yang sering bikin revisi" (carousel 6 slide atau video 30 dtk)**
- Slide 1: hook "Revisi gara-gara daftar pustaka? Cek 4 hal ini."
- Kesalahan 1: tahun di teks dan di daftar pustaka beda.
- Kesalahan 2: penulis lebih dari 2 tapi tidak ditulis "dkk."/"et al." di sitasi dalam teks.
- Kesalahan 3: judul artikel pakai Huruf Besar Semua Kata (APA 7 pakai sentence case).
- Kesalahan 4: sitasi di teks tidak ada di daftar pustaka, atau sebaliknya.
- Penutup: "MALAS bantu susun draf sitasi APA, tapi baca ulang tetap wajib." (Contoh nama: generik, mis. "Penulis, A.")

**3. "Draf itu titik mulai, bukan titik akhir" (talking-head / teks, 25-35 dtk, nada hangat)**
- Hook: "Pakai AI buat makalah itu boleh nggak sih?"
- Isi: tergantung aturan kampus dan dosenmu. Tanyakan dulu, baca silabus.
- Kalau boleh: jadikan draf sebagai kerangka, lalu tulis ulang dengan kata-katamu, tambah analisis sendiri, cek setiap sitasi.
- Checklist singkat di layar: aturan dosen ✓, baca semua bab ✓, cocokkan sumber ✓, tulis ulang bagian penting ✓.
- Penutup: "Mode uji gratis buat lihat bentuk drafnya dulu. Link di bio." (Tanpa klaim lolos deteksi, tanpa jaminan nilai.)

---

## (v) Klaim yang dipakai dan buktinya (untuk audit)

| Klaim (video/caption) | Bukti di repo | Catatan |
|---|---|---|
| Referensi dicari dari database jurnal sungguhan; fitur sudah live | `HANDOFF.md` §2b ("Live di Space sejak commit Space `b02dad45`", `MALAS_REFSEARCH=1`); `docs/refsearch.md` bagian "Alur" | Jalur ini aktif lewat variabel Space. Bila variabel dihapus (rollback), klaim ini tidak berlaku lagi |
| "Datanya diambil dari database, bukan dikarang AI" (judul, penulis, tahun, DOI) | `docs/refsearch.md`: "LLM tidak pernah menulis judul/penulis/tahun/DOI: semuanya berasal dari respons API." | Isi paragraf tetap ditulis LLM, dan sitasi di dalam teks bisa keliru (disebut di video) |
| Ada DOI/tautan yang bisa dibuka | `packages/engine/src/malas/refsearch/orchestrator.py` (`link = c.url or https://doi.org/{doi}`); `docx_converter.py` `format_apa7` menaruh link di akhir entri | Video memakai kalimat ajakan "Buka DOI-nya", bukan "selalu ada DOI": referensi cadangan (Wikipedia/Open Library) bisa tanpa DOI. Link ditulis sebagai teks di .docx; bisa disalin atau diklik bila penampil dokumen mengenalinya sebagai tautan |
| Format daftar pustaka "Penulis. (Tahun). Judul. tautan" | `packages/engine/src/malas/docx_converter.py` (`format_apa7`) | Layar video meniru format ini dengan data generik |
| Uji internal 8 topik (hukum, tafsir, fisioterapi, akuntansi syariah, sejarah, K-pop, ML, pajak) | `docs/refsearch.md` bagian "Hasil uji NYATA" (GitHub Actions 2026-11-20; workflow di commit `b3d7aea`) | Disebut sebagai "uji internal, bukan jaminan" |
| 32/32 sub-bab dapat ≥2 referensi berabstrak | sama: "32/32 sub-bab mendapat >=2 referensi, abstrak 100%" | |
| ±97% punya PDF open-access yang diketahui | sama: "PDF open-access diketahui 97%" | |
| ±78% teks lengkap berhasil diambil | sama: "full-text berhasil 78%" | |
| Jurnal berbahasa Indonesia ikut tercakup | `docs/refsearch.md` keterbatasan ("topik teknis tanpa query Inggris hanya mendapat jurnal berbahasa Indonesia"); provider DOAJ dipilih untuk topik Indonesia (bagian "Alur") | |
| Hasil = DRAF, sitasi bisa keliru, aturan AI kampus/dosen = tanggung jawab pengguna | `HANDOFF.md` §9 | Wajib ada; tampil 20,0-24,4 dtk |
| Mode uji gratis, tanpa API key; isinya teks & referensi contoh | `HANDOFF.md` §1; `packages/engine/src/malas/refsearch/providers.py` (`Fixture`: Mode uji memakai referensi fixture tanpa jaringan, DOI `10.0000/fixture…`) | Karena itu end card menyebut "Referensi nyata: pakai API key-mu" |
| Tangkapan layar tahap "Outline & referensi" | `assets/ui-job-jalan.png` (tangkapan layar asli Mode uji, disalin dari v4) | Berlabel "Tampilan contoh" |
| Daftar pustaka, kartu hasil, halaman artikel DOI | dibangun di `index.html`, data generik ("Penulis, A.", DOI `10.0000/contoh…`, prefiks tidak terdaftar) | Berlabel "Tampilan contoh"; bukan referensi nyata |

**Tidak dipakai, dengan sengaja:** nama database pihak ketiga (merek lain), estimasi waktu "10-30 menit" (belum diukur dengan key nyata, lihat `HANDOFF.md` §3), klaim relevansi sempurna (`docs/refsearch.md`: topik Majapahit masih memuat 1 artikel Sriwijaya), testimoni, urgensi, dan klaim soal deteksi AI/plagiarisme.

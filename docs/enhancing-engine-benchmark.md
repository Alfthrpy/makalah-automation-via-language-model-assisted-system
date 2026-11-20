# Enhancing Engine: hasil benchmark terhadap analisis (`docs/enhancing-engine.md`)

Tanggal: 2026-11-20. Cabang `claude/epic-einstein-gthev3`. Tujuan: menguji apakah analisis (temuan F01-F31, akar masalah RC-xx, dan perkiraan token) **benar**, setelah semua WP diimplementasikan.

## Batas yang harus dibaca dulu
- **Tidak ada LLM produksi** yang terjangkau dari sandbox (OpenRouter dan Gemini diblokir; Crossref juga diblokir proxy; OpenAlex terjangkau). Jadi yang diuji: bagian deterministik, panggilan jaringan nyata ke OpenAlex, ukuran prompt nyata dari alur asli (mode mock), dan **sampel penulis dari model haiku** (bukan model produksi) untuk menguji mekanisme.
- Sampel LLM kecil (n=2 per sel), model berbeda dari produksi: hasilnya **ilustrasi mekanisme, bukan bukti statistik**.
- Makalah uji = satu makalah (n=1). Skrip: `packages/engine/scripts/{paper_to_makalah,bench_prompts,bench_refsearch}.py`; PDF dan identitas penyusun tidak di repo.
- Biaya dalam rupiah/dolar **tidak** diukur (bergantung harga penyedia). Token keluaran penulis tidak diukur (mock).

## Ringkasan: apa yang terbukti, sebagian, dan tidak

| Klaim analisis | Hasil | Bukti |
|---|---|---|
| RC-01/RC-02: nama "Raseena P M" jadi "M", verifier buta, referensi terhapus senyap (F01) | **Terbukti** | direproduksi dengan fungsi repo + tes regresi; lint CIT-001 menangkap 4 sitasi "M dkk." pada makalah nyata |
| RC-03: penulis kekurangan konteks; Kesimpulan menulis tanpa konteks | **Terbukti pada prompt nyata** | prompt 3.1 dari alur asli berisi `subab sebelumnya :` KOSONG (kode lama); prompt baru berisi RM + ringkasan Bab II |
| RC-03 dampak pada jawaban RM | **Terindikasi** (n kecil) | TRC-001 (RM tanpa jejak di Kesimpulan): kode lama 2 dan 2 temuan; prompt baru 1 dan 0 |
| RC-05: bias referensi ke jurnal Indonesia, tanpa karya dasar | **Terbukti pada jalur tanpa LLM**; penyebab rinci tak terpisahkan | baseline 6 judul: 100% referensi berbahasa Indonesia, 0 landmark; sesudah: 58-83%, landmark 0→2 (5 dari 6 judul). Perubahan `indo` dan query Inggris dilakukan bersamaan, jadi kontribusi masing-masing tidak terukur |
| Karya teori yang diharapkan (Ryan & Deci 2000, Deterding 2011) akan muncul | **Tidak terbukti** | tetap tidak muncul untuk judul gamifikasi |
| RC-09: Daftar Isi kosong, Bab III tak pindah halaman, tanda tangan tanpa nama | **Terbukti** pada template; **diperbaiki** | XML template dibongkar; render v3 dicek visual (LibreOffice) |
| RC-09(d): salah ketik "Latar Bekalang" | **Koreksi**: analisis awal keliru | teks PDF uji memang memuat "Latar Bekalang" (saya salah membaca visual); lint LNG-001 menangkapnya |
| RC-04: penulis overclaim karena tak tahu desain studi | **Tidak tereproduksi** dengan haiku | kata kausal: kode lama 0 dan 0; prompt baru 0 dan 1. Model produksi (murah) mungkin berbeda; belum teruji |
| RC-13: subjek melenceng ("mahasiswa") karena `mata_kuliah` | **Tidak tereproduksi** | 0 kemunculan "mahasiswa" pada 8 sampel (kedua kondisi). Namun lint TRC-002 + kartu dari abstrak nyata **mendeteksi** drift pada teks asli (2 temuan) |
| Perkiraan token: baseline ±3,4k masukan/sub-bab | **Cocok** | terukur 3,17k rata-rata (28,5k total untuk 9 sub-bab) |
| Perkiraan token: tier lite −13% | **Tidak cocok** | terukur **−4%** (28,5k → 27,3k). Sub-bab 2.1 dan 3.1 justru naik karena sekarang diberi konteks |
| Perkiraan token: kartu bukti hemat prompt penulis | **Arah benar, besar lebih kecil** | deep −12% total vs off (25,1k); −8% vs lite |
| Asumsi crewAI: guardrail menerima `output.pydantic` | **Salah** | pada pemanggilan pertama `pydantic` = None (konversi menyusul); guardrail kini membaca `raw` |
| crewAI 1.15 berjalan tanpa litellm | **Terbukti** untuk 315 tes + alur mock; **belum** untuk panggilan LLM nyata | spike dan `uv.lock` baru |

## 1. Lint pada makalah nyata (0 token)
Teks PDF → `paper_to_makalah.py` → `run_lints`. Hasil: **35 temuan** (4 blocker, 10 major, 17 minor, 4 info); setelah perbaikan otomatis skor berbobot 79 → 55.

| F | Temuan analisis | Terdeteksi? | Aturan |
|---|---|---|---|
| F01 | sitasi "M dkk." | **ya** (blocker ×4) | CIT-001 |
| F02 | RM-3 tak dijawab | **tidak** (false negative: kata "prinsip/rancang" ada di Kesimpulan) | TRC-001 |
| F03 | "mahasiswa" vs bukti siswa | **ya**, bila kartu bukti ada (heuristik dari abstrak nyata, 0 LLM) | TRC-002 |
| F06-F08 | klaim melebihi desain | **sebagian**: "terbukti" pada SLR/desain tak-diketahui (3, severity info karena kartu dari abstrak berkepercayaan rendah); η²=0,113 dan "berhasil mengatasi" tak tertangkap | CLM-001 |
| F11 | tanpa sisi kritis | **sebagian** (2 dari 5 sub-bab Bab II) | CLM-002 |
| F12 | klaim Bab I tanpa sitasi | ya (9 dari 15 kalimat) | CLM-003 |
| F16, F17 | tanpa Metode/Manfaat/Saran/Keterbatasan | ya (4) | STR-003 |
| F20 | referensi dangkal/Indonesia | ya (78% berjudul Indonesia) | REF-003 |
| F21 | "2.1 2.1" | ya (5) | STR-001 |
| F22 | daftar RM/Tujuan bernomor 1-5 | ya (4) | STR-002 |
| F26 | tembok paragraf | sebagian (1 sub-bab, 9 paragraf) | STR-004 |
| F27 | angka diulang | ya (2) | RED-001 |
| F28-F30 | APA tak lengkap/KAPITAL/tak alfabet | ya | REF-001/002 |
| F31 | "di gamifikasi" | ya | LNG-001 |
| F09, F10, F13-F15, F18, F19, F25 | atribusi Wordwall, studi sekunder, konten Arab, tabel, kurikulum, melebar, halaman kosong | **tidak** (butuh LLM/kritik atau di luar jangkauan lint) | — |

Temuan sampingan: aturan **REF-003, LNG-001 "mempengaruhi" (info)** dan **CLM-003** terasa berisik; ambang belum dikalibrasi pada lebih dari satu makalah.

## 2. Retrieval (OpenAlex nyata, tanpa LLM, 6 judul)
Sumber: `bench_refsearch_baseline.json` vs `bench_refsearch_after.json`. Hanya OpenAlex yang menjawab (Crossref dan DOAJ gagal di proxy sandbox).

| Judul | ID% sebelum | ID% sesudah | landmark sebelum → sesudah |
|---|---|---|---|
| Gamifikasi bahasa Arab | 100 | 75 | 0 → 2 |
| Media sosial & kesehatan mental | 100 | 83 | 0 → 2 |
| Hukum pidana korupsi Indonesia | 100 | 83 | 0 → 2 |
| Machine learning deteksi penipuan | 100 | 58 | 0 → 2 |
| Pemasaran digital UMKM syariah | 100 | 75 | 0 → 2 |
| Majapahit | 100 | 58 | 0 → 0 |

Catatan: rencana tanpa LLM kini membawa query Inggris kasar dari glosarium (±100 entri, dikerjakan agen yang terhenti limit; perlu ditinjau); produksi memakai rencana LLM yang bisa berbeda.

## 3. Ukuran prompt penulis (alur asli, mode mock, 9 sub-bab nyata)
Token ≈ karakter/4 (tokenizer asli tidak tersedia offline).

| Tier | Total masukan | Rata-rata/sub-bab |
|---|---|---|
| off (perilaku lama) | 28.498 | 3.166 |
| lite (ContextPack) | 27.338 (−4%) | 3.038 |
| deep (+ kartu bukti) | 25.091 (−12%) | 2.788 |

Per sub-bab: 1.2 −26%, 2.3 −16%, 2.5 −15% (lite); **2.1 +31%, 3.1 +54%** (sengaja: sebelumnya nyaris tanpa konteks). Blueprint, kritik, tambal, dan dukungan-sumber **tidak** diukur di sini (butuh LLM); di mode mock, blueprint = 441 token masukan dan 12 kartu = 3,3k token masukan pada referensi fixture.

## 4. Sampel penulis (haiku, n=2 per sel, sub-bab Kesimpulan dan Analisis Dampak)
Kondisi A = prompt lama (`tasks.yaml` commit sebelum perubahan, tier off). Kondisi B = prompt baru (tier deep: ContextPack, kartu, aturan 8-9). Dievaluasi dengan lint.

| Metrik | A (lama) | B (baru) |
|---|---|---|
| Kesimpulan: temuan TRC-001 (RM tanpa jejak) | 2, 2 | 1, 0 |
| "mahasiswa" muncul | 0 dari 4 | 0 dari 4 |
| Kata kausal ("membuktikan", ...) di Dampak | 0, 0 | 0, 1 |
| Kalimat keterbatasan di Dampak | 3, 4 | 1, 2 |

Kesimpulan: mekanisme **RM terjawab** membaik; klaim **overclaim** dan **drift populasi** tak muncul pada model ini, jadi penyebabnya di makalah uji mungkin spesifik model produksi atau tidak terjadi lewat jalur ini. Jangan menyimpulkan prompt baru "lebih kritis": sampel menunjukkan sedikit lebih sedikit kalimat keterbatasan (hitungan regex kasar).

## 5. Yang belum bisa dibuktikan (perlu kunci LLM)
Presisi kritik (S18) dan tingkat penerimaan tambalan (S19); Δtoken tier standard/deep sesungguhnya (+65%/+100% adalah perkiraan, belum terukur); biaya rupiah; kualitas blueprint dan kartu bukti LLM; panggilan Gemini/OpenRouter/Kenari di crewAI 1.15; Crossref; kinerja di HF Space. Harness untuk ini ada: jalankan `uv run kickoff` dengan `MALAS_ENHANCE=off|lite|standard|deep` pada judul uji dan bandingkan `stats.usage_by_stage` dan `stats.quality`.

# Enhancing Engine: analisis kekurangan, akar masalah, dan rancangan solusi

> Status: **rancangan** (belum ada kode enhancing). Dasar: review satu makalah hasil MALAS (topik gamifikasi pembelajaran
> Bahasa Arab, 24 halaman) + pembacaan kode di commit `e561dfd` + pembacaan source crewAI **1.15.44** (rilis PyPI 2026-11-19).
> Dokumen ini ditulis untuk **agent coder/planner**: setiap temuan, akar masalah, dan solusi punya ID tetap, berkas yang
> disentuh, kriteria selesai, dan dampak token. Bahasa: Indonesia; identifier kode: Inggris/Indonesia seperti di repo.

## 0. Cara memakai dokumen ini (baca dulu)

1. **Urutan baca cepat**: §1 (ringkasan) → §4 (akar masalah) → §7 (katalog solusi) → §9 (roadmap PR). §2-§3 hanya konteks.
2. **ID** (stabil, boleh dirujuk di commit/PR): `F01..F31` temuan, `RC-01..RC-16` akar masalah, `S01..S24` solusi,
   `WP-0..WP-8` paket kerja (satu WP = satu PR), `<KELAS>-<NNN>` ID aturan lint (§6.3).
3. **Tanda bukti** pada klaim: **[V]** = sudah direproduksi dengan kode/ukuran nyata di sesi analisis, **[K]** = terbaca
   langsung dari kode (tidak dijalankan), **[H]** = hipotesis, perlu diukur. Jangan memperlakukan [H] sebagai fakta.
4. **Aturan emas biaya**: urutan kerja selalu *deterministik gratis → perbaikan di hulu (cegah) → LLM terarah (obati)*.
   Setiap solusi mencantumkan `Δtoken` terhadap baseline (§8). Solusi LLM harus punya batas anggaran dan jalur mati (env).
5. **Jangan melanggar** `HANDOFF.md` §9 (keamanan key, kejujuran produk, teks hukum, ruff pada berkas baru di `ci.yml`).
   Tambahan khusus enhancing: (a) teks pengguna **tidak** ke cache bersama; cache lintas-pengguna hanya untuk data publik
   dengan kunci DOI/hash (§6.4); (b) hasil tetap **draf**, laporan kualitas tidak boleh berbunyi "lolos/aman/terjamin".
6. **Mode uji (`MALAS_MOCK=1`) harus tetap jalan**. `AutoFakeLLM` mensyaratkan `task.output_pydantic`
   (`mock/mock_llm.py`) dan **mem-parse teks prompt penulis** dengan regex `bab : … dengan subab` dan
   `subab : … menyesuaikan` (`mock_llm.py: parse_context_from_description`). Mengubah kata-kata prompt penulis di
   `write_format_crew/config/tasks.yaml` bisa mematahkan mode uji: ubah bersama regex/tes. Panggilan LLM baru di luar
   crew wajib punya cabang `is_mock()` (contoh: `main.py:_search_refs`).
7. Tes: `uv run pytest`. (Di sesi analisis, 90 tes engine lulus pada crewAI 1.15.44; baseline lama 0.201.1 tidak dijalankan ulang.) Semua kode baru wajib punya tes tanpa jaringan/LLM.

---

## 1. Ringkasan eksekutif

Makalah uji **sumbernya nyata** (9 DOI terverifikasi ke OpenAlex) dan prosanya rapi, tetapi gagal di tiga hal:

| # | Masalah | Dari mana | Seberapa mahal memperbaikinya |
|---|---|---|---|
| 1 | **Sitasi rusak diam-diam** ("M dkk., 2026" tidak ada di daftar pustaka) | Bug nama penulis + verifier buta + `prune` menghapus referensi | **0 token**, 1 PR kecil (WP-1) |
| 2 | **Janji makalah tak dipenuhi** (RM-3, kesimpulan, kerangka konseptual); subjek melenceng; angka diulang 3× | Penulis tak pernah melihat Bab I/RM/outline; Kesimpulan menulis **tanpa konteks apa pun** | Token-**negatif** bila konteks diganti ringkasan (WP-3) |
| 3 | **Klaim melebihi bukti**, tanpa sisi kritis, referensi dangkal & bias Indonesia | Penulis hanya melihat abstrak + ≤3000 karakter, tak tahu desain studi; heuristik `indo=True` untuk hampir semua judul Indonesia; k=2/sub-bab | Kartu bukti + gerbang klaim (WP-6/7), biaya sedang |

Sisanya (Daftar Isi kosong, penomoran ganda, daftar RM rusak, format APA tak lengkap, tak ada Saran/Metode) adalah cacat
**template/konverter deterministik**, bisa dibereskan tanpa LLM (WP-1, WP-2).

**Rekomendasi inti**: bangun Enhancing Engine sebagai **tangga bertingkat** (Lite → Standard → Deep, §6.5); jangan mulai dari
"agen reviewer yang menulis ulang semuanya" (mahal, sulit diuji, dan menyalin kesalahan hulu). Mulai dari lint deterministik
+ perbaikan konteks penulis; baru tambahkan satu panggilan kritik dan penambalan terarah. Naikkan crewAI ke 1.15.x
(spike lulus, §5.4) **sebelum** WP-7 karena guardrail/`response_model` mengurangi kode retry buatan sendiri dan melepas
`litellm` dari jalur kunci BYOK.

---

## 2. Bukti & metode

| Sumber | Cara |
|---|---|
| Makalah hasil | Dibaca 24 halaman (cover → daftar pustaka). Identitas penyusun **sengaja tidak dicantumkan** di dokumen ini. |
| Referensi | 9 DOI di daftar pustaka dicek ke `api.openalex.org`: semua terselesaikan dengan judul/penulis/tahun sama; metadata `biblio` (volume, issue, halaman) tersedia untuk semuanya. Satu sumber yang disitir tetapi hilang dari daftar ("M dkk., 2026") dicocokkan ke OpenAlex: kandidat kuat *Raseena P M, Maya C, dkk. (2026), "Gamification of Teaching and Learning: A Conceptual Framework for Deep Engagement"* (DOI `10.36948/ijfmr.2026.v08i04.86022`); **[H]** — dicocokkan dari judul/topik, isinya belum dibaca. |
| Kode | `main.py`, `citations.py`, `docx_converter.py`, `tolerant.py`, `refsearch/*`, `crews/*`, template `.docx` (diurai XML). |
| Template | `template makalah.docx` dibongkar: tidak ada field TOC, 3 page-break (sebelum Daftar Isi, Bab II, Daftar Pustaka), gaya `Judul2` berpenomoran otomatis (`numId=2`), teks harfiah "Latar Bekalang" **[V]**. |
| crewAI | Wheel `crewai==1.15.44` diunduh dan dibaca (situs docs diblokir proxy sesi); ditambah pencarian web untuk insiden litellm. |
| Spike | venv terpisah: `crewai[tools]==1.15.44` **tanpa litellm** → 90 tes engine lulus + alur mock penuh menghasilkan `.docx` (§5.4). |

Batas analisis: satu makalah (n=1) dan satu domain. Pola yang **struktural** (terbaca dari kode) dianggap berlaku umum;
pola yang bergantung isi (mis. bias bahasa Indonesia) harus dikonfirmasi di set uji ±10 judul (WP-0).

---

## 3. Pipeline sekarang (peta untuk agent)

```
inputDataMakalah            main.py:136
  └ generate_outline        main.py:150   OutlineCrew (1 LLM) [+ refsearch: rencana query 1 LLM + HTTP]  -> Bab, daftar_pustaka
      └ fetch_fulltexts     main.py:307   HTTP saja (PDF OA -> teks -> BM25 chunk), tanpa LLM
          └ fill_subbab_content  main.py:322   1 crew-call per sub-bab, SEKUENSIAL, konteks = sub-bab SEBELUMNYA saja (main.py:341-348)
              └ verify_citations  main.py:368   regex sitasi vs daftar pustaka; crew "citation_editor" 1x per sub-bab bermasalah; prune referensi
                  └ write_kata_pengantar  main.py:413
                      └ finalize_and_save  main.py:432   DocxConverter(docxtpl) + logo
```

Komponen kunci:

| Komponen | Berkas | Catatan relevan untuk enhancing |
|---|---|---|
| State | `crews/models/TaskOutput.py` | `Makalah.bab: Dict[str, Bab]`; `SubBab.content: List[ContentText\|ContentList]` (**tak ada tabel/gambar**, RC-16) |
| Penulis | `crews/write_format_crew/*` | 1 agen, **bertool DuckDuckGo** (`write_format_crew.py:50`), `output_pydantic=SubBab`, `TolerantConverter`; task review **dikomentari** |
| Parser toleran | `tolerant.py` | Perapihan lokal JSON/prosa → pydantic, tanpa LLM; **pertahankan** |
| Referensi | `refsearch/{plan,providers,orchestrator,rank}.py` | deterministik; `k=2`/sub-bab (`orchestrator.py:81`); LLM hanya menyusun query + opsional rerank |
| Sitasi | `citations.py` | regex APA; `prune_unused_references` (`:156`) |
| Konversi | `docx_converter.py` | `normalize_for_template` (`:70`), `_as_list` (`:39`), `format_apa7` (`:84`), urutan referensi = urutan temu |
| Checkpoint | `checkpoint.py` | JSON `Makalah`+usage+stats, `VERSION=1`; **field baru pada `Makalah` harus opsional** agar checkpoint lama tetap valid |
| Tahap UI | `steps.py` | tahap baru harus ditambah di sini (UI web mengikutinya) |
| Peran model | `config.py` | `planner`, `writer`, `reviewer` (BYOK: `reviewer`=model penulis; UI hanya dua kolom model) |

---

## 4. Temuan → akar masalah

### 4.1 Peta temuan (F01-F31 = nomor butir pada review sebelumnya)

Kolom *Tanpa LLM?*: apakah **terdeteksi** otomatis tanpa token (D = deterministik penuh, P = sebagian, L = perlu LLM).

| ID | Temuan (ringkas) | Akar | Solusi | Tanpa LLM? |
|---|---|---|---|---|
| F01 | Sitasi "M dkk., 2026" tak ada di Daftar Pustaka (±10× dipakai) | RC-01, RC-02 | S01, S02 | D |
| F02 | RM-3 & Tujuan-3 (prinsip/kerangka integrasi) tak dijawab | RC-03, RC-11 | S08, S11, S18 | P |
| F03 | Bukti siswa MTs/SDIT, kesimpulan bicara "mahasiswa" | RC-13, RC-03 | S08, S10 | P |
| F04 | Daftar Isi kosong | RC-09 | S06 | D |
| F05 | Logo masih "LOGO" | RC-09 (by design) | S06 (peringatan) | D |
| F06 | η²=0,113 dibahasakan "nyata/signifikan" berlebih | RC-04 | S15, S16 | P |
| F07 | Pre-post tanpa kontrol (Laiya) dibaca kausal; skor hasil belajar dipakai untuk klaim motivasi | RC-04 | S15, S16 | P |
| F08 | Studi kualitatif ditulis "berhasil mengatasi" | RC-04 | S15, S16 | P |
| F09 | Wordwall salah diatribusikan ke Utami di Kesimpulan | RC-03 | S08, S20 | P |
| F10 | "Studi yang dikutip dalam tinjauan" tanpa sumber primer | RC-04, RC-12 | S15 | L |
| F11 | Tanpa sisi kritis (overjustification, novelty, leaderboard, perspektif Islam) | RC-04, RC-14 | S11, S18 | P |
| F12 | Klaim masalah di Bab I tanpa sitasi | RC-04 | S07 (CLM-003) | D |
| F13 | Nol konten khas Bahasa Arab (mufradat, nahwu, maharah) | RC-14 | S11 (domain checklist) | L |
| F14 | Teori primer (Deterding, Ryan & Deci…) tak ada | RC-05 | S14 | D (deteksi: rasio landmark) |
| F15 | Tanpa tabel/gambar | RC-16 | S13 | D |
| F16 | Bab I tanpa metode/manfaat/ruang lingkup | RC-06 | S12, S06 | D |
| F17 | Tanpa Saran/keterbatasan | RC-06 | S12 | D |
| F18 | Kurikulum Bahasa Arab madrasah (CP, KMA 183) tak dibahas | RC-14 | S11 | L |
| F19 | Sub-bab 2.5 melebar ke pendidikan karakter | RC-03, RC-14 | S11, S18 | L |
| F20 | Hanya 9 referensi, 8 jurnal Indonesia | RC-05 | S14 | D |
| F21 | Judul "2.1 2.1 …" | RC-08 | S04 | D |
| F22 | Daftar RM/Tujuan bernomor 1-5 (pengantar & penjelasan ikut jadi butir) | RC-07 | S05 | D |
| F23 | Hlm. iii hanya "Yogyakarta…/Penulis" tanpa nama | RC-09 | S06 | D |
| F24 | BAB III tidak mulai halaman baru | RC-09 | S06 | D |
| F25 | Halaman nyaris kosong (4, 18, 20) | RC-09 (akibat page-break + ekor) | S06 | P |
| F26 | Tembok paragraf, tanpa sub-judul | RC-16, RC-12 | S13, S11 | P |
| F27 | Statistik/daftar platform diulang 3× | RC-03 | S08 (ledger), S07 (RED-001) | D |
| F28 | APA 7 tak lengkap (tanpa jurnal/volume/halaman/italik) | RC-10 | S03 | D |
| F29 | Judul huruf kapital semua | RC-10 | S03 | D |
| F30 | Pustaka tak berurut alfabet | RC-10 | S03 | D |
| F31 | Typo/kalimat janggal ("di gamifikasi") | RC-12, RC-11 | S07 (LNG-001), S18 | P |

### 4.2 Akar masalah

#### RC-01 Penguraian nama penulis mengambil token terakhir **[V]**
`citations.py:_surname` (`:33`), `_surname_display` (`:92`) dan `docx_converter.format_apa7` (`:84`) semuanya memakai
`author.split()[-1]`. OpenAlex mengembalikan `display_name` apa adanya (mis. `"Raseena P M"`), sehingga nama keluarga terbaca
`"M"`. Crossref sebenarnya memberi `family`/`given` terpisah, tetapi `refsearch/providers.py:118` menggabungnya jadi satu string
sehingga informasi hilang.
*Reproduksi* (sudah dijalankan): `citation_label(ReferenceItem(authors=["Raseena P M","Maya C",…], year=2026))` → `"(M dkk., 2026)"`;
`_ref_keys` → `{('m',2026), ('c',2026), ('kattikulangara',2026)}`.
*Akibat*: label sitasi yang disalin penulis dari field `sitasi` salah dari awal, dan APA di daftar pustaka juga salah.

#### RC-02 Verifier buta terhadap sitasi yang tak terurai, lalu menghapus referensinya **[V]**
Regex nama `_NAMA = [A-ZÀ-Ý][\w'’\-]+` (`citations.py:16`) mensyaratkan **minimal 2 huruf**. `(M dkk., 2026)` dan `M dkk. (2026)`
lolos `_PAREN` tetapi gagal di `_ITEM`/`_NARASI` **tanpa laporan**. Akibatnya: (a) tidak masuk `invalid` (tidak ada alarm),
(b) referensi `M` tidak masuk `used_refs`, (c) `prune_unused_references` (`:156`) membuangnya karena "tidak dikutip".
*Reproduksi*: sitasi `(M dkk., 2026)` ×2 + `(Utami, 2024)` → `extracted=['(Utami, 2024)','Utami (2024)']`, `invalid={}`,
`pruned=1`. **Persis gejala di makalah uji**: kutipan ada di teks, entri tidak ada di Daftar Pustaka, `stats.citations_invalid_after=0`
(laporan "bersih" padahal rusak). Ini kelas bug paling berbahaya: *kegagalan senyap yang tampak sukses*.

#### RC-03 Kelaparan konteks pada penulis **[K]**
`main.py:341-348`: konteks hanya `bab.subbab[i-1]` **jika `i>0`** di bab yang sama. Konsekuensi:
- **2.1 tidak melihat Bab I** (termasuk RM) dan **3.1 Kesimpulan tidak melihat apa pun** (Bab III hanya 1 sub-bab → `i=0`).
- Tak ada outline lengkap, RM, daftar klaim yang sudah dipakai, atau definisi populasi.
- `_references_for` (`:254`): sub-bab tanpa referensi sendiri (1.2, 1.3, 3.1) menerima `semua[:3]`, yaitu **3 referensi pertama
  daftar**, bukan ringkasan apa yang dikatakan tiap sumber → mudah mencampur atribusi (F09) dan mengulang angka (F27).
*Akibat*: RM tak dijawab (F02), kesimpulan melenceng (F03, F09), pengulangan (F27), melebar (F19).

#### RC-04 Kelaparan bukti & bias optimistis **[K]**
Penulis menerima per sub-bab: abstrak ≤900 karakter per referensi (`orchestrator.py`: `abstract[:900]`) + kutipan full-text
**total ≤ `MALAS_FULLTEXT_CHARS`=3000 karakter** dibagi rata ke semua referensi sub-bab (`main.py:265`). Abstrak cenderung
memuat hasil positif; desain studi (kontrol? n? instrumen?), batasan, dan angka kecil jarang masuk. Prompt penulis
(`tasks.yaml`) melarang menambah klaim di luar kutipan, tetapi **tidak** meminta: bahasa terkalibrasi menurut desain studi,
satu sisi-kritis per sub-bab, atau pembedaan hasil belajar vs motivasi. Hasilnya: "terbukti", "berhasil mengatasi" (F06-F08).

#### RC-05 Bias pencarian referensi **[K]**
- `plan.py:15,25`: `indo = len(_ID_HINT.findall(judul)) >= 1` dan `_ID_HINT` memuat kata sambung `dan|yang|di|untuk|pada|dalam|…`.
  Hampir **semua judul berbahasa Indonesia** memicu `indo=True` (judul uji: "…**untuk** Meningkatkan…"). Efek: sumber/bahasa Indonesia
  ditambahkan (`providers_for`) dan `rank.py:158` memberi **+0,3** prior untuk `language=="id"`. Dugaan kuat penyebab 8/9 referensi Indonesia **[H]**
  (LLM-plan dapat menimpa dengan `indo` boolean, tetapi tak dijamin).
- `k=2` per sub-bab dan hanya Bab 1.1 + Bab II (`main.py:215`) → total referensi 9-15.
- Tak ada pass "landmark" (karya dasar). `rank.py` memberi bobot `cited_by` maksimal 0,3×0,2 — kecil; karya klasik 50k kutipan
  tak diuntungkan relatif terhadap jurnal lokal yang kata kuncinya pas.

#### RC-06 Outline terkunci pada indeks template **[K]**
`tasks.yaml` memaksa Bab I tepat 3 sub-bab dan Bab III tepat 1 ("HANYA"); `main.py:196` membatasi 5 bab; template memakai
`bab.I.subbab[0..2]` dan `bab.III.subbab[0]` (indeks tetap). Karena itu Metode, Manfaat, Ruang Lingkup, Saran, Keterbatasan
**tak mungkin** muncul.

#### RC-07 Perataan tipe konten merusak daftar **[V]**
`docx_converter._as_list` (`:39`) memecah **semua baris** teks jadi butir. Teks RM dari LLM biasanya: kalimat pengantar +
butir + paragraf penjelasan → ketiganya jadi butir (diuji: 4 butir dari 1 pengantar + 2 pertanyaan + 1 penjelasan) = F22.
Prompt penulis tidak memberi format khusus untuk 1.2/1.3.

#### RC-08 Tabrakan penomoran judul **[V]**
Prompt outline mewajibkan judul `"2.1 Judul"`, sedangkan gaya `Judul2` di template memakai penomoran otomatis Word (`numId=2`) →
dicetak "2.1 2.1 Judul". Judul bernomor juga dipakai sebagai kunci (`refsearch`, `ReferenceItem.sections`, checkpoint), jadi
**jangan** menghapus nomor dari state; hapus di konverter saja.

#### RC-09 Cacat template **[V]**
Diurai dari XML: (a) `DAFTAR ISI` hanya judul + bookmark `_Toc…`, **tanpa field TOC** → kosong; (b) page-break hanya sebelum Daftar Isi,
Bab II, Daftar Pustaka → Bab III menempel; (c) blok "Penulis" tanpa nama dan tanpa `keepNext` → terlempar ke halaman sendiri;
(d) teks harfiah "Latar Bekalang" di repo (PDF uji tidak memuatnya → kemungkinan diedit manual/template lain; **perbaiki di template**);
(e) logo "LOGO" = perilaku sengaja layanan web (`HANDOFF` §5 #10) tetapi pengguna tidak diberi tahu.

#### RC-10 Pemformat pustaka minimal **[K]**
`format_apa7` hanya `Penulis. (Tahun). Judul. Tautan`: tanpa nama jurnal, volume(issue), halaman, italik, sentence case, urutan
alfabet; `ReferenceItem` hanya punya `venue`, tidak ada volume/issue/halaman walau OpenAlex memberinya (**[V]**: `biblio` ada untuk 9/9 DOI) dan
Crossref (`volume,issue,page`) juga.

#### RC-11 Tak ada QA semantik pasca-tulis **[K]**
Satu-satunya pemeriksaan: eksistensi sitasi. Tak ada cek: klaim vs desain, RM terjawab, pengulangan, struktur, kelengkapan bagian.
Agen `quality_reviewer` dan `review_content_task` ada di YAML/Python tetapi **dikomentari** (dan prompt-nya masih merujuk konteks Jinja2 lama).

#### RC-12 Penulis sekali-jalan bertool, tanpa kerangka argumen **[K]**
Satu panggilan per sub-bab; tak ada "tugas argumen" per sub-bab. `DuckDuckGoSearchTool` terpasang dan prompt memerintahkannya bila
`excerpt` kosong → loop ReAct (tiap iterasi mengirim ulang seluruh konteks; biaya **[H]** perlu diukur) dan permukaan untuk
sitasi di luar daftar. Dengan `MALAS_REFSEARCH=1` + full-text, tool ini tak diperlukan.

#### RC-13 Input tak memuat lingkup **[K]**
Field input: judul, mata kuliah, dosen, dll. Tak ada *jenis makalah* (kajian pustaka vs penelitian), *subjek/jenjang*, atau
*bahasa sasaran*. `mata_kuliah` disuntik di tiap prompt → kecenderungan "mahasiswa PAI" di bagian yang tak punya bukti populasi itu (F03) **[H]**.
Bab I juga memakai istilah "penelitian ini" padahal makalah kajian pustaka (konsistensi jenis dokumen).

#### RC-14 Tak ada checklist domain/analisis **[K]**
Tak ada langkah yang menurunkan dari judul+mata kuliah: istilah wajib, contoh konkret, sudut pandang kritis, kerangka kurikulum
relevan. Penulis hanya "menyusun narasi dari excerpt" sehingga isi domain (F13, F18) bergantung kebetulan isi abstrak.

#### RC-15 Utang teknis platform **[K + sumber]**
`engine/pyproject.toml`: `crewai[tools]>=0.193.2,<1.0.0` (terkunci 0.201.1); crewAI terbaru **1.15.44**. Pin `<1.0` berarti
tak ada perbaikan keamanan/fitur 1.x. `litellm` ada di jalur kunci BYOK (`config.get_llm`, prefix `gemini/`, `openrouter/`, `openai/`).
Maret 2026 `litellm` di PyPI diserang rantai-pasok (rilis berbahaya 1.82.7/1.82.8 mencuri kredensial; PyPI mengarantina;
crewAI terdampak secara transitif). `uv.lock` repo di 1.74.9 (sebelum insiden) sehingga **tidak terdampak**, tetapi tiap
`uv lock --upgrade` di masa depan membawa risiko; aplikasi ini memegang API key pengguna. Logika retry/perbaikan buatan sendiri
(`_write_subbab`, `run_citation_fix`) menduplikasi fitur guardrail crewAI.

#### RC-16 Model konten tak mengenal tabel/sub-judul **[K]**
`ContentItem = ContentText | ContentList`. Tak ada tabel sintesis studi, tak ada sub-judul (3.2.1) (dan outline melarangnya).
Template menaruh list Bab II sebagai `a) b) c)`.

---

## 5. Landasan crewAI sekarang

### 5.1 Versi
Repo: `0.201.1` (`uv.lock`). PyPI terbaru: **1.15.44** (2026-11-19), `requires-python >=3.10,<3.14`. Baris 1.15.x dirilis hampir harian.

### 5.2 Fakta dari source 1.15.44 yang mengubah desain
| Fakta (diverifikasi dari kode wheel) | Implikasi |
|---|---|
| `litellm` kini **extra opsional** (`crewai[litellm]`, pin `>=1.105.3,<1.105.4`). Provider native: `openai, anthropic, claude, azure, azure_openai, google, gemini, bedrock, aws, openrouter, deepseek, ollama, ollama_chat, hosted_vllm, cerebras, dashscope, snowflake, deepinfra` (`llm.py:201`). Model tak cocok → jatuh ke litellm, dan **raise `ImportError`** bila litellm tak terpasang. | BYOK (OpenRouter, Kenari) bisa berjalan **tanpa litellm**. Hilangkan litellm dari dependensi default. |
| Routing uji (`LLM(...)`, tanpa litellm): `openrouter/<m>` → `providers/openai_compatible` (base `https://openrouter.ai/api/v1`); `openai/<m>` + `base_url="https://kenari.id/v1"` → provider `openai` native (base_url dihormati). **`gemini/<m>` gagal** kecuali `crewai[google-genai]` terpasang. | Tambah extra `google-genai` bila Gemini dipertahankan sebagai default `.env` (`DEFAULT_MODEL`). |
| `Task.guardrails=[fn\|str]`, `guardrail=`; fungsi `(TaskOutput\|LiteAgentOutput) -> (bool, Any)`; `guardrail_max_retries` default **3**; string → `LLMGuardrail` (LLM agen). Umpan balik gagal dikirim ke agen yang sama untuk diulang. **Saat retry habis crewAI `raise Exception(...)`** (`task.py:1562`). `Task.max_retries` deprecated. | Pakai guardrail deterministik menggantikan crew `citation_fix`; **wajib soft-fail** (lihat §7 S17) agar job tak mati. |
| `Task.response_model` = keluaran terstruktur **native provider** (terpisah dari `output_pydantic`+`converter_cls`). | Pakai bila provider native; **pertahankan `TolerantConverter`** untuk model gratis/non-native (Kenari `:free`). Keduanya masih ada (`converter_cls` di `task.py:265`; `crewai.utilities.converter.Converter/ConverterError` masih ada). |
| `Agent.kickoff(messages, response_format=…)` = agen mandiri tanpa Crew/Task, mengembalikan `LiteAgentOutput`. `LLM.call` langsung juga ada (dipakai `refsearch`). | Untuk panggilan tunggal (kartu bukti, kritik, blueprint) pakai **`LLM.call` + parser tolerant**/`response_format`, bukan Crew penuh: lebih sedikit overhead prompt scaffolding. |
| `HallucinationGuardrail` di OSS adalah **placeholder no-op** (`tasks/hallucination_guardrail.py`). | **Jangan** mengandalkannya; verifikasi dukungan-sumber dibangun sendiri (S20). |
| Flow: `@start/@listen/@router`, `or_/and_`, state pydantic, `@persist` (SQLite bawaan), `@human_feedback` (butuh ≥1.8.0 per docs). `Agent.kickoff(from_checkpoint=…)` ada. | **Jangan migrasi checkpoint** ke `@persist`: `checkpoint.py` sudah jalan, ada UI resume, dan menyimpan state tanpa key. `@router` berguna untuk loop audit→tambal. `@human_feedback`: tahap lanjut (persetujuan tambalan di UI). |
| `Crew.kickoff_for_each`, `kickoff_async`, `akickoff*` ada. | Paralelisme untuk kartu bukti (waktu, bukan token); tetap hormati `max_rpm`/kuota BYOK. |
| Provider Anthropic native menstempel `cache_control` otomatis (`llms/providers/anthropic/completion.py`); Azure mendukung `prompt_cache_key`. Caching implisit Gemini/OpenAI bergantung **awalan prompt yang stabil**. | Susun prompt: bagian statis (aturan, blueprint, rubrik) **di depan**, bagian dinamis (referensi sub-bab) di belakang. Nol kode, potensi hemat input berulang **[H]** (ukur `usage`). |
| Telemetry: `CREWAI_TRACING_ENABLED=false` tetap dihormati. | Pertahankan override di `config.py`/`main.py`. |

### 5.3 Yang **sengaja tidak** dipakai
`Memory`/`Knowledge`/RAG bawaan (butuh embedding+vektor DB; BM25 kita sudah cukup dan gratis), `@persist` (lihat atas),
`@human_feedback` (UI belum ada; fase lanjut), `HallucinationGuardrail` (no-op), agen "reviewer" otonom bertool (mahal, tak deterministik).

### 5.4 Hasil spike kompatibilitas (dijalankan di sesi analisis)
venv baru, `crewai[tools]==1.15.44` + dependensi engine, **tanpa litellm**:
- `pytest packages/engine/tests` → **90 passed**.
- `MALAS_MOCK=1 MALAS_REFSEARCH=1 python -m malas.main` → alur 7 tahap selesai, `.docx` terbentuk.
- `langchain-community` **masih dibutuhkan** (`tools/custom_tool.py`), tidak ikut ter-install otomatis oleh `crewai[tools]`.
- **Belum teruji**: panggilan LLM sungguhan (Gemini native, OpenRouter, Kenari), `apps/api/tests`, perilaku `AutoFakeLLM` pada jalur guardrail,
  dan kinerja/RAM di HF Space. Itu tugas WP-8.

---

## 6. Rancangan Enhancing Engine

### 6.1 Prinsip
1. **Cegah > obati.** Memperbaiki konteks penulis (S08-S11) lebih murah daripada menulis ulang sub-bab (S19) — satu penulisan ulang ≈ biaya satu sub-bab awal.
2. **Deterministik dulu.** Aturan yang bisa dihitung (sitasi, struktur, pengulangan, leksikon klaim) berjalan tanpa token dan tanpa LLM; LLM hanya untuk yang butuh pemahaman.
3. **LLM tidak menulis fakta sumber.** Pola `refsearch`: LLM memilih/menilai ID; metadata dan angka berasal dari API/teks sumber.
4. **Monoton.** Tambalan hanya diterima bila jumlah temuan (berbobot) **turun** dan tidak ada temuan `blocker` baru; selain itu teks asli dipertahankan.
5. **Berbatas biaya.** Setiap tahap punya anggaran token; melewati anggaran = lewati tahap, tulis di laporan (bukan gagal).
6. **Idempoten & dapat dilanjutkan.** State baru disimpan di checkpoint; tambalan tersimpan per sub-bab.
7. **Jujur.** Laporan menyebut temuan dan keterbatasan pemeriksa, tidak menyatakan "bebas masalah".

### 6.2 Lapisan

```
 L0  Lint deterministik (0 token)          malas/enhance/lint/*      -> Finding[]
 L1  Konteks & kerangka (hulu, murah)      Blueprint + ContextPack   -> dipakai penulis
 L2  Kartu bukti per referensi (LLM murah, cache DOI)  EvidenceCard   -> dipakai penulis + lint
 L3  Kritik terarah (1 panggilan LLM)      critic.py                 -> Finding[] (rule_id, lokasi, instruksi)
 L4  Tambal terarah + verifikasi ulang     patch.py                  -> SubBab baru bila L0 membaik
```
Mode eksekusi: **(a) di dalam flow** (disarankan; state terstruktur ada) sebagai tahap `enhance` setelah `verify_citations` dan sebelum
`write_kata_pengantar`; **(b) mandiri** dari checkpoint/`Makalah` JSON (`python -m malas.enhance --lint <checkpoint.json>`) untuk uji dan CI.
Mengimpor `.docx` pengguna → `Makalah` (best-effort) ditunda (WP lanjut; di luar cakupan).

### 6.3 Model data (usulan; letakkan di `malas/enhance/models.py`)

```python
class Location(BaseModel):
    bab: str | None = None            # "II"
    subbab: str | None = None         # judul apa adanya (kunci stabil, termasuk nomor)
    paragraph: int | None = None      # indeks item konten

class Finding(BaseModel):
    rule_id: str                      # "CIT-001"
    severity: Literal["blocker", "major", "minor", "info"]
    where: Location = Location()
    message: str                      # Indonesia, ≤200 karakter, tanpa klaim absolut
    evidence: str = ""                # kutipan ≤200 karakter dari teks
    fix: Literal["auto", "patch", "human", "none"] = "none"
    hint: str = ""                    # instruksi singkat untuk penambal LLM
    source: Literal["lint", "critic", "verifier"] = "lint"

class EvidenceCard(BaseModel):        # per referensi; kunci cache = doi atau hash judul+tahun
    ref_key: str
    design: Literal["rct", "kuasi_eksperimen", "pre_post", "survei", "kualitatif",
                    "slr", "konseptual", "pengembangan_rnd", "lainnya", "tak_diketahui"]
    has_control: bool | None = None
    n: int | None = None
    population: str = ""              # "siswa MTs", "mahasiswa", ...
    outcome: Literal["motivasi", "hasil_belajar", "persepsi", "lainnya", "tak_diketahui"] = "tak_diketahui"
    key_result: str = ""              # angka VERBATIM dari sumber (mis. "F(1,67)=8,52; p=0,005")
    limitations: str = ""
    causal_ok: bool = False           # True hanya bila desain mendukung klaim kausal (rct/kuasi dgn kontrol)
    confidence: Literal["rendah", "sedang", "tinggi"] = "rendah"
    basis: Literal["abstrak", "fulltext"] = "abstrak"

class Blueprint(BaseModel):           # 1 panggilan planner; disimpan di Makalah.blueprint (opsional)
    scope: Scope                      # jenis_makalah, subjek, jenjang
    research_questions: list[str]     # ≤3, kalimat tanya utuh
    rq_map: dict[str, list[str]]      # RM -> judul sub-bab yang menjawab
    subbab_tasks: dict[str, str]      # judul sub-bab -> tugas argumen 1-2 kalimat
    domain_checklist: list[str]       # 3-6 istilah/contoh wajib (mis. mufradat, nahwu, maharah)
    avoid_repeat: list[str] = []      # klaim/angka yang dialokasikan ke satu sub-bab saja

class ContextPack(BaseModel):         # dibangun KODE (bukan LLM) per sub-bab saat menulis
    outline_titles: list[str]
    rq: list[str]
    ledger: list[str]                 # ringkasan ekstraktif kalimat/angka yang SUDAH dipakai (≤250 token)
    digest_bab2: list[str]            # hanya untuk Kesimpulan: 2 kalimat/sub-bab Bab II
```
Field baru pada `Makalah` semuanya **opsional** (`blueprint`, `evidence`, `quality: list[Finding]`) agar `checkpoint.load` lama tetap valid
(`Makalah.model_validate`). Naikkan `checkpoint.VERSION` hanya bila bentuk field lama berubah.

### 6.4 Katalog aturan lint (L0) — `malas/enhance/lint/`
Tiap aturan: fungsi murni `(Makalah, ctx) -> list[Finding]`, terdaftar di registri, satu berkas tes. Prefix: CIT sitasi, REF pustaka,
STR struktur, RED pengulangan, CLM klaim, TRC keterlacakan, LNG bahasa, DOM domain, TPL template.

| ID | Memeriksa | Metode | Sev | Fix |
|---|---|---|---|---|
| CIT-001 | Sitasi-mirip yang **tak terurai** (suspect) atau tak ada di pustaka | `_PAREN` cocok tetapi `_ITEM` gagal; atau kunci tak ada | blocker | auto/patch |
| CIT-002 | Referensi yang akan di-prune (nama judulnya dilaporkan) | selisih used/unused | info | none |
| CIT-003 | Atribusi: nama+tahun di kalimat vs `sections`/kartu | kunci sitasi ∈ referensi sub-bab itu? | major | patch |
| REF-001 | Entri APA tak lengkap (tanpa venue/volume/halaman bila tersedia di metadata) | cek field | minor | auto |
| REF-002 | Tak berurut alfabet / judul KAPITAL | urut & rasio huruf besar | minor | auto |
| REF-003 | Rasio referensi berbahasa Indonesia > 60% padahal `indo=False`; tak ada landmark (cited_by≥300) di sub-bab konsep | statistik refs | major | refsearch |
| STR-001 | Penomoran ganda (`2.1 2.1`) | `^\d+(\.\d+)+\s` pada judul yang dicetak | minor | auto |
| STR-002 | Daftar RM/Tujuan: butir bukan kalimat tanya/tujuan, butir pengantar/penutup | pola | major | auto |
| STR-003 | Bagian wajib menurut profil tak ada (Metode, Manfaat, Saran, Keterbatasan) | judul sub-bab | major | outline |
| STR-004 | Sub-bab Bab II > N paragraf tanpa sub-judul/tabel | hitung | minor | none |
| RED-001 | Fakta numerik berulang antar sub-bab (`F\(\d+,\s*\d+\)\s*=\s*[\d,.]+`, `p\s*=\s*0[,.]\d+`, `η²`, persen, n) | sidik jari angka | major | patch |
| RED-002 | Paragraf nyaris sama (Jaccard 5-gram > 0,6) antar sub-bab | shingling | major | patch |
| CLM-001 | Kata kausal/penguat (`membuktikan\|terbukti\|menyebabkan\|berhasil mengatasi\|jelas menunjukkan\|secara signifikan meningkatkan`) pada kalimat yang menyitir referensi dengan `causal_ok=False` | leksikon × kartu | major | patch |
| CLM-002 | Sub-bab Bab II tanpa kalimat keterbatasan/kontra (`namun\|keterbatasan\|tidak semua\|perlu kehati-hatian\|…`) | leksikon | minor | patch |
| CLM-003 | Rasio kalimat faktual tanpa sitasi di Bab I.1/II > ambang | kalimat bergaya klaim tanpa `(…, tahun)` | minor | patch |
| CLM-004 | Klaim motivasi disitir ke kartu `outcome=hasil_belajar` | kartu | major | patch |
| TRC-001 | Setiap RM punya jejak leksikal di Kesimpulan (BM25 RM↔paragraf; ambang) | BM25 | major | patch |
| TRC-002 | Kata populasi di Kesimpulan (siswa/mahasiswa/guru…) tak ada di `Blueprint.scope` ∪ populasi kartu | set | major | patch |
| TRC-003 | Tujuan ↔ RM: jumlah sama dan kata kunci tumpang-tindih | pola | minor | none |
| LNG-001 | Daftar typo/kalimat janggal terkurasi (`\bdi\s+(gamifikasi\|digitalisasi)\w*`→`di-…`/`digamifikasi`, "penelitian ini" dalam profil kajian pustaka, "mengkaji" konsisten) | regex terkurasi, **kecil & bertes** | minor | auto |
| DOM-001 | Cakupan `domain_checklist` (≥ 60% istilah muncul) | token | major | patch |
| TPL-001 | Template: ada field TOC; page-break sebelum Bab III; tak ada teks salah ketik; blok tanda tangan memuat nama | parse XML `.docx` template | blocker | human |

Catatan: ambang awal ditetapkan konservatif dan **dikalibrasi di WP-0** terhadap set uji; aturan `severity` yang kerap *false positive* turun jadi `info`.

### 6.5 Tingkat (tier) — satu env `MALAS_ENHANCE=off|lite|standard|deep`

| Tier | Isi | Δtoken vs baseline* | Kelas model |
|---|---|---|---|
| `off` | perilaku sekarang | 0 | — |
| `lite` (default setelah WP-3) | L0 lint + perbaikan otomatis + ContextPack + hapus tool penulis | **≈ −13%** | — (tanpa LLM baru) |
| `standard` | lite + Blueprint + Kritik (1 panggilan) + tambal ≤3 sub-bab | **≈ +65%** | planner (murah) untuk blueprint/kritik; writer untuk tambal |
| `deep` | standard + Kartu Bukti + cek dukungan-sumber | **≈ +100%** | + planner untuk kartu |

\* Perkiraan dari ukuran prompt (§8); **harus diukur** di WP-0 dengan `stats.usage`. Batas keras: `MALAS_ENHANCE_MAX_TOKENS` (default 40k).

---

## 7. Katalog solusi

Format kartu: **Menyelesaikan** · **P**rioritas (P0 wajib, P1 tinggi, P2 sedang) · **U**saha (S ≤½ hari, M 1-2 hari, L >2 hari) ·
**Δtoken** (per makalah; negatif = hemat) · **Berkas** · **Perubahan** · **Selesai bila** (tes) · **Risiko**.

### Gelombang A — integritas (deterministik, 0 token)

#### S01 Normalisasi nama penulis di batas provider
- **Menyelesaikan** F01, sebagian F28 · **P0 · S · Δ0**
- **Berkas** baru `refsearch/names.py`; ubah `refsearch/providers.py` (OpenAlex `:84`, Crossref `:118`, tiap provider), `citations.py:_surname/_surname_display`, `docx_converter.format_apa7`.
- **Perubahan**
  - `normalize_author(raw) -> "Family, G. G."` (bentuk koma, yang **sudah** didukung hilir). Aturan: sudah ada koma → pertahankan; lembaga (`is_institution`) → utuh; token **di belakang** berupa 1-2 huruf kapital (`P`, `M`, `PM`, `J.`) = inisial → keluarga = token pertama (`"Raseena P M"` → `"Raseena, P. M."`); selain itu keluarga = token terakhir.
  - Crossref: simpan `"{family}, {given}"` (jangan gabung), ini sumber paling andal. Tambah `name_confidence` ("tinggi" Crossref/koma, "rendah" heuristik) di `Candidate`/`ReferenceItem` (opsional).
  - `_surname*`/`format_apa7` dialihkan ke satu fungsi bersama (hapus 3 salinan `split()[-1]`).
- **Selesai bila** tes: `"Raseena P M"`→label `(Raseena dkk., 2026)`; `"Maya C"`→`Maya, C.`; `"Syihabuddin Syihabuddin"` tak menghasilkan inisial ganda; nama Arab/Indonesia satu kata tetap; lembaga utuh; tak ada label berupa satu huruf. **Catatan jujur**: urutan nama India/ber-inisial di belakang ambigu; tanpa data Crossref/ORCID benar-tidaknya bergantung heuristik → tandai `name_confidence=rendah`, jangan klaim pasti.
- **Risiko** sitasi lama di checkpoint memakai label lama → verifier harus kebal (S02 menangani).

#### S02 Verifier tidak boleh buta, prune tidak boleh senyap
- **Menyelesaikan** F01 · **P0 · S · Δ0**
- **Berkas** `citations.py`, `main.py:verify_citations (:368-410)`, `apps/api` (skema stats bila ditampilkan).
- **Perubahan**
  1. Terima nama ≥1 huruf **hanya** untuk jalur parenthetical (`(M dkk., 2026)`) atau, lebih aman, tambah ember **`suspect`**: setiap isi kurung bertahun yang cocok `_PAREN` tetapi gagal `_ITEM`/`_NARASI` dicatat (bukan dibuang). Hindari melonggarkan `_NARASI` global (risiko "Gambar A (2024)").
  2. `CitationReport.suspect: Dict[judul, List[str]]`; `stats.citations_suspect`.
  3. `prune_unused_references`: **jangan prune** bila ada `suspect` ATAU `invalid`; selalu kembalikan daftar judul yang dibuang → `stats.refs_pruned_titles` (info CIT-002).
  4. Kesimpulan verifikasi: bila `suspect`/`invalid` masih ada setelah perbaikan → tampilkan peringatan nyata di hasil (bukan "bersih").
- **Selesai bila** tes: reproduksi §4.2 RC-02 (`(M dkk., 2026)` ×2) menghasilkan `suspect` tidak kosong dan **tidak** ada prune; kasus "semua sitasi cocok" tidak berubah; tes lama `test_citations.py` hijau.
- **Risiko** false positive pada kurung non-sitasi ("(lihat Tabel 2, 2024)") → hanya laporkan bila kurung berisi pola `Nama[ dkk.| &…], tahun` sebelum koma; selain itu abaikan.

#### S03 Pemformat APA 7 v2
- **Menyelesaikan** F28-F30 · **P1 · M · Δ0**
- **Berkas** `crews/models/TaskOutput.py` (`ReferenceItem` + `volume, issue, pages`), `refsearch/providers.py` (OpenAlex `SELECT` += `biblio`; Crossref `volume,issue,page`), `refsearch/models.py`, `docx_converter.py`, template (`{{r …}}` untuk RichText).
- **Perubahan**
  - Target keluaran (contoh nyata, metadata dari OpenAlex): `Utami, R. (2024). Gamifikasi dalam pembelajaran bahasa Arab di lembaga pendidikan Indonesia. *Nun: Journal of Arabic Studies, 4*(2), 36–52. https://doi.org/10.56633/nun.v4i2.1634` (nama jurnal dan volume italik; DOI sebagai URL).
  - `to_sentence_case(title, protected)`: hanya bila judul ≥60% KAPITAL atau Title-Case ≥70% kata≥4 huruf; pertahankan huruf awal, setelah titik dua, akronim (≤5 huruf kapital), dan **kata berkapital di tengah kalimat pada abstrak/venue/judul makalah** (sinyal nama diri, mis. "Arab", "Indonesia", "Islam"). Tanpa LLM.
  - Urut alfabet (nama keluarga penulis pertama, lalu tahun); tanpa penulis → judul menggantikan posisi penulis (APA).
  - Italik via `docxtpl.RichText`; fallback teks polos bila field kosong (data lama).
- **Selesai bila** tes golden untuk 3 referensi di atas + kasus tanpa volume, tanpa penulis, judul KAPITAL; `ReferenceItem` lama (tanpa field baru) tetap bisa dirender.
- **Risiko** sentence-case salah pada nama diri → daftar `protected` dari sinyal data + tes; selalu bisa dimatikan (`MALAS_APA_SENTENCECASE=0`).

#### S04 Cabut nomor ganda di judul
- **Menyelesaikan** F21 · **P0 · S · Δ0** · **Berkas** `docx_converter.py` (`_generate_context`).
- Hapus awalan `^\s*\d+(\.\d+)*[.)]?\s+` dari `sub.judul` **hanya di konteks render** (gunakan `refsearch.plan.strip_number`). State/checkpoint/`sections` tak diubah (RC-08).
- **Selesai bila** tes render: judul "2.1 Konsep" tercetak sekali; Bab I (teks harfiah di template) tak terpengaruh.

#### S05 Normalisasi daftar RM/Tujuan
- **Menyelesaikan** F22 · **P0 · S · Δ0** · **Berkas** `docx_converter._as_list`, `write_format_crew/config/tasks.yaml` (tambahan aturan format 1.2/1.3).
- `_as_list` hanya mengambil baris **bermarker** (`1)`, `a.`, `-`) bila ada ≥2 baris bermarker; baris tanpa marker sebelum butir pertama (pengantar) dan sesudah butir terakhir (penjelasan) **dibuang dari daftar** (pengantar boleh dipindah jadi paragraf pembuka bila template mendukung, lihat S06). Bila tak ada marker, perilaku lama.
- Prompt: untuk "Rumusan Masalah"/"Tujuan" → "keluarkan **hanya butir**, tanpa kalimat pengantar/penjelasan; jumlah butir RM = jumlah butir Tujuan". (Hati-hati regex mock, §0 poin 6.)
- **Selesai bila** tes: input pengantar+2 pertanyaan+penjelasan → 2 butir; input tanpa marker → perilaku lama.

#### S06 Template v3 + peringatan
- **Menyelesaikan** F04, F05, F16/F17 (prasyarat), F23, F24, F25 · **P1 · M · Δ0** · **Berkas** `templates/*.docx`, `docx_converter.py`, `logo.py`, `steps.py`/stats.
- Edit di Word/LibreOffice (bukan skrip), satu template baru `template makalah v3.docx`, lama dipertahankan sebagai cadangan:
  1. **Daftar Isi**: field `TOC \o "1-2" \h \z \u` + `<w:updateFields w:val="true"/>` di `settings.xml` (Word menanyakan pembaruan saat dibuka). Halaman hanya benar setelah layout dihitung (Word/LibreOffice); jangan menjanjikan nomor halaman dari kode. Tampilkan catatan UI: "Klik kanan Daftar Isi → Perbarui bidang".
  2. Page-break sebelum Bab III; sama untuk Kata Pengantar→Daftar Isi bila perlu.
  3. Blok penutup kata pengantar: `{{formatted_date}}` + "Penulis" + `{% for p in penyusun %}{{p.nama}}{% endfor %}`, paragraf-paragraf akhir diberi `keepNext` agar tak terlempar sendirian (F23).
  4. Perbaiki "Latar Bekalang"; ganti indeks tetap dengan **loop generik** `for sub in bab.I.subbab` / `bab.III.subbab` dan render per `SubBab.kind` (`narasi|daftar`) — prasyarat S12.
  5. Logo: bila tanpa logo pengguna, isi `stats.logo_placeholder=true` dan tampilkan peringatan di hasil ("Logo masih placeholder").
- **Selesai bila** tes `TPL-001` (parse XML template) hijau + render mock memiliki field TOC, tanda tangan bernama, page-break Bab III. Tes golden: bandingkan teks hasil render (`docx2txt`/XML) dengan fixture.
- **Risiko** menyunting `.docx` merusak gaya/jinja → uji render mock dan render nyata; simpan template lama; ruff/CI tak mencakup `.docx`.

### Gelombang B — pencegahan di hulu (murah / hemat token)

#### S07 Registri lint + laporan kualitas (L0 penuh)
- **Menyelesaikan** F12, F27, F31 + deteksi semua kolom "Tanpa LLM = D/P" · **P1 · M · Δ0**
- **Berkas** baru `enhance/{models.py,lint/__init__.py,lint/*.py}`, `main.py` (tahap `enhance`), `steps.py` (`("enhance","Cek kualitas","Pemeriksaan otomatis & perbaikan terarah")`), `stats["quality"]`, skema API + `packages/api-types` (regenerate) + UI "Catatan kualitas" (daftar temuan, bukan angka skor tunggal).
- Tahap `enhance` berada **setelah `verify_citations`, sebelum `write_kata_pengantar`**; pada `lite` hanya menjalankan aturan `fix=auto` dan melaporkan sisanya.
- **Selesai bila** tiap aturan punya tes positif+negatif dengan fixture sintetis (§10); `--lint` CLI mengeluarkan JSON; waktu < 1 dtk untuk makalah 9 sub-bab.
- **Risiko** false positive membuat pengguna lelah → default tampilkan `blocker`+`major`; `minor/info` dilipat.

#### S08 Kebijakan konteks penulis (ContextPack)
- **Menyelesaikan** F02 (sebagian), F03, F09, F19, F27 · **P0 · M · Δ ≈ −6k**
- **Berkas** `main.py:fill_subbab_content (:322-363)`, `enhance/context.py` baru, `tasks.yaml` (placeholder baru).
- **Perubahan**: ganti "isi penuh sub-bab sebelumnya" (~1.000 token) dengan `ContextPack` buatan **kode**: judul seluruh outline (~150 token), RM (≈200), **ledger** (kalimat pertama tiap paragraf + semua fakta numerik yang sudah dipakai, ≤250 token), dan khusus 3.1 `digest_bab2` (2 kalimat/sub-bab Bab II, ≈400). Penulis 2.1 kini melihat RM; Kesimpulan melihat RM + ringkasan hasil.
  Prompt tambahan (statis, di depan): "jawab setiap RM dengan merujuk sub-bab hasilnya; jangan ulang angka yang ada di ledger — rujuk saja ('lihat 2.4')."
  `_references_for` untuk sub-bab tanpa referensi sendiri → beri **kartu/ringkasan 1 baris per sumber** (judul, tahun, apa yang diklaim) alih-alih 3 referensi pertama.
- **Selesai bila** tes: prompt 3.1 memuat semua RM dan digest; prompt 2.1 memuat RM; token prompt rata-rata turun (bandingkan `usage` WP-0); mode uji lulus.
- **Risiko** ekstraksi kalimat pertama kurang informatif → mulai sederhana, ukur lewat RED-001/TRC-001.

#### S09 Lepas tool pencarian dari penulis
- **Menyelesaikan** F10 (sebagian), biaya · **P1 · S · Δ negatif [H]** · **Berkas** `write_format_crew.py:50`, `tasks.yaml` (aturan 2).
- Dengan `MALAS_REFSEARCH=1` set `tools=[]` dan hapus instruksi "gunakan DuckDuckGo". Pertahankan di jalur lama (`REFSEARCH=0`).
- **Selesai bila** A/B di set uji: jumlah panggilan LLM/sub-bab = 1, sitasi `invalid` tidak naik. **Risiko** sub-bab tanpa excerpt makin tipis → sudah ditangani `_references_for` (kartu/abstrak).

#### S10 Parameter lingkup di input
- **Menyelesaikan** F03, RC-13 · **P1 · S · Δ ≈ 0** · **Berkas** `Makalah` (`jenis_makalah`, `subjek`, `jenjang`, opsional), `contoh.yaml`, `apps/api` skema job + form web (opsional; boleh diinferensi).
- Tanpa menambah panggilan: perluas `Outline` (skema keluaran outline) dengan `scope {jenis_makalah, subjek, jenjang}` dan `research_questions` kerangka; bila pengguna mengisi, itu menang. Isi disuntik ke prompt penulis (statis, di depan).
- **Selesai bila** tes parser (`tolerant.parse_outline` menerima kunci baru dan **tetap** menerima bentuk lama) + dummy mock.

#### S11 Blueprint (kerangka argumen) — 1 panggilan planner
- **Menyelesaikan** F02, F11, F13, F18, F19, F26 · **P1 · M · Δ ≈ +7,6k**
- **Berkas** `enhance/blueprint.py`, `main.py` (di `generate_outline`, setelah referensi ada), `tasks.yaml` (rujuk `subbab_tasks`).
- **Perubahan**: setelah outline + referensi + (jika ada) kartu, **satu** `llm.call` terstruktur (`Blueprint`, §6.3) dengan masukan: judul, mata kuliah, outline, judul+tahun tiap referensi (tanpa abstrak). Keluaran: RM (≤3), peta RM→sub-bab, tugas argumen per sub-bab (termasuk "satu sisi kritis" dan "bedakan hasil belajar vs motivasi bila relevan"), `domain_checklist`, `avoid_repeat`. Cabang `is_mock()` → dummy. Penulis menerima hanya potongan relevan (±250 token).
- **Selesai bila** tes: gagal-parse → `None` dan alur berjalan tanpa blueprint; RM hasil blueprint memenuhi TRC-003 dengan Tujuan; stats mencatat token tahap.
- **Risiko** halusinasi checklist domain → ia hanya *panduan* untuk penulis dan lint DOM-001 (tidak jadi fakta). **Biaya** hanya di tier `standard+`.

#### S12 Outline v2 (profil dokumen)
- **Menyelesaikan** F16, F17 · **P1 · M · Δ ≈ +1,5k** · **Prasyarat** S06 (template loop generik).
- `MALAS_PROFILE=kajian_pustaka` (default) → Bab I: Latar Belakang, Rumusan Masalah, Tujuan, **Manfaat**, **Metode Penulisan**; Bab III: Kesimpulan, **Saran** (+ "Keterbatasan" di Kesimpulan). Profil `penelitian` ditunda.
- Ubah prompt outline (`tasks.yaml` `make_outline_task`) dari "HANYA 3/1" ke daftar per profil; `SubBab.kind` ditentukan dari judul (daftar: rumusan/tujuan/manfaat).
- **Selesai bila** tes render dengan Bab I 5 sub-bab dan Bab III 2 sub-bab; checkpoint lama (3/1) tetap bisa di-resume.

#### S13 Tabel sintesis dari kartu bukti (tanpa token penulis)
- **Menyelesaikan** F15, F26 · **P2 · M · Δ ≈ 0 (tabel dirakit kode)** · **Prasyarat** S15 (kartu), S06 (render tabel).
- Tambah `ContentTable{caption, header, rows}` ke `ContentItem`; konverter merender tabel (tambahkan di template via `{% tr %}` docxtpl atau sub-template). Tabel "Sintesis studi" (penulis-tahun, desain, sampel, hasil utama, keterbatasan) disusun **dari `EvidenceCard`**, bukan dari LLM penulis; disisipkan di akhir sub-bab 2.x yang disebut Blueprint.
- **Selesai bila** tes: tabel dengan 3 kartu terender; `TolerantConverter`/checkpoint menerima tipe baru.

#### S14 Retrieval v2 (referensi lebih beragam, ada karya dasar)
- **Menyelesaikan** F14, F20 · **P1 · M · Δ ≈ +1,2k (referensi tambahan ke prompt)** · **Berkas** `refsearch/{plan,orchestrator,rank}.py`.
- **Perubahan**
  1. **Perbaiki `indo`**: hapus kata sambung dari `_ID_HINT` (`plan.py:15`); `indo=True` hanya bila ada penanda topik lokal (indonesia, nasional, daerah, islam, hukum, pancasila, undang, nama daerah) **atau** LLM-plan menyatakannya. Turunkan prior bahasa +0,3 → +0,1.
  2. **Pass landmark**: untuk sub-bab bertipe konsep/teori (dari Blueprint `subbab_tasks` atau judul), tambah satu query Inggris tanpa batas tahun, urut `cited_by`, `kind=article|book`, `year_min` longgar; wajib ≥1 landmark bila tersedia.
  3. `k` adaptif: 3 untuk konsep/teori & 1.1, 2 lainnya; target total referensi `MALAS_REF_TARGET` (default 12), tetap `max_reuse=2`.
  4. Laporan `report`: rasio bahasa, jumlah landmark; sumbernya aturan REF-003.
- **Selesai bila** tes `test_refsearch.py` diperluas: judul Indonesia generik → `indo=False`; fixture dengan karya 20k kutipan terpilih di sub-bab konsep; rasio bahasa tercatat. Ukuran nyata di WP-0/uji CI refsearch.
- **Risiko** lebih banyak HTTP → tetap dalam tenggat global (`MALAS_REFSEARCH_TIMEOUT`) dan cache sqlite 14 hari; kuota OpenAlex (key opsional).

### Gelombang C — bukti & kritik (LLM, berbatas biaya)

#### S15 Kartu Bukti (L2)
- **Menyelesaikan** F06-F08, F10, F11 · **P1 · L · Δ ≈ +9k bersih (+15k kartu − 6k prompt penulis)**
- **Berkas** `enhance/evidence.py`, `main.py` (setelah `fetch_fulltexts`, sebelum menulis), cache `.cache/refsearch` (tabel baru `evidence_cards`).
- **Perubahan**
  - Praproses **tanpa LLM**: regex ukuran sampel (`n\s*=\s*\d+`, "70 siswa"), statistik (`F\(`, `p\s*[=<]`, `η²`, `CI`), kata desain ("kuasi", "kelompok kontrol", "pretest-posttest", "systematic review", "R&D/ADDIE", "wawancara/observasi").
  - 1 `llm.call` murah per referensi (model `planner`), masukan: judul + abstrak + ≤1.500 karakter passage terpilih (BM25 query "metode sampel hasil keterbatasan"), keluaran `EvidenceCard` terstruktur; angka `key_result` **harus substring** dari teks masukan (cek kode; jika tidak → kosongkan). `basis` mencatat abstrak vs full-text, `confidence` rendah bila hanya abstrak.
  - **Cache lintas pengguna kunci DOI** (data publik; tidak memuat teks pengguna). `ref_key=doi|hash(judul+tahun)`; TTL 90 hari.
  - Penulis menerima **kartu ringkas (≈150 token/ref)** + 1 passage pendek alih-alih seluruh dump 3.000 karakter → hemat input penulis.
  - Paralel dengan `ThreadPoolExecutor(4)` mengikuti pola `refsearch`; hormati `max_rpm`.
- **Selesai bila** tes: kartu dari abstrak Sholahudin-style fixture (kuasi, kontrol, n=70, F=8,52) → `causal_ok=True`; fixture pre-post tanpa kontrol → `False`; angka yang tak ada di teks dibuang; cache hit tidak memanggil LLM.
- **Risiko** salah klasifikasi desain dari abstrak → `confidence=rendah` dan `CLM-001` hanya `major` bila `confidence≥sedang`; selebihnya `info`.

#### S16 Gerbang klaim (guardrail penulis)
- **Menyelesaikan** F06-F08 · **P1 · S · Δ ≈ 0-+2k (retry bila gagal)** · **Prasyarat** S15 dan WP-8 (crewAI 1.x).
- Fungsi guardrail murni kode: jalankan `CLM-001/CLM-004/CIT-001/RED-001` pada keluaran sub-bab; bila ada `major+` → `(False, "umpan balik terarah: kalimat X memakai 'terbukti' padahal studi Y pra-pascates tanpa kontrol; ganti 'menunjukkan peningkatan' dan sebut keterbatasan")`.
- Pakai `Task(guardrails=[fn], guardrail_max_retries=1)`. **Soft-fail**: closure penghitung percobaan; pada percobaan terakhir kembalikan `(True, hasil)` dan catat temuan ke `quality`, karena crewAI **melempar** Exception saat retry habis (`task.py:1562`). Hentikan `_write_subbab` retry buatan sendiri **hanya** untuk jalur guardrail (tetap tangani galat fatal/kosong).
- **Selesai bila** tes dengan LLM palsu yang pertama melanggar lalu patuh → 2 panggilan, hasil bersih; yang tak pernah patuh → hasil terakhir + temuan, tanpa raise.

#### S17 Ganti crew `citation_fix` dengan guardrail sitasi
- **Menyelesaikan** efisiensi · **P2 · S · Δ ≈ 0** · `main.py:verify_citations`, `finishing_crew`.
- Pindahkan perbaikan sitasi ke guardrail S16 (pesan: "sitasi X tak sah; gunakan hanya: [label sah]"), pertahankan `verify_citations` sebagai **pemeriksa akhir + pelapor** (tanpa crew). Hemat satu pembuatan Crew+Agent per sub-bab bermasalah. Jalur lama tetap ada di balik env sampai WP-8 lolos uji nyata.

#### S18 Kritik terarah (L3) — **satu** panggilan
- **Menyelesaikan** F02, F11, F19, F31 + residu semua aturan · **P1 · M · Δ ≈ +16k**
- **Berkas** `enhance/critic.py`, `enhance/rubric.md` (rubrik di-embed sebagai string).
- **Perubahan**: `llm.call` tunggal, masukan = seluruh makalah dengan penanda lokasi `[II/2.3 ¶4]`, `Blueprint`, kartu ringkas, hasil lint (agar tak mengulang), rubrik singkat (RM terjawab? klaim vs desain? kritis? domain? pengulangan? melebar?). Keluaran JSON `list[Finding]` (maks 12, wajib `where` + `hint` satu kalimat). Validasi: lokasi harus ada; temuan tak berlokasi dibuang; duplikat lint dibuang. Model: `reviewer` (di BYOK = model penulis; di server bisa model murah panjang-konteks).
- **Selesai bila** tes dengan LLM palsu: JSON rusak → `[]` tanpa raise; lokasi fiktif dibuang; batas 12 ditaati. Evaluasi manual di set uji (WP-0): presisi temuan ≥ 70% (ditinjau manusia).
- **Risiko** kritik fiktif → hanya temuan berlokasi yang valid dan **tidak langsung diterapkan**: melalui S19 dengan penerimaan monoton.

#### S19 Penambal terarah (L4)
- **Menyelesaikan** semua `fix=patch` · **P1 · M · Δ ≈ +4,3k per sub-bab (rata-rata 3 → ≈ +13k)**
- **Berkas** `enhance/patch.py`, `main.py` (loop `enhance`), checkpoint (`subbab.content` + `quality`).
- Per sub-bab bertemuan `major+` (urut keparahan, **maks N=3** atau sampai anggaran habis): panggil penulis dengan teks sekarang + daftar `hint` + kartu/ContextPack; keluaran dipaksa sama bentuk (`SubBab`). **Penerimaan monoton**: jalankan ulang L0 pada sub-bab; terima bila skor berbobot turun (blocker=8, major=3, minor=1) dan tak ada blocker baru; sebaliknya pertahankan teks lama dan catat "tambalan ditolak".
- Simpan checkpoint setelah tiap tambalan (resume aman). Satu putaran saja (tanpa loop tak berujung).
- **Selesai bila** tes: tambalan yang memperburuk ditolak; yang memperbaiki diterima; anggaran habis → sisanya dilewati dan dilaporkan.

#### S20 Cek dukungan-sumber (opsional, tier deep)
- **Menyelesaikan** F09, F10, sebagian F06-F08 · **P2 · M · Δ ≈ +7k**
- Untuk kalimat bersitasi berangka/kausal (prioritas risiko): skor tumpang-tindih BM25 antara kalimat dan kartu/passage sumber (0 token). Hanya yang < ambang dikirim **dalam satu batch** (≤12 kalimat/panggilan) ke LLM penilai ("didukung/sebagian/tidak, kutip kalimat sumber"). Hasil → `CIT-003`/`CLM-*`. Tanpa NLI lokal (terlalu berat untuk Space CPU gratis).

### Gelombang D — platform & kendali biaya

#### S21 Naikkan crewAI ke 1.15.x dan lepas litellm dari jalur kunci
- **Menyelesaikan** RC-15 · **P1 · M · Δ 0** · **Berkas** `packages/engine/pyproject.toml`, `uv.lock`, `config.py`, `providers.py`.
- Pin `crewai[tools,google-genai]>=1.15,<1.16` (+ `langchain-community`), tanpa `litellm`. `providers.py`: ganti nama field `litellm_prefix` → `model_prefix` (kompatibel mundur di UI/API: tetap menerima nama lama bila ada klien); Kenari: `openai/<model>` + `base_url` (sudah terbukti membuat provider native). Uji sungguhan satu job per provider (Gemini, OpenRouter, Kenari) **sebelum** merge ke `main`.
- **Daftar periksa**: `pytest` engine+api; mock penuh; 1 makalah nyata per provider (catat token); HF Space (RAM/start-up, dependensi `lancedb/qdrant-client/chromadb` ikut terpasang → ukur ukuran image & cold start; jika berat, evaluasi `crewai` ber-extras minimal); `CREWAI_TRACING_ENABLED=false` tetap efektif; `AutoFakeLLM` kompatibel dengan `BaseLLM` 1.x (lolos di spike).
- **Rollback**: beri tag git sebelum merge (seperti `pre-refsearch-2026-11-20`); `git revert` memulihkan lockfile lama.
- **Risiko**: rilis 1.15.x harian → pin kecil dan upgrade terjadwal; perilaku `Flow` berubah halus (event/streaming); logika `_FATAL` di `main.py:45` mencocokkan teks galat → galat provider native berbeda format → perluas daftar dan uji.

#### S22 Kendali biaya & telemetri token per tahap
- **Menyelesaikan** semua · **P0 · S · Δ 0** · **Berkas** `main.py:_add_usage`, `stats`, `config.py`.
- `stats["usage_by_stage"] = {outline, refs_plan, tulis, sitasi, enhance_blueprint, enhance_cards, enhance_critic, enhance_patch, ...}`; `MALAS_ENHANCE`, `MALAS_ENHANCE_MAX_TOKENS`; estimasi biaya sebelum jalan (sudah di daftar ide `HANDOFF` §4C) memakai tabel §8.
- Panggilan langsung `llm.call` tak melaporkan usage → pakai taksiran 4 karakter/token seperti `_search_refs` (`main.py:229`) dan **beri label "taksiran"**.

#### S23 Harness evaluasi (set uji)
- **P0 · M · Δ 0** · lihat §10.

#### S24 Teknologi yang dipertimbangkan lalu ditunda/ditolak
| Opsi | Keputusan | Alasan & biaya |
|---|---|---|
| Embedding/vektor lokal untuk RAG | **Tolak (sekarang)** | BM25 + kartu cukup; embedding menambah dependensi/RAM di Space gratis dan tak menaikkan akurasi sitasi secara terukur |
| NLI lokal untuk dukungan-sumber | **Tolak** | model multibahasa berat untuk CPU gratis; S20 (BM25 + batch LLM) lebih murah |
| Fitur "Citations/grounding" native penyedia | **Tunda** | bagus, tetapi BYOK lintas penyedia (OpenRouter/Kenari) tak seragam; evaluasi bila 1 penyedia dominan |
| Batch API penyedia (diskon umumnya ±50%, verifikasi harga) | **Tunda** | cocok untuk mode `deep` offline; job kita interaktif; kembali bila ada antrean malam |
| `@human_feedback` (persetujuan tambalan di UI) | **Tunda** | butuh UI + status job "menunggu pengguna"; nilai tinggi setelah S19 stabil |
| Pindah ke LangGraph/DSPy | **Tolak** | `Flow` + guardrail cukup; migrasi tak menambah kemampuan yang dibutuhkan |
| Model "reasoning" untuk kritik | **Opsional** | ganti env `MALAS_MODEL_REVIEWER` pada server; satu panggilan sehingga dampak biaya terbatas |
| Tool pencarian web umum untuk penulis | **Tolak** | permukaan sitasi palsu + loop biaya (RC-12); pencarian dilakukan `refsearch` |

---

## 8. Anggaran token (perkiraan — **ukur di WP-0**)

Asumsi baseline (9 sub-bab: 1.1-1.3, 2.1-2.5, 3.1; `MALAS_REFSEARCH=1`, `FULLTEXT=1`):

| Tahap | Masukan | Keluaran | Catatan |
|---|---|---|---|
| Outline | ~1,2k | ~0,5k | |
| Rencana query (refsearch) | ~0,8k | ~0,5k | |
| Penulis × 9 | ~3,4k (aturan+scaffold ~1,2k; sub-bab sebelumnya ~1,0k; referensi ~1,2k) | ~1,3k | ReAct bertool dapat melipatgandakan |
| Perbaikan sitasi | 2,5k + 1,2k per sub-bab bermasalah | | 0-n kali |
| Kata pengantar | ~0,7k | ~0,5k | |
| **Total baseline B** | **≈ 36k** | **≈ 11k** | **≈ 47k (±30%)** |

Δ per komponen (token, kelas model):

| Komponen | Δ total | Kelas | Catatan |
|---|---|---|---|
| S08 ContextPack | −6k | penulis | ganti 1,0k dengan ~0,35k × 8 |
| S09 lepas tool | ≤0 [H] | penulis | hemat iterasi |
| S11 Blueprint | +4k panggilan +3,6k ke penulis = **+7,6k** | planner + penulis | |
| S15 Kartu bukti | +15k kartu (murah) −6k penulis = **+9k** | planner | cache DOI → tinggal ≈0 untuk referensi yang pernah diproses |
| S18 Kritik | **+16k** (≈14k masuk, 1,5k keluar) | reviewer | 1 panggilan |
| S19 Tambal (3 sub-bab) | **+13k** | penulis | batas N dan anggaran |
| S20 Cek dukungan | **+7k** | planner | opsional |
| S12 Outline v2 | +1,5k | penulis | 2 sub-bab tambahan |
| S14 Retrieval v2 | +1,2k | penulis | referensi tambahan |

Tier: **lite ≈ −6k (−13%)**; **standard ≈ −6 +7,6 +16 +13 ≈ +30k (≈ +65%)**; **deep ≈ standard + 9 + 7 ≈ +46k (≈ +100%)**.
Nilai rupiah/dolar bergantung harga penyedia dan model yang dipilih pengguna (BYOK) — **jangan menanamkan harga di kode**; hitung
dari `usage_by_stage` × harga yang pengguna/operator isi. Prinsip penghematan: (1) cache DOI (kartu & kandidat referensi), (2) satu
panggilan panjang lebih murah daripada banyak panggilan kecil (overhead scaffolding), (3) awalan prompt statis di depan untuk caching,
(4) tambal hanya sub-bab bermasalah, (5) berhenti saat anggaran habis.

---

## 9. Roadmap (satu WP = satu PR; urut)

| WP | Isi | Solusi | Bergantung | Token | Alasan urutan |
|---|---|---|---|---|---|
| **WP-0** | Harness evaluasi + baseline ukur: fixture sintetis, skrip metrik, ukur token/waktu/jumlah referensi di ≥5 judul nyata | S22 (telemetri), S23 | — | 0 | Tanpa angka, semua Δ di atas hanya tebakan |
| **WP-1** | Integritas sitasi/pustaka | S01, S02, S03, S04, S05 | WP-0 (fixture) | 0 | ROI tertinggi; menutup F01, F21, F22, F28-F30; **tanpa menyentuh template** |
| **WP-2** | Template v3 + peringatan logo | S06 | WP-1 | 0 | Cacat visual & prasyarat S12/S13 |
| **WP-3** | Konteks penulis + lingkup + tanpa tool | S08, S09, S10 | WP-1 | −13% | Cegah F02/F03/F09/F27 di hulu |
| **WP-4** | Lint registri + laporan kualitas + UI | S07 | WP-1, WP-2 | 0 | Menjadikan semua temuan terlihat; mulai tier `lite` |
| **WP-5** | Retrieval v2 | S14 | WP-0 | +2% | Memperbaiki F14/F20 |
| **WP-6** | crewAI 1.15.x + provider native | S21 | WP-1 | 0 | Prasyarat guardrail; uji nyata wajib |
| **WP-7** | Blueprint + Outline v2 + Kartu bukti + tabel | S11, S12, S15, S13 | WP-2, WP-3, WP-5 | +~20k | Tier `standard/deep` |
| **WP-8** | Guardrail + Kritik + Tambal + cek dukungan | S16, S17, S18, S19, S20 | WP-4, WP-6, WP-7 | +~36k | Pengobatan terarah, berbatas biaya |

Setiap PR: tes baru hijau, `uv run pytest` hijau, berkas baru dimasukkan ke daftar ruff di `ci.yml`, **tanpa** mengubah teks hukum kecuali perilaku data berubah
(cache kartu = data publik; tidak menyimpan teks pengguna → catat di PR bila ada keraguan). Mode uji lulus.

---

## 10. Pengujian & evaluasi

**Fixture sintetis** (`packages/engine/tests/fixtures/enhance/`): pendek, tanpa data pribadi, satu cacat per berkas; **jangan** menaruh makalah pengguna atau PDF uji di repo.
Contoh kasus wajib (diturunkan dari makalah uji, tetapi ditulis ulang sintetis):

| Fixture | Memicu |
|---|---|
| `cit_single_letter.json` (`(M dkk., 2026)` + `(Utami, 2024)`) | CIT-001, tak ada prune (S02) |
| `names.json` (`Raseena P M`, `Maya C`, lembaga, satu kata) | S01 |
| `rm_list.json` (pengantar + 2 butir + penjelasan) | STR-002 / S05 |
| `dup_numbering.json` (`2.1 …`) | STR-001 / S04 |
| `repeat_stats.json` (statistik sama di 3 sub-bab) | RED-001 |
| `overclaim.json` + kartu `causal_ok=False` | CLM-001 |
| `kesimpulan_no_rm.json` | TRC-001 |
| `population_drift.json` (bukti siswa, kesimpulan mahasiswa) | TRC-002 |
| `tpl_missing_toc` (template uji tanpa field) | TPL-001 |

**Metrik** (dilaporkan per run di `stats.quality_metrics`; tolok ukur target di set uji ±10 judul lintas jurusan, sesuai ide `HANDOFF` §4C):
sitasi `suspect/invalid = 0`; referensi hilang senyap = 0; RM tanpa jejak di Kesimpulan = 0; duplikat fakta numerik ≤ 1 per fakta; pelanggaran
klaim-kausal (kartu confidence≥sedang) = 0; kelengkapan APA ≥ 95% entri; rasio referensi berbahasa Indonesia ≤ 60% pada topik non-lokal;
≥1 landmark pada sub-bab konsep; token total terhadap baseline per tier; tambalan diterima : ditolak.

**Evaluasi manusia** (sebelum menaikkan default tier): 10 makalah × 2 penilai buta, rubrik 5 butir (RM terjawab, kejujuran klaim, kedalaman,
keterbacaan, format). Tolak naik tier bila tambalan menurunkan keterbacaan pada >20% sampel.

**Regresi**: `pytest` engine+api; mock penuh; satu job nyata per provider sebelum merge S21; uji RC-02 selalu ada di CI.

---

## 11. Risiko, keputusan terbuka, dan yang sengaja tidak dilakukan

| # | Risiko / pertanyaan | Mitigasi / keputusan |
|---|---|---|
| 1 | Kritik/tambal LLM menurunkan mutu | Penerimaan monoton (S19), satu putaran, tier bertingkat, default `lite` |
| 2 | False positive lint | Ambang dikalibrasi WP-0; `minor/info` dilipat di UI |
| 3 | Edit template `.docx` merusak gaya | Template lama dipertahankan; tes render; uji di Word & LibreOffice |
| 4 | Daftar Isi tanpa nomor halaman bila pengguna tak memperbarui field | Catatan UI; **jangan** menjanjikan halaman dari kode |
| 5 | crewAI 1.15.x berubah cepat; image Space membengkak (`lancedb`, `qdrant`) | Pin minor, ukur image, evaluasi extras minimal (WP-6) |
| 6 | Klasifikasi desain dari abstrak keliru | `confidence`, hanya aturan `major` bila ≥sedang |
| 7 | Nama penulis ambigu (nama ber-inisial di belakang) | Crossref `family/given` diutamakan; heuristik ditandai `name_confidence` |
| 8 | Kejujuran produk | Laporan kualitas berisi temuan + batas pemeriksa; tak ada kata "lolos/aman"; hasil tetap **draf** (`HANDOFF` §9) |
| 9 | Retensi/hukum | Cache kartu hanya data publik (DOI); jangan cache teks makalah; bila diubah → perbarui `features/legal/content.ts` |
| 10 | **Terbuka**: apakah `lite` jadi default global? | Usul: ya, setelah WP-4 lolos uji manusia |
| 11 | **Terbuka**: model kritik terpisah di UI BYOK? | Usul: **tidak** di v1 (hanya dua kolom model: planner/writer); server boleh `MALAS_MODEL_REVIEWER` |
| 12 | **Terbuka**: impor `.docx` pengguna untuk ditingkatkan | Di luar cakupan; butuh parser struktur; tinjau setelah WP-8 |

**Sengaja tidak dilakukan**: menulis ulang seluruh makalah dengan agen reviewer; menambah Memory/Knowledge crewAI; migrasi checkpoint ke `@persist`;
embedding/NLI lokal; tool web bagi penulis; menanamkan harga token di kode; menjanjikan deteksi AI/plagiarisme.

---

## 12. Lampiran

### 12.1 Peta berkas yang akan disentuh

| Area | Berkas |
|---|---|
| Baru | `packages/engine/src/malas/enhance/{__init__,models,context,blueprint,evidence,critic,patch}.py`, `enhance/lint/*.py`, `refsearch/names.py`, `tests/test_enhance_*.py`, `tests/fixtures/enhance/*` |
| Ubah | `main.py` (tahap `enhance`, konteks), `steps.py`, `citations.py`, `docx_converter.py`, `crews/models/TaskOutput.py`, `crews/write_format_crew/{write_format_crew.py,config/tasks.yaml}`, `crews/planner_crew/config/tasks.yaml`, `refsearch/{providers,plan,rank,orchestrator,models}.py`, `tolerant.py` (kunci outline/blueprint baru), `config.py`, `providers.py`, `pyproject.toml`, `uv.lock`, `templates/*.docx`, `.github/workflows/ci.yml` (ruff berkas baru), `apps/api` (skema stats), `packages/api-types` (regenerate), `apps/web` (Catatan kualitas) |
| Jangan disentuh tanpa alasan | `checkpoint.py` (hanya tambah field opsional di `Makalah`), `apps/api` autentikasi/vault/kuota, teks hukum |

### 12.2 Perintah reproduksi (dijalankan di sesi analisis)

```bash
# RC-01/RC-02: sitasi "M dkk." tak terdeteksi dan referensinya terhapus
PYTHONPATH=packages/engine/src python3 - <<'EOF'
from malas.crews.models.TaskOutput import *
from malas.citations import *
ref = ReferenceItem(title="Gamification of teaching and learning", authors=["Raseena P M", "Maya C"], year=2026, link="https://doi.org/x")
ref2 = ReferenceItem(title="Gamifikasi dalam pembelajaran bahasa Arab", authors=["Rizka Utami"], year=2024, link="https://doi.org/y")
print(citation_label(ref))                                   # (M dkk., 2026)
txt = "… (M dkk., 2026). Menurut M dkk. (2026) … (Utami, 2024)."
print([c.raw for c in extract_citations(txt)])               # hanya (Utami, 2024)
m = Makalah(daftar_pustaka=[ref, ref2], bab={"II": Bab(judul="x", subbab=[SubBab(judul="2.1", content=[ContentText(isi=txt)])])})
r = check_citations(m); print(r.invalid, prune_unused_references(m, r))   # {} 1  -> referensi dihapus senyap
EOF
```
Spike crewAI 1.15.44: `uv venv && uv pip install "crewai[tools]==1.15.44" docxtpl duckduckgo-search pillow pypdf python-dotenv pyyaml requests trafilatura langchain-community pytest httpx`,
lalu `pytest packages/engine/tests` dan `python -m malas.main` dengan `MALAS_MOCK=1 MALAS_REFSEARCH=1 MALAS_FULLTEXT=0`.

### 12.3 Sumber
- Source crewAI 1.15.44 (wheel PyPI, dibaca langsung): `crewai/llm.py`, `crewai/task.py`, `crewai/tasks/{llm_guardrail,hallucination_guardrail}.py`, `crewai/agent/core.py`, `crewai/flow/*`, `crewai/llms/providers/*`.
- PyPI: <https://pypi.org/project/crewai/> (versi terbaru & dependensi), <https://pypi.org/project/litellm/>.
- Insiden rantai-pasok litellm (Maret 2026): <https://docs.litellm.ai/blog/security-update-march-2026>, <https://snyk.io/articles/poisoned-security-scanner-backdooring-litellm>, <https://research.jfrog.com/post/litellm-compromised-teampcp/> (sumber berbeda soal lama rilis berbahaya online: ±40 menit hingga ±3 jam).
- Dokumentasi crewAI (tidak dapat diakses dari sandbox; ringkasan dari hasil pencarian): <https://docs.crewai.com/concepts/tasks>, <https://docs.crewai.com/en/concepts/flows>, panduan penghapusan litellm `docs.crewai.com/edge/en/learn/litellm-removal-guide`. **Verifikasi ulang di mesin berinternet** sebelum WP-6.
- OpenAlex (metadata referensi uji, `biblio`): <https://api.openalex.org/>.

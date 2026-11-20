/** Teks Ketentuan Layanan dan Kebijakan Privasi.
 *
 *  Isinya HARUS mengikuti perilaku sistem yang sebenarnya. Fakta di bawah diambil dari kode (per 2026-11-20):
 *  - retensi: job selesai/gagal dihapus 48 jam setelah selesai (JobManager.purge; default di app.py DEFAULT_RETENTION_HOURS, mode hosting);
 *  - yang dikirim ke penyedia LLM: judul, mata kuliah, tahun, kota, NAMA dosen dan penyusun (kata pengantar), plus
 *    konten yang disusun; NIM, kelas, universitas, fakultas, jurusan tidak dikirim (packages/engine crews/*.yaml);
 *  - pencarian referensi: Crossref, Semantic Scholar, arXiv (tools/custom_tool.py, fulltext.py);
 *  - tabel `users` hanya menyimpan id Clerk; tabel `usage` menyimpan kuota harian (id pengguna, tanggal, jumlah);
 *  - logo kampus/sekolah: satu per akun di tabel user_logos (PNG ternormalisasi), disimpan sampai pengguna menghapusnya,
 *    tidak dikirim ke penyedia LLM, hanya ditanam ke .docx;
 *  - API key: hanya di memori selama job; penyimpanan terenkripsi hanya bila fitur diaktifkan dan dipilih pengguna.
 *  Bila perilaku itu berubah (mis. analitik ditambahkan, retensi diubah), perbarui teks ini dan LEGAL_UPDATED. */

export type Block = string | string[]; // string = paragraf, array = daftar butir
export interface Section { id: string; title: string; blocks: Block[] }
export interface LegalDoc { title: string; intro: string; sections: Section[] }

export const LEGAL_UPDATED = "20 November 2026";
export const CONTACT_URL = "https://github.com/Alfthrpy/makalah-automation-via-language-model-assisted-system/issues";

export const TERMS: LegalDoc = {
  title: "Ketentuan Layanan",
  intro:
    "Ini aturan main memakai MALAS. Dibuat sesingkat dan sejelas mungkin. Dengan membuat akun atau memakai MALAS, kamu setuju dengan ketentuan ini.",
  sections: [
    {
      id: "apa-itu-malas",
      title: "Apa itu MALAS",
      blocks: [
        "MALAS (Makalah Automation via Language-model Assisted System) adalah alat bantu yang menyusun DRAF makalah dengan bantuan model bahasa (AI). Hasilnya berupa berkas .docx yang kamu baca, cek, dan sesuaikan sendiri.",
        "MALAS bukan pengganti proses belajar dan bukan layanan yang menjamin hasil akhir. Pengelola layanan adalah perorangan (proyek pribadi), bukan lembaga pendidikan.",
      ],
    },
    {
      id: "tanggung-jawabmu",
      title: "Tanggung jawabmu",
      blocks: [
        [
          "Hasilnya draf. Baca seluruhnya, periksa isi, angka, dan klaimnya sebelum dipakai.",
          "Sitasi dicocokkan dengan sumber yang ditemukan, tetapi tetap bisa keliru atau tidak lengkap. Cek ulang ke sumber aslinya.",
          "Aturan kampus dan dosenmu soal penggunaan AI berlaku. Memahami dan mematuhinya adalah tanggung jawabmu, termasuk menyatakan penggunaan AI bila diwajibkan.",
          "Kamu bertanggung jawab atas makalah yang kamu kumpulkan dan atas segala akibat akademiknya.",
        ],
      ],
    },
    {
      id: "yang-tidak-dijanjikan",
      title: "Yang tidak kami janjikan",
      blocks: [
        [
          "Nilai, kelulusan, atau diterimanya makalah oleh dosen atau kampusmu.",
          "Lolos atau tidaknya pemeriksaan plagiarisme maupun pendeteksi AI. MALAS tidak dirancang untuk menghindari pemeriksaan semacam itu dan tidak boleh dipakai untuk tujuan tersebut.",
          "Keakuratan, kebaruan, atau kelengkapan isi maupun daftar pustaka.",
          "Bahwa layanan selalu tersedia atau setiap makalah selalu selesai.",
        ],
      ],
    },
    {
      id: "akun-dan-kuota",
      title: "Akun, kuota, dan batas pemakaian",
      blocks: [
        [
          "Kamu masuk lewat akun yang dikelola Clerk. Satu akun untuk satu orang; jaga akunmu.",
          "Saat ini kuotanya 3 makalah nyata per akun per hari (Mode uji dan 'lanjutkan dari titik terakhir' tidak dihitung). Angka ini bisa berubah.",
          "Satu akun hanya boleh punya satu makalah yang sedang diproses, dan antrean bersama dibatasi.",
          "Dilarang mengakali batas ini, misalnya dengan banyak akun atau otomatisasi massal.",
        ],
      ],
    },
    {
      id: "api-key-dan-biaya",
      title: "API key dan biaya",
      blocks: [
        [
          "Biaya model bahasa ditagih penyedia (OpenRouter atau Kenari) ke API key milikmu, bukan ke MALAS. Besarnya bergantung pada model dan panjang makalah, dan kami tidak bisa memastikannya di muka.",
          "Disarankan memakai key khusus dengan batas kredit kecil, lalu mencabutnya setelah selesai.",
          "Mode uji tidak memanggil model bahasa, tidak butuh key, dan isinya hanya teks contoh.",
          "Pakai hanya key milikmu sendiri atau key yang kamu punya izin untuk memakainya.",
        ],
      ],
    },
    {
      id: "yang-dilarang",
      title: "Penggunaan yang dilarang",
      blocks: [
        [
          "Melanggar hukum atau hak orang lain, atau membuat konten yang melecehkan, menyesatkan, atau berbahaya.",
          "Mengganggu, membebani secara berlebihan, atau mencoba membobol layanan atau akun orang lain.",
          "Memakai MALAS untuk kecurangan akademik yang dilarang institusimu.",
        ],
        "Bila ini terjadi, kami boleh membatasi atau menutup aksesmu.",
      ],
    },
    {
      id: "hasil-dan-hak",
      title: "Hasil dan hak",
      blocks: [
        "Isian yang kamu masukkan dan berkas hasilnya adalah milikmu; kami tidak mengklaim hak atas makalahmu. Karena hasilnya dibuat model bahasa, isinya bisa mirip dengan keluaran lain. Soal hak cipta, lisensi sumber, dan pengakuan penggunaan AI, kamu sendiri yang bertanggung jawab.",
        "Kamu menyatakan punya hak untuk memasukkan data yang kamu isi, termasuk logo kampus atau sekolah yang kamu unggah. Pakai hanya logo yang memang boleh kamu pakai; MALAS tidak memeriksa kepemilikannya dan tidak menyiratkan dukungan dari institusi mana pun.",
      ],
    },
    {
      id: "layanan-gratis",
      title: "Layanan gratis, apa adanya",
      blocks: [
        [
          "MALAS gratis dan berjalan di layanan gratis, jadi server bisa tidur atau restart sewaktu-waktu. Makalah yang sedang diproses bisa terputus; kamu bisa melanjutkannya dari titik terakhir.",
          "Riwayat dan berkas dihapus otomatis 48 jam setelah makalah selesai. Unduh segera.",
          "Layanan diberikan apa adanya, tanpa jaminan apa pun.",
        ],
      ],
    },
    {
      id: "batas-tanggung-jawab",
      title: "Batas tanggung jawab",
      blocks: [
        "Sejauh diizinkan hukum yang berlaku, pengelola tidak bertanggung jawab atas kerugian tidak langsung, hilangnya data, sanksi atau akibat akademik, maupun biaya penyedia API yang timbul dari pemakaianmu.",
      ],
    },
    {
      id: "perubahan-dan-kontak",
      title: "Perubahan, penghentian, dan kontak",
      blocks: [
        [
          "Ketentuan ini bisa berubah. Perubahan penting diumumkan di situs ini; memakai MALAS setelah perubahan berarti kamu menerimanya.",
          "Kamu boleh berhenti kapan saja. Hapus makalahmu dari dasbor, dan hapus akunmu lewat menu akun bila tersedia atau hubungi kami.",
          "Kami boleh menghentikan layanan atau menutup akun yang melanggar ketentuan.",
          "Ketentuan ini tunduk pada hukum Republik Indonesia.",
        ],
        `Pertanyaan, laporan penyalahgunaan, atau permintaan hapus data: buka isu di ${CONTACT_URL}.`,
      ],
    },
  ],
};

export const PRIVACY: LegalDoc = {
  title: "Kebijakan Privasi",
  intro:
    "Ringkasnya: kami menyimpan sesedikit mungkin, makalahmu dihapus otomatis, dan API key-mu tidak ditulis ke disk atau log. Berikut rinciannya.",
  sections: [
    {
      id: "ringkasan",
      title: "Ringkasan",
      blocks: [
        [
          "Makalah dan riwayatmu dihapus otomatis 48 jam setelah selesai.",
          "API key tidak ditulis ke disk, log, maupun basis data (kecuali kamu memilih menyimpannya, lihat bagian API key).",
          "Isi yang dikirim ke model bahasa melewati penyedia yang kamu pilih lewat key-mu sendiri (bagian Pihak yang menerima data).",
          "Kami tidak menjual datamu dan tidak memasang iklan. Situs ini tidak memakai pelacak iklan atau analitik pihak ketiga.",
        ],
      ],
    },
    {
      id: "data-yang-diproses",
      title: "Data yang kami proses",
      blocks: [
        [
          "Akun: dikelola Clerk (mis. email, nama, metode masuk, sesi). Di basis data MALAS hanya tersimpan id pengguna dari Clerk.",
          "Isian makalah: judul, mata kuliah, nama dosen, nama dan NIM penyusun, kelas, universitas, fakultas, jurusan, kota, tahun, dan template yang dipilih.",
          "Logo (opsional): gambar kampus atau sekolah yang kamu unggah, disimpan satu per akun sebagai PNG yang sudah dibersihkan (metadata gambar dibuang) sampai kamu menghapusnya.",
          "Hasil: berkas .docx, log tahap proses, statistik pemakaian (jumlah panggilan dan token), serta pesan error bila gagal.",
          "Kuota: id pengguna, tanggal, dan jumlah makalah nyata hari itu. Catatan kuota ini tidak ikut terhapus otomatis bersama riwayat makalah.",
          "Teknis: log dasar server oleh penyedia hosting (permintaan dan galat). Isi makalahmu tidak dicetak ke log aplikasi.",
          "Di browsermu: draf formulir (tanpa API key) dan preferensi tema di penyimpanan lokal, serta cookie sesi Clerk untuk login.",
        ],
      ],
    },
    {
      id: "api-key",
      title: "API key",
      blocks: [
        [
          "Key dikirim lewat HTTPS saat kamu membuat makalah, hanya disimpan di memori server selama prosesnya, dan dibuang setelah makalah selesai, gagal, atau dibatalkan. Key tidak ditulis ke disk atau log, dan dibersihkan dari pesan error.",
          "Penyimpanan key bersifat opsional dan hanya berlaku bila fitur itu aktif di layanan dan kamu memilihnya. Key disimpan terenkripsi, tidak pernah ditampilkan kembali, dan bisa kamu hapus kapan saja di Pengaturan.",
        ],
        "Batas yang jujur: kami tidak bisa menjamin string terhapus seketika dari memori. Karena itu pakai key khusus dengan batas kredit kecil dan cabut setelah selesai.",
      ],
    },
    {
      id: "pihak-penerima",
      title: "Pihak yang menerima data",
      blocks: [
        [
          "Penyedia model bahasa pilihanmu (OpenRouter atau Kenari): menerima key-mu dan isi yang dikirim ke model, yaitu judul, mata kuliah, tahun, kota, nama dosen dan nama penyusun (untuk kata pengantar), serta bagian makalah yang sedang disusun. NIM, kelas, universitas, fakultas, dan jurusan tidak dikirim. Penyedia itu punya kebijakan sendiri.",
          "Logo yang kamu unggah tidak dikirim ke penyedia model bahasa maupun layanan lain; ia hanya disimpan di basis data kami dan ditanam ke berkas .docx-mu.",
          "Layanan pencarian literatur (Crossref, Semantic Scholar, arXiv): menerima kata kunci yang diturunkan dari judulmu untuk mencari referensi.",
          "Clerk: mengelola akun dan login.",
          "Neon (basis data), Hugging Face (server API), dan Netlify (situs web): menyimpan atau meneruskan data yang disebut di atas sebagai penyedia infrastruktur.",
        ],
        "Kami tidak membagikan datamu ke pihak lain di luar itu, kecuali bila diwajibkan hukum.",
      ],
    },
    {
      id: "penyimpanan-dan-penghapusan",
      title: "Berapa lama disimpan dan cara menghapus",
      blocks: [
        [
          "Makalah, berkas, dan log dihapus otomatis 48 jam setelah selesai atau gagal. Kamu juga bisa menghapusnya sendiri dari dasbor kapan saja.",
          "Makalah yang masih mengantre atau berjalan tidak dihapus sampai selesai.",
          "Logo tersimpan sampai kamu menghapusnya (di halaman Buat makalah atau Pengaturan). Menghapus akun juga menghapusnya.",
          "Catatan kuota harian disimpan lebih lama. Untuk menghapusnya, atau menghapus akunmu, hubungi kami lewat kontak di bawah.",
        ],
      ],
    },
    {
      id: "keamanan",
      title: "Keamanan",
      blocks: [
        "Koneksi memakai HTTPS. Riwayat tiap akun terpisah; makalah milik orang lain tidak bisa dibuka. Tidak ada sistem yang sepenuhnya aman, jadi jangan memasukkan data yang tidak ingin kamu bagikan ke penyedia model bahasa.",
      ],
    },
    {
      id: "perubahan-dan-kontak",
      title: "Perubahan dan kontak",
      blocks: [
        `Kebijakan ini bisa berubah dan perubahan penting diumumkan di situs. Pertanyaan atau permintaan hapus data: buka isu di ${CONTACT_URL}.`,
      ],
    },
  ],
};

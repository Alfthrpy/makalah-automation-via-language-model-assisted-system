"""Daftar tahap pipeline MALAS (dipakai flow dan web UI agar selalu sinkron)."""

# (kunci, label singkat, penjelasan)
STEPS = [
    ("input", "Memuat data", "Membaca data makalah dan penyusun"),
    ("outline", "Outline & referensi", "Menyusun bab/sub-bab dan mencari referensi akademik"),
    ("fulltext", "Full-text referensi", "Mengunduh isi paper open-access (tanpa LLM)"),
    ("tulis", "Menulis sub-bab", "Menulis isi tiap sub-bab dengan sitasi APA"),
    ("sitasi", "Verifikasi sitasi", "Mencocokkan sitasi dengan daftar pustaka"),
    ("pengantar", "Kata pengantar", "Menulis kata pengantar"),
    ("docx", "Membuat dokumen", "Merender ke template Word (.docx)"),
]
STEP_KEYS = [k for k, _, _ in STEPS]

# Makalah Automation via Language-model Assisted System (MALAS)
MALAS (Makalah Automation via Language-model Assisted System) is a project designed to automate the process of writing academic papers ("makalah" in Indonesian). By leveraging a multi-agent system built with the `crewAI` framework, MALAS streamlines the entire workflow from research and content generation to final formatting. This system aims to assist users in producing well-structured and comprehensive academic documents efficiently.

## Fitur

- **Riset Otomatis**: Mengumpulkan informasi relevan dari web berdasarkan topik yang diberikan.
- **Penulisan Konten**: Menghasilkan draf konten untuk setiap bagian makalah (Pendahuluan, Pembahasan, Kesimpulan).
- **Struktur Dokumen**: Menyusun hasil akhir dalam format Markdown yang terstruktur.
- **Sistem Multi-Agen**: Menggunakan agen-agen khusus (Peneliti, Penulis, Peninjau) untuk menangani tugas-tugas spesifik.

## Instalasi

### Prasyarat
- Python 3.8+
- API Key dari penyedia LLM yang didukung (misalnya, OpenAI, Groq).

### Langkah-langkah
1.  **Clone repository ini:**
    ```bash
    git clone https://github.com/your-username/malas.git
    cd malas
    ```

2.  **Buat dan aktifkan virtual environment (disarankan):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Di Windows, gunakan `venv\Scripts\activate`
    ```

3.  **Instal dependensi yang diperlukan:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment Variables:**
    Buat file `.env` di direktori root proyek dan tambahkan API key Anda.
    ```env
    # Contoh untuk OpenAI
    OPENAI_API_KEY="ganti_dengan_api_key_anda"

    # Contoh untuk Groq
    # GROQ_API_KEY="ganti_dengan_api_key_anda"
    ```

## ⚠️ Coming soon!

> Masih dalam tahap pengembangan!
# dummy_factory.py (atau di file yang sama)

from pydantic import BaseModel
from typing import Type

from malas.crews.models.TaskOutput import Outline, ReferenceItem, References, Subbab


def create_dummy_instance(model_class: Type[BaseModel]) -> BaseModel:
    """
    Factory function to create a dummy instance of a given Pydantic model class.
    """
    print(f"--- [Factory] Membuat dummy instance untuk {model_class.__name__} ---")
    
    if model_class == Outline:
        return Outline(
            subbabs={
                "Bab 1: Pendahuluan": Subbab(
                    sections=[
                        "1.1 Latar Belakang",
                        "1.1.1 Konteks Umum (mengapa topik ini penting)",
                        "1.1.2 Identifikasi Masalah (celah penelitian atau masalah praktis)",
                        "1.1.3 Urgensi Penelitian (mengapa masalah ini perlu diteliti segera)",
                        "1.2 Rumusan Masalah",
                        "1.2.1 Pertanyaan Penelitian Utama",
                        "1.2.2 Pertanyaan Penelitian Pendukung (jika ada)",
                        "1.3 Tujuan Penulisan",
                        "1.3.1 Tujuan Utama Penelitian",
                        "1.3.2 Tujuan Spesifik Penelitian (berdasarkan rumusan masalah)",
                    ]
                ),
                "Bab 2: Pembahasan": Subbab(
                    sections=[
                        "2.1 Landasan Teori",
                        "2.1.1 Definisi Konsep Kunci (definisi dari para ahli dan sumber terpercaya)",
                        "2.1.2 Teori yang Relevan (teori-teori yang mendasari penelitian)",
                        "2.1.3 Kerangka Konseptual (bagaimana konsep-konsep terkait saling berhubungan)",
                        "2.2 Analisis dan Interpretasi Data/Informasi",
                        "2.2.1 Deskripsi Data/Informasi yang Digunakan (sumber data, metode pengumpulan)",
                        "2.2.2 Analisis Data/Informasi (menggunakan metode yang sesuai)",
                        "2.2.3 Interpretasi Hasil Analisis (makna dari hasil analisis)",
                        "2.3 Studi Kasus/Contoh (jika relevan)",
                        "2.3.1 Deskripsi Studi Kasus/Contoh",
                        "2.3.2 Analisis Studi Kasus/Contoh (kaitkan dengan teori dan data)",
                        "2.4 Implikasi Penelitian",
                        "2.4.1 Implikasi Teoretis (kontribusi terhadap pengembangan teori)",
                        "2.4.2 Implikasi Praktis (manfaat bagi praktisi atau pembuat kebijakan)",
                        "2.5 Tantangan dan Keterbatasan Penelitian",
                        "2.5.1 Identifikasi Tantangan",
                        "2.5.2 Batasan Metodologi",
                        "2.5.3 Potensi Penelitian Lanjutan",
                    ]
                ),
                "Bab 3: Penutup": Subbab(
                    sections=[
                        "3.1 Kesimpulan",
                        "3.1.1 Ringkasan Temuan Utama (jawab pertanyaan penelitian)",
                        "3.1.2 Implikasi Temuan (dampak dari temuan penelitian)",
                        "3.2 Saran",
                        "3.2.1 Saran untuk Penelitian Lanjutan",
                        "3.2.2 Saran Praktis (rekomendasi tindakan berdasarkan temuan)",
                    ]
                ),
            }
        )
    elif model_class == References:
        return References(
            references=[
                ReferenceItem(title="Buku Referensi Auto-Generated 1", authors=["Penulis A"], year=2023,link="https://contohlink.com"),
                ReferenceItem(title="Jurnal Referensi Auto-Generated 2", authors=["Penulis B"], year=2024,link="https://contohlink.com"),
                ReferenceItem(title="Jurnal Referensi Auto-Generated 3", authors=["Penulis c"], year=2024,link="https://contohlink.com"),
                ReferenceItem(title="Jurnal Referensi Auto-Generated 4", authors=["Penulis D"], year=2024,link="https://contohlink.com"),
                ReferenceItem(title="Jurnal Referensi Auto-Generated 5", authors=["Penulis E"], year=2024,link="https://contohlink.com"),
                ReferenceItem(title="Jurnal Referensi Auto-Generated 6", authors=["Penulis F"], year=2024,link="https://contohlink.com"),
            ]
        )
    
    # Tambahkan model lain di sini jika ada
    # elif model_class == ModelLain:
    #     return ModelLain(...)

    else:
        # Jika model tidak dikenali, berikan error yang jelas
        raise TypeError(f"Tidak ada pabrik dummy yang terdefinisi untuk model: {model_class.__name__}")
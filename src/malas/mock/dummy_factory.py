# dummy_factory.py (atau di file yang sama)

from pydantic import BaseModel
from typing import Dict, Optional, Type

from malas.crews.models.TaskOutput import Outline, ReferenceItem, References, SimpleSubbab, SubBab, ContentText, ContentList


def create_dummy_instance(model_class: Type[BaseModel],context: Optional[Dict] = None) -> BaseModel:
    """
    Factory function to create a dummy instance of a given Pydantic model class.
    """
    print(f"--- [Factory] Membuat dummy instance untuk {model_class.__name__} ---")
    
    if model_class == Outline:
        return Outline(
            subbabs={
                "Bab 1: Pendahuluan": SimpleSubbab(
                    sections=[
                        "1.1 Latar Belakang",
                        "1.2 Rumusan Masalah",
                        "1.3 Tujuan Penulisan",
                    ]
                ),
                "Bab 2: Pembahasan": SimpleSubbab(
                    sections=[
                        "2.1 Landasan Teori",
                        "2.2 Analisis dan Interpretasi Data/Informasi",
                        "2.3 Studi Kasus/Contoh",
                        "2.4 Implikasi Penelitian",
                        "2.5 Tantangan dan Keterbatasan Penelitian",
                        "2.5.3 Potensi Penelitian Lanjutan",
                    ]
                ),
                "Bab 3: Penutup": SimpleSubbab(
                    sections=[
                        "3.1 Kesimpulan",
                        "3.2 Saran",
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
    elif model_class == SubBab:
        judul_dinamis = context.get('subbab_now', 'Judul Dummy Tidak Ditemukan')
        bab_now = context.get('bab_now', 'Bab Dummy Tidak Ditemukan')
        konten_paragraf_1 = ContentText(
            isi=f"Ini adalah paragraf pengantar dummy untuk {judul_dinamis}. "
                "Teks ini menjelaskan konteks umum dari topik yang akan dibahas secara naratif.",
                type="text"
            
        )
        
        konten_list_poin = ContentList(
            title_items="Berikut adalah poin-poin utama permasalahan:",
            items=[
                "Poin pertama yang mengidentifikasi celah penelitian.",
                "Poin kedua yang menyoroti urgensi dari masalah.",
                "Poin ketiga yang berkaitan dengan dampak praktis.",
            ],
            type="list"
        )
        
        konten_paragraf_2 = ContentText(
            isi="Paragraf penutup ini menyimpulkan poin-poin di atas dan "
                "mengarahkan pembaca ke bagian selanjutnya dari makalah."
        )
        return SubBab(
            judul=f"{bab_now}",
            content=[konten_paragraf_1, konten_list_poin, konten_paragraf_2]
        )
    
    # Tambahkan model lain di sini jika ada
    # elif model_class == ModelLain:
    #     return ModelLain(...)

    else:
        # Jika model tidak dikenali, berikan error yang jelas
        raise TypeError(f"Tidak ada pabrik dummy yang terdefinisi untuk model: {model_class.__name__}")
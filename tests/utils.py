import copy
from types import SimpleNamespace

def to_dict(obj):
    """
    Mengubah SimpleNamespace DAN dict yang bersarang menjadi dict murni.
    """
    if isinstance(obj, SimpleNamespace):
        # Jika objek adalah SimpleNamespace, ubah jadi dict dan proses isinya
        return {k: to_dict(v) for k, v in vars(obj).items()}
    
    # <-- TAMBAHAN KRUSIAL DI SINI
    elif isinstance(obj, dict):
        # Jika objek adalah dict, proses setiap nilai di dalamnya
        return {k: to_dict(v) for k, v in obj.items()}
    
    elif isinstance(obj, list):
        # Jika objek adalah list, proses setiap elemen di dalamnya
        return [to_dict(elem) for elem in obj]
    else:
        # Jika bukan semuanya, kembalikan apa adanya
        return obj
    

def transform_structure(makalah_data, chapter_key="I"):
    """
    Mengubah struktur konten dari satu bab spesifik (default: Bab "I")
    menjadi SimpleNamespace yang ringkas, tanpa menyentuh bab lain.
    """
    # 1. Buat salinan data yang aman untuk diubah
    data_copy = copy.deepcopy(makalah_data)

    # 2. Cek dulu apakah bab yang dituju ada di dalam data
    if "bab" not in data_copy or chapter_key not in data_copy["bab"]:
        print(f"Peringatan: Bab '{chapter_key}' tidak ditemukan. Tidak ada perubahan dilakukan.")
        return data_copy

    # Mapping nama atribut (hanya untuk Bab I)
    key_map = {
        "Latar Belakang": "latar_belakang",
        "Rumusan Masalah": "rumusan_masalah",
        "Tujuan Penulisan": "tujuan"
    }
    
    # 3. Ambil data bab spesifik yang akan diubah
    chapter_dict = data_copy["bab"][chapter_key]
    transformed_chapter = SimpleNamespace()

    # Salin properti utama bab (seperti judul)
    for key, value in chapter_dict.items():
        if key != 'subbab':
            setattr(transformed_chapter, key, value)
            
    # 4. Proses sub-bab dari bab yang ditargetkan ini
    for subbab in chapter_dict.get("subbab", []):
        judul_subbab = subbab.get("judul", "")
        attribute_key = None
        
        for formal_name, attr_name in key_map.items():
            if formal_name in judul_subbab:
                attribute_key = attr_name
                break
        
        if not attribute_key:
            # Fallback jika tidak ada di map
            cleaned_title = ' '.join(judul_subbab.split(' ')[1:])
            attribute_key = cleaned_title.lower().replace(' ', '_').strip()

        # Gabungkan konten menjadi satu string ringkas
        content_parts = []
        for content_item in subbab.get("content", []):
            if content_item.get("type") == "text":
                content_parts.append(content_item.get("isi", ""))
            elif content_item.get("type") == "list":
                if content_item.get("title_items"):
                    content_parts.append(content_item.get("title_items"))
                for item in content_item.get("items", []):
                    content_parts.append(f"- {item}")
        
        final_content = "\n".join(content_parts)
        setattr(transformed_chapter, attribute_key, final_content)

    # 5. Ganti bab lama dengan bab yang sudah ditransformasi di dalam data
    data_copy["bab"][chapter_key] = transformed_chapter
    
    return data_copy
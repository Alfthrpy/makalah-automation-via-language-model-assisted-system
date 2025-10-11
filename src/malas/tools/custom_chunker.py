from crewai_tools.rag.chunkers.base_chunker import BaseChunker
from chonkie import SentenceChunker # Pastikan chonkie sudah terinstal

class ChonkieChunker(BaseChunker):
    """
    Chunker custom yang menggunakan library Chonkie di belakang layar
    dan mengadaptasi outputnya agar sesuai dengan ekspektasi RagAdapter.
    """
    def __init__(self):
        # Inisialisasi chunker dari Chonkie sekali saja saat objek dibuat
        self.chonkie = SentenceChunker(tokenizer_or_token_counter = 'character')

    def chunk(self, content: str) -> list[str]:
        """
        Menerima konten teks, memotongnya dengan Chonkie, lalu
        mengembalikan daftar string teks saja.
        """
        print(">>> Menggunakan ChonkieChunker untuk memotong teks... <<<")
        
        # 1. Panggil Chonkie untuk mendapatkan daftar objek Chunk
        chunks_from_chonkie = self.chonkie.chunk(content)
        
        print(f"Chonkie menghasilkan {len(chunks_from_chonkie)} chunk.")
        
        text_chunks = [chunk.text for chunk in chunks_from_chonkie]
        with open (file='D:/CODING/PYTHON/AGENTIC AI/malas/tests/chonkie_result.txt',mode='w',encoding='utf-8') as file:
            file.write('=====CHUNK====='.join(text_chunks))
        return text_chunks
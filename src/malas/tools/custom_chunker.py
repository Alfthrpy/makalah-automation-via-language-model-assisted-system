from crewai_tools.rag.chunkers.base_chunker import BaseChunker
from chonkie import SentenceChunker

import tiktoken


tokenizer = tiktoken.get_encoding("gpt2")
class ChonkieChunker(BaseChunker):
    """
    Chunker custom yang menggunakan library Chonkie di belakang layar
    dan mengadaptasi outputnya agar sesuai dengan ekspektasi RagAdapter.
    """
    def __init__(self):
        # Inisialisasi chunker dari Chonkie sekali saja saat objek dibuat

        self.chonkie = SentenceChunker(
    tokenizer_or_token_counter=tokenizer,     # Default tokenizer (or use "gpt2", etc.)
    chunk_size=512,           # Maximum tokens per chunk
    chunk_overlap=32,         # Overlap between chunks
    min_sentences_per_chunk=1  # Minimum sentences in each chunk
)

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
        return text_chunks
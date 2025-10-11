from crewai_tools.rag.data_types import DataType

from malas.tools.custom_chunker import ChonkieChunker



class CustomPdfHandler:
    def get_loader(self):
        # Tetap pakai loader PDF bawaan
        return DataType.PDF_FILE.get_loader()
        
    def get_chunker(self):
        # Kembalikan chunker CHONKIE baru kita!
        return ChonkieChunker()


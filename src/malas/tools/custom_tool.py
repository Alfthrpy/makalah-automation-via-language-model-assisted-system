from crewai.tools import BaseTool
from crewai_tools import RagTool
from typing import Type
from pydantic import BaseModel, Field
from langchain_community.tools import DuckDuckGoSearchResults
import requests
from pathlib import Path
from crewai_tools.adapters.crewai_rag_adapter import CrewAIRagAdapter
from crewai.rag.chromadb.config import ChromaDBConfig
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai_tools.rag.data_types import DataType
import trafilatura
from chromadb.config import Settings



class DuckDuckGoToolInput(BaseModel):
    """Input schema for DuckDuckGoSearchTool."""
    query: str = Field(..., description="The search query to run on DuckDuckGo.")


class DuckDuckGoSearchTool(BaseTool):
    name: str = "DuckDuckGo Search Tool"
    description: str = (
        "Useful for searching information on the internet using DuckDuckGo. "
        "Provide a query and it will return top search results."
    )
    args_schema: Type[BaseModel] = DuckDuckGoToolInput

    def _run(self, query: str) -> list[dict]:
        search = DuckDuckGoSearchResults(max_results=3)
        raw = search.run(query)  # string mentah
        results = []
    
        # contoh sederhana split tiap line, parse title, url, snippet
        for line in raw.split("\n"):
            if "title:" in line and "link:" in line:
                results.append({
                    "judul": line.split("title:")[1].split(",")[0].strip(),
                    "url": line.split("link:")[1].strip(),
                    "tahun": None,  # bisa parse dari snippet jika ada
                    "penulis": None
                })
        return results


class ReferenceFinderTool(BaseTool):
    name: str = "Reference Finder Tool"
    description: str = (
        "Gunakan untuk mencari referensi akademik (artikel jurnal, prosiding, buku) "
        "berdasarkan topik atau kata kunci."
    )

    def _run(self, query: str) -> str:
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": 5}  # ambil 5 teratas
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            items = res.json()["message"]["items"]

            results = []
            for item in items:
                title = item.get("title", ["No title"])[0]
                author = ", ".join([a.get("family", "") for a in item.get("author", [])[:3]])
                year = item.get("issued", {}).get("date-parts", [[None]])[0][0]
                doi = item.get("DOI", "")
                results.append(f"{title} ({year}) - {author} | DOI: {doi}")

            return "\n".join(results) if results else "Tidak ada referensi ditemukan."
        except Exception as e:
            return f"Error mencari referensi: {e}"
        


class ResearchExtractorTool(BaseTool):
    name: str = "Research Extractor Tool"
    description: str = (
        "Ekstrak konten dari artikel online (misalnya berita, jurnal, blog). "
        "Masukkan URL artikel."
    )

    def _run(self, url: str) -> str:
        try:
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded)
            return text[:500] if text else "Konten tidak bisa diekstrak."
        except Exception as e:
            return f"Error mengambil konten: {e}"
        


class PaperRagTool(BaseTool):
    """
    Sebuah tool RAG custom untuk mencari informasi dari 
    database paper ilmiah lokal.
    """
    name: str = "Scientific Paper Knowledge Base"
    description: str = (
        "Searches a local knowledge base of scientific papers for relevant information. "
        "The input to this tool should be a specific question or topic to search for."
    )
    _rag_tool: RagTool  # Menyimpan instance RagTool internal

    def __init__(self, 
                 collection_name: str = "paper_knowledge_base",
                 model_name: str = 'sentence-transformers/distiluse-base-multilingual-cased-v2',
                 cache_dir: str = 'D:/MODELS'):
        """
        Inisialisasi tool dengan setup RAG lengkap di dalamnya.
        """
        super().__init__()
        print(f"Initializing Knowledge Base with collection: '{collection_name}'...")
        
        embedding_function = SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            cache_folder=cache_dir
        )
        
        chroma_config = ChromaDBConfig(
            embedding_function=embedding_function
        )
        
        my_adapter = CrewAIRagAdapter(
            config=chroma_config,
            collection_name=collection_name,
        )
        
        # Simpan RagTool yang sudah dikonfigurasi sebagai atribut internal
        self._rag_tool = RagTool(adapter=my_adapter)
        print("Knowledge Base ready.")

    def add_paper(self, pdf_path: str | Path, data_type : DataType = DataType.PDF_FILE) -> None:
        """
        Metode untuk menambahkan paper (PDF) ke dalam knowledge base.
        Ini dipanggil oleh Anda (developer), bukan oleh agent.
        """
        print(f"Adding paper '{pdf_path}' to the knowledge base...")
        # Gunakan tool internal untuk menambahkan data
        self._rag_tool.add(
            str(pdf_path),  # Pastikan path dalam format string
            data_type=data_type
        )
        print("Paper added successfully.")

    def _run(self, query: str, similarity_threshold : float) -> str:
        """
        Metode yang akan dijalankan oleh agent CrewAI.
        """
        print(f"\nSearching knowledge base for: '{query}'")
        return self._rag_tool.run(
            query,
            limit=3,
            similarity_threshold = similarity_threshold
        )
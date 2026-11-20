from crewai.tools import BaseTool
from typing import Type, Any
from pydantic import BaseModel, Field, PrivateAttr
from langchain_community.tools import DuckDuckGoSearchResults
import requests
import trafilatura
import re



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
        raw = search.run(query)
        results = []
        
        # Regex untuk menangkap url
        url_pattern = r'(https?://[^\s,]+)'
        
        for line in raw.split("\n"):
            if "title:" in line and "link:" in line:
                # Ambil title
                title = line.split("title:")[1].split(",")[0].strip()
                # Ambil url dengan regex agar tidak kecampur snippet
                match = re.search(url_pattern, line)
                url = match.group(0) if match else None

                results.append({
                    "judul": title,
                    "url": url,
                    "tahun": None,
                    "penulis": None
                })
        return results


class ReferenceFinderToolInput(BaseModel):
    """Input schema for ReferenceFinderTool."""
    query: str = Field(..., description="Kata kunci pencarian referensi akademik (jurnal, prosiding, buku, semua bidang ilmu).")

class ReferenceFinderTool(BaseTool):
    name: str = "Reference Finder Tool"
    description: str = (
        "Cari referensi akademik lintas bidang ilmu (jurnal, prosiding, buku) via CrossRef. "
        "Cocok untuk topik non-teknis/non-sains yang tidak tercakup di Arxiv. "
        "Mengembalikan judul, penulis, tahun, abstract (jika tersedia), dan DOI."
    )
    args_schema: Type[BaseModel] = ReferenceFinderToolInput

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
                link = f"https://doi.org/{doi}" if doi else ""
                raw_abstract = item.get("abstract")
                abstract = re.sub(r"<[^>]+>", "", raw_abstract).strip() if raw_abstract else "Abstract tidak tersedia."
                results.append(
                    f"Title: {title}\nAuthors: {author}\nYear: {year}\nAbstract: {abstract}\nLink: {link}"
                )

            return "\n\n".join(results) if results else "Tidak ada referensi ditemukan."
        except Exception as e:
            return f"Error mencari referensi: {e}"



class SemanticScholarToolInput(BaseModel):
    """Input schema for SemanticScholarTool."""
    query: str = Field(..., description="Query pencarian paper akademis, sebaiknya Bahasa Inggris. Mencakup semua bidang ilmu (sains, sosial, humaniora, kedokteran, dll).")

class SemanticScholarTool(BaseTool):
    """
    Tool pencarian paper via Semantic Scholar Graph API (tanpa API key).
    Cakupan lintas bidang ilmu, tidak terbatas pada sains/teknik seperti Arxiv.
    """
    name: str = "Semantic Scholar Search Tool"
    description: str = (
        "Cari paper akademis di semua bidang ilmu (sains, sosial, humaniora, kedokteran, ekonomi, dll) "
        "via Semantic Scholar. Gunakan untuk topik yang tidak tercakup di Arxiv. "
        "Mengembalikan judul, penulis, tahun, abstract, dan link untuk tiap hasil."
    )
    args_schema: Type[BaseModel] = SemanticScholarToolInput

    def _run(self, query: str, max_results: int = 3) -> str:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,authors,year,abstract,url",
        }
        try:
            res = requests.get(url, params=params, timeout=10)
            res.raise_for_status()
            papers = res.json().get("data", [])

            if not papers:
                return "Tidak ada paper ditemukan di Semantic Scholar."

            results = []
            for p in papers:
                title = p.get("title", "No title")
                authors = ", ".join(a.get("name", "") for a in p.get("authors", [])[:3])
                year = p.get("year", "N/A")
                abstract = p.get("abstract") or "Abstract tidak tersedia."
                link = p.get("url", "")
                results.append(
                    f"Title: {title}\nAuthors: {authors}\nYear: {year}\nAbstract: {abstract}\nLink: {link}"
                )
            return "\n\n".join(results)
        except Exception as e:
            return f"Error mencari paper di Semantic Scholar: {e}"


class ResearchExtractorTool(BaseTool):
    name: str = "Research Extractor Tool"
    description: str = (
        "Ekstrak konten dari artikel online (misalnya berita, jurnal, blog). "
        "Masukkan URL artikel."
    )

    def _run(self, url: str) -> str:
        try:
            print(f"searching content from: {url}...")
            downloaded = trafilatura.fetch_url(url)
            text = trafilatura.extract(downloaded)
            return text
        except Exception as e:
            return f"Error mengambil konten: {e}"
        


# === LIMITED ARXIV TOOL ===

class LimitedArxivToolInput(BaseModel):
    """Input schema for LimitedArxivTool."""
    search_query: str = Field(..., description="Query pencarian paper di Arxiv (WAJIB dalam Bahasa Inggris)")


class LimitedArxivTool(BaseTool):
    """
    Wrapper ArxivPaperTool yang membatasi results per panggilan.
    Tidak ada hard limit total calls - diserahkan ke task description.
    PDF tidak di-download - cukup metadata + abstract untuk context langsung ke penulis,
    hanya cocok untuk topik sains/teknik/matematika (cakupan Arxiv).
    """
    name: str = "Arxiv Paper Search Tool"
    description: str = (
        "Cari paper akademis dari Arxiv (khusus bidang sains, teknik, matematika, komputer). "
        "Setiap panggilan mengembalikan TEPAT 2 paper beserta abstract-nya. "
        "Gunakan 1x per sub-bab saja untuk efisiensi. "
        "Untuk topik non-sains/teknik gunakan Semantic Scholar atau Reference Finder Tool."
    )
    args_schema: Type[BaseModel] = LimitedArxivToolInput

    _arxiv_tool: Any = PrivateAttr()
    _results_per_call: int = PrivateAttr()
    _call_count: int = PrivateAttr(default=0)  # untuk logging saja

    def __init__(self, results_per_call: int = 2):
        super().__init__()
        from crewai_tools import ArxivPaperTool
        self._arxiv_tool = ArxivPaperTool(
            download_pdfs=False,
            use_title_as_filename=False
        )
        self._results_per_call = results_per_call
        self._call_count = 0
    
    def _run(self, search_query: str) -> str:
        self._call_count += 1
        print(f"📚 Arxiv Search [call #{self._call_count}]: {search_query}")
        
        # Paksa results sesuai config
        result = self._arxiv_tool._run(search_query=search_query, max_results=self._results_per_call)
        return result

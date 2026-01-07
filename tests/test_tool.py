
from crewai_tools import RagTool
from crewai_tools.adapters.crewai_rag_adapter import CrewAIRagAdapter
from crewai.rag.chromadb.config import ChromaDBConfig
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai_tools.rag.data_types import DataType
from malas.tools.custom_pdf_handler import CustomPdfHandler
from malas.tools.custom_tool import DuckDuckGoSearchTool, PaperRagTool, ResearchExtractorTool
# from tests.utils import DocxConverter


# tool = ArxivPaperTool(
#     download_pdfs=True, 
#     save_dir="../references",
#     use_title_as_filename=False
# )


my_custom_handler = CustomPdfHandler()
knowledge_base = PaperRagTool(collection_name='baru')
knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/arxiv_pdfs/1909_01727v1.pdf')
result = knowledge_base._run('As the strength of Large Language Models (LLMs) has grown over',similarity_threshold=0.5,limit=3)
print(result)


# docx_converter = DocxConverter("template/template makalah.docx",hardcoded=True)
# docx_converter.convert(None)
# search_tool = DuckDuckGoSearchTool()
# extractor_tool = ResearchExtractorTool()
# result = search_tool._run("What is CrewAI?")
# print(result)
# extracted = extractor_tool._run(result[0]['url'])
# print(extracted)


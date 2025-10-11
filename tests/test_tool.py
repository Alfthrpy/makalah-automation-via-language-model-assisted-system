from crewai_tools import ArxivPaperTool
from crewai_tools import RagTool
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from crewai_tools.adapters.crewai_rag_adapter import CrewAIRagAdapter
from crewai.rag.chromadb.config import ChromaDBConfig
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai_tools.rag.data_types import DataType

from malas.tools.custom_pdf_handler import CustomPdfHandler
from malas.tools.custom_tool import PaperRagTool


tool = ArxivPaperTool(
    download_pdfs=True, 
    save_dir="../references",
    use_title_as_filename=False
)


# model_name = 'sentence-transformers/distiluse-base-multilingual-cased-v2'
# cache_dir = 'D:/MODELS'


# embedding_function = SentenceTransformerEmbeddingFunction(
#     model_name=model_name,
#     cache_folder=cache_dir
# )

# chroma_config = ChromaDBConfig(
#     embedding_function=embedding_function
# )


# my_adapter = CrewAIRagAdapter(
#     config=chroma_config,
#     collection_name="new_embedding", # Beri nama koleksi
# )

# rag_tool = RagTool(adapter=my_adapter)
# rag_tool.add("D:/CODING/PYTHON/AGENTIC AI/malas/references/2503_18238v2.pdf", data_type=DataType.PDF_FILE)

# result = rag_tool.run('how agentic work',limit=1,similarity_threshold=0.6)
# print(result)


my_custom_handler = CustomPdfHandler()
knowledge_base = PaperRagTool(collection_name='baru')
knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/references/2503_18238v2.pdf',data_type=my_custom_handler)
# knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/references/2502_18359v1.pdf',data_type=my_custom_handler)
# knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/references/2507_10571v3.pdf',data_type=my_custom_handler)
result = knowledge_base._run('what is an agentic AI architecture',similarity_threshold=0.3)
with open (file='result.txt',mode='w' ) as file:
    file.write(result)
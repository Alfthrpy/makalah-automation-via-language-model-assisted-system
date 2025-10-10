from crewai_tools import ArxivPaperTool
from crewai_tools import RagTool
from transformers import AutoTokenizer, AutoModel
from sentence_transformers import SentenceTransformer
from crewai_tools.adapters.crewai_rag_adapter import CrewAIRagAdapter
from crewai.rag.chromadb.config import ChromaDBConfig
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from crewai_tools.rag.data_types import DataType




tool = ArxivPaperTool(
    download_pdfs=True, 
    save_dir="../references",
    use_title_as_filename=False
)


model_name = 'sentence-transformers/distiluse-base-multilingual-cased-v2'
cache_dir = 'D:/MODELS'


embedding_function = SentenceTransformerEmbeddingFunction(
    model_name=model_name,
    cache_folder=cache_dir
)

chroma_config = ChromaDBConfig(
    embedding_function=embedding_function
)


my_adapter = CrewAIRagAdapter(
    config=chroma_config,
    collection_name="new_embedding", # Beri nama koleksi
)

rag_tool = RagTool(adapter=my_adapter)
rag_tool.add("D:/CODING/PYTHON/AGENTIC AI/malas/references/2503_18238v2.pdf", data_type=DataType.PDF_FILE)

result = rag_tool.run('how agentic work',limit=1,similarity_threshold=0.6)
print(result)

with open (file='result.txt',mode='w' ) as file:
    file.write(result)
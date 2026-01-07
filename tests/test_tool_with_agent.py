# Create an agent

from malas.tools.custom_pdf_handler import CustomPdfHandler
from malas.tools.custom_tool import PaperRagTool
from crewai import Agent,LLM

my_custom_handler = CustomPdfHandler()
knowledge_base = PaperRagTool(collection_name='menggokil')
# knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/arxiv_pdfs/1511_05263v4.pdf', data_type=my_custom_handler)
# knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/arxiv_pdfs/1803_08503v1.pdf', data_type=my_custom_handler)
knowledge_base.add_paper('D:/CODING/PYTHON/AGENTIC AI/malas/arxiv_pdfs/Specialist Data Engineering 2025.pdf', data_type=my_custom_handler)

llm = LLM(model='gemini/gemini-2.0-flash')

researcher = Agent(
    role="Data Engineering Expert & Technical Mentor",
    goal="Help the user understand and answer questions about data engineering concepts using the provided learning materials.",
    backstory=(
        "You are an experienced Data Engineer with deep knowledge in data warehousing, ETL pipelines, data governance, "
        "OLAP/OLTP systems, data modeling, and modern data stack tooling. "
        "You have access to a curated learning knowledge base containing PDF materials about data engineering. use lower threshold if needed."
        "Your purpose is to act as a mentor—explaining concepts clearly, answering questions with references to the provided documents, "
        "and guiding the user step-by-step in developing strong data engineering understanding."
    ),
    tools=[knowledge_base],   # pastikan ini instance, bukan class
    verbose=True,
    llm=llm,
)


# Use kickoff() to interact directly with the agent
result = researcher.kickoff("what is data warehouse?")
print(result.raw)
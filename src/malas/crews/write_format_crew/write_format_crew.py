from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
import os
import glob
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

from malas.crews.models.TaskOutput import SubBab
from malas.mock.mock_llm import AutoFakeLLM
from malas.tools.custom_tool import ResearchExtractorTool, PaperRagTool, DuckDuckGoSearchTool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

MOCKUP = True
if MOCKUP:
    llm = AutoFakeLLM(model_name='gpt-6')
else:
    llm = LLM(model='gemini/gemini-2.0-flash')

# Instantiate tools
paper_rag = PaperRagTool(
    collection_name="paper_knowledge_base"
)
search_tool = DuckDuckGoSearchTool()


@CrewBase
class WriteFormatCrew():
    """WriteFormatCrew crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def content_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_writer'], # type: ignore[index]
            verbose=True,
            llm=llm,
        )

    # @agent
    # def quality_reviewer(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config['quality_reviewer'], # type: ignore[index]
    #         llm=llm,
    #         verbose=True,
    #     )


    @task
    def write_content(self) -> Task:
        return Task(
            config=self.tasks_config['write_content_task'], # type: ignore[index]
            tools=[paper_rag, search_tool],
            output_pydantic=SubBab
        )

    # @task
    # def review_content(self) -> Task:
    #     return Task(
    #         config=self.tasks_config['review_content_task'], # type: ignore[index]
    #         output_pydantic=SubBab
    #     )


    @crew
    def crew(self) -> Crew:
        """Creates the WriteFormatCrew crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            output_log_file="logs/write_format_crew.json",
            max_rpm=10
        )

    @before_kickoff
    def ingest_pdfs(self, inputs):
        """
        Sebelum crew berjalan, scan folder arxiv_pdfs dan masukkan semua PDF
        ke dalam knowledge base PaperRagTool.
        """
        print("\n📥 [WriteFormatCrew] Checking 'arxiv_pdfs' for new papers...")
        pdf_files = glob.glob("arxiv_pdfs/*.pdf")
        
        if not pdf_files:
            print("⚠️ No PDFs found in arxiv_pdfs.")
            return inputs

        print(f"found {len(pdf_files)} PDFs. Ingesting to Knowledge Base...")
        for pdf_path in pdf_files:
            try:
                # Pastikan path absolut atau relative yang benar
                abs_path = os.path.abspath(pdf_path)
                paper_rag.add_paper(abs_path)
                print(f"  - Added: {os.path.basename(pdf_path)}")
            except Exception as e:
                print(f"  ❌ Failed to add {pdf_path}: {e}")
        
        print("✅ Ingestion complete.")
        return inputs

    @after_kickoff
    def cleanup_pdfs(self, output):
        """
        Setelah crew selesai, hapus semua PDF di folder arxiv_pdfs 
        untuk membersihkan storage.
        """
        print("\n🧹 [WriteFormatCrew] Cleaning up 'arxiv_pdfs'...")
        pdf_files = glob.glob("arxiv_pdfs/*.pdf")
        
        for pdf_path in pdf_files:
            try:
                os.remove(pdf_path)
                print(f"  - Deleted: {os.path.basename(pdf_path)}")
            except Exception as e:
                print(f"  ❌ Failed to delete {pdf_path}: {e}")
        
        print("✅ Cleanup complete.")
        return output

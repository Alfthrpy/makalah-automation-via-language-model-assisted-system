from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Optional,Dict
from pydantic import BaseModel
from malas.crews.models.TaskOutput import Outline, References
from malas.mock.mock_llm import AutoFakeLLM
from malas.tools.custom_tool import (
    DuckDuckGoSearchTool,
    LimitedArxivTool,
    SemanticScholarTool,
    ReferenceFinderTool,
    ResearchExtractorTool,
)

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# PYDANTIC OUTPUT

# Sumber referensi: Arxiv untuk sains/teknik, Semantic Scholar + CrossRef untuk lintas bidang,
# DuckDuckGo + extractor sebagai fallback topik non-akademis.
paper_tool = LimitedArxivTool(results_per_call=2)
semantic_scholar_tool = SemanticScholarTool()
reference_finder_tool = ReferenceFinderTool()
search_tool = DuckDuckGoSearchTool()
extractor_tool = ResearchExtractorTool()

MOCKUP = False
if MOCKUP:
    llm = AutoFakeLLM(model_name='gpt-6')
else:
    llm = LLM(model='gemini/gemini-2.5-flash-lite-preview-09-2025')



@CrewBase
class PlannerCrew:
    """Planner Crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"


    @agent
    def outline_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["outline_planner"],  # type: ignore[index]
            llm=llm,  
            
        )
    
    @agent
    def academic_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["academic_researcher"],  # type: ignore[index]
            llm=llm,
        )

    @task
    def make_outline_task(self) -> Task:
        return Task(
            config=self.tasks_config["make_outline_task"],  # type: ignore[index]
            output_pydantic=Outline,
        )
    
    @task
    def search_reference_task(self) -> Task:
        return Task(
            config=self.tasks_config["search_reference_task"],  # type: ignore[index]
            output_pydantic=References,
            tools=[paper_tool, semantic_scholar_tool, reference_finder_tool, search_tool, extractor_tool]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Research Crew"""


        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            output_log_file="logs/planner_crew_log.json",
            max_rpm=5
        )

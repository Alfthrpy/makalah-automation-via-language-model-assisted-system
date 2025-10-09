from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

from malas.crews.models.TaskOutput import SubBab
from malas.mock.mock_llm import AutoFakeLLM
from malas.tools.custom_tool import ResearchExtractorTool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

MOCKUP = False
if MOCKUP:
    llm = AutoFakeLLM(model_name='gpt-6')
else:
    llm = LLM(model='gemini/gemini-2.0-flash')

extractor_tool = ResearchExtractorTool()

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
            tools=[extractor_tool],
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

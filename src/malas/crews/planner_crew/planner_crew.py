from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List, Optional,Dict
from pydantic import BaseModel
from malas.crews.models.TaskOutput import Outline, References
from malas.mock.mock_llm import AutoFakeLLM
from malas.tools.custom_tool import DuckDuckGoSearchTool

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# PYDANTIC OUTPUT


search_tool = DuckDuckGoSearchTool()

MOCKUP = True
if MOCKUP:
    llm = AutoFakeLLM(model_name='gpt-6')
else:
    llm = LLM(model='gemini/gemini-2.0-flash')



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
            tools=[search_tool],
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
        )

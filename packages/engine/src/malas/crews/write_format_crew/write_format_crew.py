import os

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from malas import refsearch
from malas.config import enhance_tier, get_llm, is_mock
from malas.crews.models.TaskOutput import SubBab
from malas.enhance.guardrail import make_guardrail
from malas.tolerant import TolerantConverter
from malas.tools.custom_tool import DuckDuckGoSearchTool

# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

# Tool pelengkap; konteks utama (excerpt referensi) sudah dimasukkan ke prompt.
search_tool = DuckDuckGoSearchTool()


@CrewBase
class WriteFormatCrew:
    """WriteFormatCrew crew"""

    agents: list[BaseAgent]
    tasks: list[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def content_writer(self) -> Agent:
        return Agent(
            config=self.agents_config['content_writer'], # type: ignore[index]
            verbose=True,
            llm=get_llm("writer"),
        )

    # @agent
    # def quality_reviewer(self) -> Agent:
    #     return Agent(
    #         config=self.agents_config['quality_reviewer'], # type: ignore[index]
    #         llm=get_llm("writer"),
    #         verbose=True,
    #     )


    guard_ctx = None  # diisi MalasFlow sebelum tiap sub-bab: {"state", "judul", "report"}

    @task
    def write_content(self) -> Task:
        gate = {}
        if enhance_tier() in ("standard", "deep"):  # retry berbiaya LLM: hanya di tier yang memang menanggungnya
            gate = {"guardrails": [make_guardrail(lambda: self.guard_ctx, max_retries=1)], "guardrail_max_retries": 1}
        return Task(
            config=self.tasks_config['write_content_task'], # type: ignore[index]
            tools=[] if refsearch.enabled() else [search_tool],  # refsearch+full-text: tool tak perlu (loop token + sitasi liar)
            output_pydantic=SubBab,
            converter_cls=TolerantConverter,
            **gate,
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
            output_log_file="logs/write_format_crew.json" if os.getenv("MALAS_DEBUG_LOGS") == "1" else None,
            max_rpm=None if is_mock() else 10
        )

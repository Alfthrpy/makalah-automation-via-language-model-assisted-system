"""Crew khusus outline (tanpa agen peneliti). Dipakai bila MALAS_REFSEARCH=1; referensi dicari oleh
`malas.refsearch` (kode deterministik), bukan oleh agen LLM bertool.

Sengaja tidak memakai @CrewBase: CrewBase memvalidasi SEMUA task di tasks.yaml (termasuk
search_reference_task yang butuh agen peneliti), padahal crew ini hanya membuat outline.
"""
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from malas.config import get_llm, is_mock
from malas.crews.models.TaskOutput import Outline
from malas.tolerant import TolerantConverter

_CFG = Path(__file__).parent / "config"


def _load(name: str) -> dict:
    return yaml.safe_load((_CFG / name).read_text(encoding="utf-8"))


class OutlineCrew:
    def __init__(self) -> None:
        agent_cfg = _load("agents.yaml")["outline_planner"]
        task_cfg = dict(_load("tasks.yaml")["make_outline_task"])
        task_cfg.pop("agent", None)  # agen diberikan langsung di bawah
        self.agent = Agent(config=agent_cfg, llm=get_llm("planner"))
        self.tasks = [Task(config=task_cfg, agent=self.agent, output_pydantic=Outline, converter_cls=TolerantConverter)]

    def crew(self) -> Crew:
        return Crew(agents=[self.agent], tasks=self.tasks, process=Process.sequential, verbose=True,
                    max_rpm=None if is_mock() else 5)

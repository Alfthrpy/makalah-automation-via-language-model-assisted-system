"""Crew kecil tahap akhir: Kata Pengantar dan perbaikan sitasi per sub-bab."""
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task

from malas.config import get_llm
from malas.crews.models.TaskOutput import KataPengantar, SubBab

_CONFIG = Path(__file__).parent / "config"


def _load(name: str) -> dict:
    return yaml.safe_load((_CONFIG / name).read_text(encoding="utf-8"))


def _single_task_crew(config_file: str, agent_key: str, task_key: str, output, role: str) -> tuple[Crew, Task]:
    cfg = _load(config_file)
    agent = Agent(config=cfg["agents"][agent_key], llm=get_llm(role), verbose=False)
    task = Task(config=cfg["tasks"][task_key], agent=agent, output_pydantic=output)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False, max_rpm=10)
    return crew, task


def run_kata_pengantar(inputs: dict) -> str | None:
    crew, task = _single_task_crew(
        "kata_pengantar.yaml", "kata_pengantar_writer", "write_kata_pengantar", KataPengantar, "writer"
    )
    crew.kickoff(inputs=inputs)
    out = task.output
    return out.pydantic.isi.strip() if out and out.pydantic else None


def run_citation_fix(inputs: dict) -> SubBab | None:
    crew, task = _single_task_crew(
        "citation_fix.yaml", "citation_editor", "fix_citations", SubBab, "reviewer"
    )
    crew.kickoff(inputs=inputs)
    out = task.output
    return out.pydantic if out and out.pydantic else None

"""Crew kecil tahap akhir: Kata Pengantar dan perbaikan sitasi per sub-bab."""
from pathlib import Path
from typing import Callable, Optional

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


UsageCallback = Optional[Callable[[object], None]]


def run_kata_pengantar(inputs: dict, on_usage: UsageCallback = None) -> str | None:
    crew, task = _single_task_crew(
        "kata_pengantar.yaml", "kata_pengantar_writer", "write_kata_pengantar", KataPengantar, "writer"
    )
    result = crew.kickoff(inputs=inputs)
    if on_usage:
        on_usage(result)
    out = task.output
    return out.pydantic.isi.strip() if out and out.pydantic else None


def run_citation_fix(inputs: dict, on_usage: UsageCallback = None) -> SubBab | None:
    crew, task = _single_task_crew(
        "citation_fix.yaml", "citation_editor", "fix_citations", SubBab, "reviewer"
    )
    result = crew.kickoff(inputs=inputs)
    if on_usage:
        on_usage(result)
    out = task.output
    return out.pydantic if out and out.pydantic else None

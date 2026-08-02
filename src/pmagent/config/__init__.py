# Line ending: LF
# Encoding: UTF-8

"""
Load agents and tasks from YAML config files.

CrewAI's YAML loader expects a specific structure; we load and parse
the YAML ourselves then build Agent/Task objects from it.
"""

from __future__ import annotations

import yaml
from pathlib import Path

from crewai import Agent, Task

_CONFIG_DIR = Path(__file__).resolve().parent


def _load_yaml(filename: str) -> dict:
    with open(_CONFIG_DIR / filename, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ── Agents ────────────────────────────────────────────────────────────────────

_agents_cfg = _load_yaml("agents.yaml")

project_planner_agent = Agent(
    config=_agents_cfg["project_planner"],
)
risk_analyst_agent = Agent(
    config=_agents_cfg["risk_analyst"],
)
resource_allocator_agent = Agent(
    config=_agents_cfg["resource_allocator"],
)
manager_agent = Agent(
    config=_agents_cfg["manager"],
)


# ── Tasks ─────────────────────────────────────────────────────────────────────

_tasks_cfg = _load_yaml("tasks.yaml")

# Build Task objects from YAML config, passing fields as kwargs.
# Agents are already created above, so we can reference them directly.
task_breakdown = Task(
    description=_tasks_cfg["task_breakdown"]["description"],
    expected_output=_tasks_cfg["task_breakdown"]["expected_output"],
    agent=project_planner_agent,
)

risk_analysis = Task(
    description=_tasks_cfg["risk_analysis"]["description"],
    expected_output=_tasks_cfg["risk_analysis"]["expected_output"],
    agent=risk_analyst_agent,
)

resource_allocation = Task(
    description=_tasks_cfg["resource_allocation"]["description"],
    expected_output=_tasks_cfg["resource_allocation"]["expected_output"],
    agent=resource_allocator_agent,
)

manager_synthesis = Task(
    description=_tasks_cfg["manager_synthesis"]["description"],
    expected_output=_tasks_cfg["manager_synthesis"]["expected_output"],
    agent=manager_agent,
)
manager_synthesis.context = [task_breakdown, risk_analysis, resource_allocation]

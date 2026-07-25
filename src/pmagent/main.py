# L1: Automated Project Planning, Estimation, and Allocation
# Run with: python -m pmagent.main

import sys
import warnings
warnings.filterwarnings('ignore')

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

import json
import os
from pathlib import Path
import yaml
import pandas as pd
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# ── SQLite disk I/O workaround ────────────────────────────────────────────────
try:
    import crewai.memory.storage.kickoff_task_outputs_storage as _kos
    import crewai.utilities.task_output_storage_handler as _tosh

    class _NoOpStorage:
        def __init__(self, *a, **kw): pass
        def _initialize_db(self): pass
        def save(self, *a, **kw): pass
        def get_all(self): return []
        def load(self): return []
        def add(self, *a, **kw): pass
        def update(self, *a, **kw): pass
        def delete_all(self): pass

    _NoOpStorage.__name__ = "KickoffTaskOutputsSQLiteStorage"
    _kos.KickoffTaskOutputsSQLiteStorage = _NoOpStorage
    _tosh.KickoffTaskOutputsSQLiteStorage = _NoOpStorage
except Exception:
    pass
# ──────────────────────────────────────────────────────────────────────────────

from crewai import Agent, Task, Crew

# ── 0. Env ────────────────────────────────────────────────────────────────────
load_dotenv()

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key or api_key == "your_openai_key_here":
    warnings.warn(
        "OPENAI_API_KEY is not set — crew.kickoff() will fail until you set it in .env",
        RuntimeWarning,
        stacklevel=2,
    )
os.environ["OPENAI_MODEL_NAME"] = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")

# ── 1. Pydantic models ────────────────────────────────────────────────────────
class TaskEstimate(BaseModel):
    task_name: str = Field(..., description="Name of the task")
    estimated_time_hours: float = Field(..., description="Estimated time in hours")
    required_resources: List[str] = Field(..., description="List of resources required")
    assigned_to: str = Field(default="", description="Team member name assigned to this task, e.g. Fawad")

class Milestone(BaseModel):
    milestone_name: str = Field(..., description="Name of the milestone")
    tasks: List[str] = Field(..., description="List of task IDs associated with this milestone")

class ProjectPlan(BaseModel):
    tasks: List[TaskEstimate] = Field(..., description="List of tasks with estimates")
    milestones: List[Milestone] = Field(..., description="List of project milestones")

# ── 2. YAML loader (CWD-independent) ─────────────────────────────────────────
_config_dir = Path(__file__).resolve().parent / "config"

def _load_yaml(filename: str) -> dict:
    with open(_config_dir / filename, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

agents_config = _load_yaml("agents.yaml")
tasks_config  = _load_yaml("tasks.yaml")

# ── 3. Agents ─────────────────────────────────────────────────────────────────
project_planning_agent = Agent(
    config=agents_config["project_planning_agent"],
)
estimation_agent = Agent(
    config=agents_config["estimation_agent"],
)
resource_allocation_agent = Agent(
    config=agents_config["resource_allocation_agent"],
)

# ── 4. Tasks ──────────────────────────────────────────────────────────────────
task_breakdown = Task(
    config=tasks_config["task_breakdown"],
    agent=project_planning_agent,
)
time_resource_estimation = Task(
    config=tasks_config["time_resource_estimation"],
    agent=estimation_agent,
)
resource_allocation = Task(
    config=tasks_config["resource_allocation"],
    agent=resource_allocation_agent,
    output_pydantic=ProjectPlan,
)

# ── 5. Crew ───────────────────────────────────────────────────────────────────
crew = Crew(
    agents=[
        project_planning_agent,
        estimation_agent,
        resource_allocation_agent,
    ],
    tasks=[
        task_breakdown,
        time_resource_estimation,
        resource_allocation,
    ],
    verbose=True,
)

# ── 6. Default inputs ────────────────────────────────────────────────────────
inputs = {
    "project_type": "Residential Construction – 20-Marla Plot",
    "project_objectives": "Complete construction of a 2-story house on a 20-marla plot",
    "industry": "Construction",
    "team_members": """
- Ali (Site Engineer)
- Ahmed (Carpenter / Steel Worker)
- Usman (Electrician)
- Hassan (Plumber)
- Bilal (General Laborer)
""",
    "project_requirements": """
- Excavation and foundation work
- Column and beam reinforcement and casting
- Brick masonry and wall construction
- Roof slab casting
- Electrical wiring and conduit installation
- Plumbing pipework and drainage
- Window and door frame installation
- Interior and exterior plastering
- Flooring (marble/tiles)
- Paint and finishing
""",
}

# ── 7. Kickoff ────────────────────────────────────────────────────────────────
def kickoff(persist: bool = True, inputs: dict | None = None) -> dict:
    """Run the L1 crew and optionally persist the plan to the database.

    Args:
        persist: If True, save the plan to SQLite after generation.
        inputs: Project description dict. Falls back to the module-level
                default if not provided.
    """
    _inputs = inputs or globals()["inputs"]

    print("=" * 60)
    print("  CrewAI L1 – Project Planning, Estimation & Allocation")
    print("=" * 60)
    print()

    try:
        import crewai.llms.cache as _cache_mod
        _cache_mod.mark_cache_breakpoint = lambda message: message
    except Exception:
        pass

    result = crew.kickoff(inputs=_inputs)

    # ── Usage metrics ──────────────────────────────────────────────────────────
    costs = 0.050 * (
        crew.usage_metrics.prompt_tokens + crew.usage_metrics.completion_tokens
    ) / 1_000_000
    print(f"\nTotal costs: ${costs:.4f}")
    usage = crew.usage_metrics.dict()

    # ── Structured result ─────────────────────────────────────────────────────
    plan = result.pydantic.dict() if hasattr(result, "pydantic") and result.pydantic else {}
    tasks_df = pd.DataFrame(plan.get("tasks", []))
    milestones_df = pd.DataFrame(plan.get("milestones", []))

    print("\n" + "=" * 60)
    print("  Tasks")
    print("=" * 60)
    if not tasks_df.empty:
        print(tasks_df.to_string(index=False))
    else:
        print("(no structured tasks returned)")

    print("\n" + "=" * 60)
    print("  Milestones")
    print("=" * 60)
    if not milestones_df.empty:
        print(milestones_df.to_string(index=False))
    else:
        print("(no structured milestones returned)")

    # ── Persist to DB ─────────────────────────────────────────────────────────
    if persist:
        try:
            from pmagent.persistence import save_l1_plan
            project_id = save_l1_plan(inputs=_inputs, plan_data=plan)
            if project_id:
                print(f"\n✅ Plan saved to database — project_id={project_id}")
            else:
                print(f"\n⚠️  DB save returned None — plan generated but NOT saved.")
                print(f"    plan_data keys: {list(plan.keys()) if plan else 'empty'}")
                print(f"    tasks in plan: {len(plan.get('tasks', []))}")
        except Exception as exc:
            print(f"\n❌ DB save failed: {exc}")
            import traceback; traceback.print_exc()

    return {
        "plan": plan,
        "tasks_df": tasks_df,
        "milestones_df": milestones_df,
        "usage": usage,
        "raw": result.raw if hasattr(result, "raw") else str(result),
        "cost_usd": round(costs, 4),
    }


# ── 8. Run directly ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    kickoff()

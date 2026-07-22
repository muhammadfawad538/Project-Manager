# L1: Automated Project Planning, Estimation, and Allocation
# Run with: python main.py

import sys
import warnings
warnings.filterwarnings('ignore')

# Fix Windows console encoding for emoji output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path
import yaml
import pandas as pd
from typing import List
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# ── SQLite disk I/O workaround ────────────────────────────────────────────
# crewai 1.x opens a SQLite file on Crew() init.  On some drives this
# fails with "disk I/O error".  Swapping in a no-op storage class lets
# the crew initialize cleanly; KickoffTaskOutputs storage is not used
# by this project anyway.
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
# ──────────────────────────────────────────────────────────────────────────

from crewai import Agent, Task, Crew

# ── 0. Load env ───────────────────────────────────────────────────────────────
load_dotenv()

# ── 0. Configure Groq (free LLM provider) ────────────────────────────────────
api_key = os.environ.get("GROQ_API_KEY", "")
if not api_key or api_key == "your_groq_key_here":
    # Soft warning — crew.kickoff() will fail until key is set
    warnings.warn(
        "GROQ_API_KEY is not set — crew.kickoff() will fail until you set it in .env",
        RuntimeWarning,
        stacklevel=2,
    )
else:
    os.environ["GROQ_API_KEY"] = api_key
    os.environ["OPENAI_API_KEY"] = api_key  # CrewAI reads this by default
os.environ["OPENAI_MODEL_NAME"] = "groq/llama-3.3-70b-versatile"

# Groq does not support LiteLLM prompt caching — disable it to avoid
# 'cache_breakpoint is unsupported' errors.
os.environ["LITELLM_CACHE"] = "False"

# ── 1. Pydantic models for structured output ──────────────────────────────────
class TaskEstimate(BaseModel):
    task_name: str = Field(..., description="Name of the task")
    estimated_time_hours: float = Field(..., description="Estimated time in hours")
    required_resources: List[str] = Field(..., description="List of resources required")

class Milestone(BaseModel):
    milestone_name: str = Field(..., description="Name of the milestone")
    tasks: List[str] = Field(..., description="List of task IDs associated with this milestone")

class ProjectPlan(BaseModel):
    tasks: List[TaskEstimate] = Field(..., description="List of tasks with estimates")
    milestones: List[Milestone] = Field(..., description="List of project milestones")

# ── 2. Load YAML configs ──────────────────────────────────────────────────────
_config_dir = Path(__file__).resolve().parent / "config"

with open(_config_dir / "agents.yaml", "r") as f:
    agents_config = yaml.safe_load(f)

with open(_config_dir / "tasks.yaml", "r") as f:
    tasks_config = yaml.safe_load(f)

# ── 3. Create Agents ─────────────────────────────────────────────────────────
project_planning_agent = Agent(
    config=agents_config["project_planning_agent"],
)

estimation_agent = Agent(
    config=agents_config["estimation_agent"],
)

resource_allocation_agent = Agent(
    config=agents_config["resource_allocation_agent"],
)

# ── 4. Create Tasks ──────────────────────────────────────────────────────────
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

# ── 5. Assemble Crew ─────────────────────────────────────────────────────────
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

# ── 6. Inputs ────────────────────────────────────────────────────────────────
inputs = {
    "project_type": "Website",
    "project_objectives": "Create a website for a small business",
    "industry": "Technology",
    "team_members": """
- John Doe (Project Manager)
- Jane Doe (Software Engineer)
- Bob Smith (Designer)
- Alice Johnson (QA Engineer)
- Tom Brown (QA Engineer)
""",
    "project_requirements": """
- Create a responsive design that works well on desktop and mobile devices
- Implement a modern, visually appealing user interface with a clean look
- Develop a user-friendly navigation system with intuitive menu structure
- Include an "About Us" page highlighting the company's history and values
- Design a "Services" page showcasing the business's offerings with descriptions
- Create a "Contact Us" page with a form and integrated map for communication
- Implement a blog section for sharing industry news and company updates
- Ensure fast loading times and optimize for search engines (SEO)
- Integrate social media links and sharing capabilities
- Include a testimonials section to showcase customer feedback and build trust
""",
}

# ── 7. Run ───────────────────────────────────────────────────────────────────
def kickoff():
    print("=" * 60)
    print("  CrewAI – Automated Project Planning, Estimation & Allocation")
    print("=" * 60)
    print()

    # Groq does not support LiteLLM prompt caching.  Make
    # `mark_cache_breakpoint()` a no-op so the unsupported key is never
    # injected into the outgoing request body.
    try:
        import crewai.llms.cache as _cache_mod

        def _noop_mark(message):
            return message

        _cache_mod.mark_cache_breakpoint = _noop_mark
    except Exception:
        pass

    result = crew.kickoff(inputs=inputs)

    # ── 8. Usage Metrics ─────────────────────────────────────────────────────────
    costs = 0.050 * (
        crew.usage_metrics.prompt_tokens + crew.usage_metrics.completion_tokens
    ) / 1_000_000
    print(f"\nTotal costs: ${costs:.4f}")
    print("\nUsage Metrics:")
    print(pd.DataFrame([crew.usage_metrics.dict()]))

    # ── 9. Structured Result ─────────────────────────────────────────────────────
    plan = result.pydantic.dict()

    tasks_df = pd.DataFrame(plan["tasks"])
    milestones_df = pd.DataFrame(plan["milestones"])

    print("\n" + "=" * 60)
    print("  Tasks")
    print("=" * 60)
    print(tasks_df.to_string(index=False))

    print("\n" + "=" * 60)
    print("  Milestones")
    print("=" * 60)
    print(milestones_df.to_string(index=False))


if __name__ == "__main__":
    kickoff()

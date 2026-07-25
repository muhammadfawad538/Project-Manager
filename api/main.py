"""
Vercel serverless entrypoint for pmagent.

Uses direct OpenAI API calls instead of CrewAI to keep the bundle under 500MB.
Produces the same structured output (tasks, milestones, estimates, assignments).
"""
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ── Path setup ─────────────────────────────────────────────────────────────────

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

app = FastAPI(title="pmagent – AI Project Planning API")


# ── Schemas ────────────────────────────────────────────────────────────────────

class ProjectInput(BaseModel):
    project_type: str = Field(default="Website", description="Type of project")
    project_objectives: str = Field(
        default="Create a website for a small business",
        description="High-level project objectives",
    )
    industry: str = Field(default="Technology", description="Industry sector")
    deadline: str = Field(default="3 days", description="Project deadline")
    team_members: str = Field(
        default="",
        description="Plain-text list of team members with roles, e.g. '- Ali (Engineer)'",
    )
    project_requirements: str = Field(
        default="",
        description="Plain-text list of requirements",
    )


class TaskOut(BaseModel):
    task_name: str
    estimated_time_hours: float
    required_resources: list[str] = Field(default_factory=list)
    assigned_to: str = ""


class MilestoneOut(BaseModel):
    milestone_name: str
    tasks: list[str] = Field(default_factory=list)


class ProjectPlanResponse(BaseModel):
    tasks: list[TaskOut]
    milestones: list[MilestoneOut]
    raw: str = ""


# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a senior project manager AI with three specialized sub-agents.

Given a project description, team, requirements, and deadline, produce a structured plan.

Follow these three phases in your reasoning:

1. PROJECT PLANNER: Break requirements into granular tasks. For each task give:
   - A clear name
   - Estimated hours
   - Dependencies / order (sequence them logically)
   - Which team member should do it (match by role/skill)

2. ESTIMATION ANALYST: Review each task for realistic hour estimates.
   Consider complexity, team member skill, and dependencies. Flag risks.

3. RESOURCE ALLOCATOR: Finalize assignments. Distribute work evenly across
   team members. No one person should be overloaded.

Output ONLY valid JSON matching this exact schema:
{
  "tasks": [
    {
      "task_name": "string",
      "estimated_time_hours": number,
      "required_resources": ["string"],
      "assigned_to": "string (team member name exactly as provided)"
    }
  ],
  "milestones": [
    {
      "milestone_name": "string",
      "tasks": ["string (task names belonging to this milestone)"]
    }
  ]
}

Rules:
- Every task MUST have assigned_to set to an exact team member name from the input
- Tasks should be in execution order (dependencies first)
- estimated_time_hours must be a number (not a range)
- milestone tasks arrays must reference task_name values exactly
- Do NOT include markdown formatting, explanations, or extra fields
- Respond ONLY with the JSON object
"""


# ── OpenAI call ────────────────────────────────────────────────────────────────

def _call_openai(user_content: str) -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"openai package not installed: {exc}") from exc

    model = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc

    usage = {}
    if hasattr(response, "usage") and response.usage:
        usage = {
            "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
            "completion_tokens": getattr(response.usage, "completion_tokens", 0),
        }

    raw = response.choices[0].message.content or "{}"
    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {}

    # Normalize into expected shape
    tasks = [
        TaskOut(
            task_name=t.get("task_name", ""),
            estimated_time_hours=float(t.get("estimated_time_hours") or 0),
            required_resources=t.get("required_resources", []) or [],
            assigned_to=t.get("assigned_to", "") or "",
        ).model_dump()
        for t in plan.get("tasks", [])
    ]

    milestones = [
        MilestoneOut(
            milestone_name=m.get("milestone_name", ""),
            tasks=m.get("tasks", []) or [],
        ).model_dump()
        for m in plan.get("milestones", [])
    ]

    pt = usage.get("prompt_tokens", 0)
    ct = usage.get("completion_tokens", 0)
    cost = 0.050 * (pt + ct) / 1_000_000

    return {
        "tasks": tasks,
        "milestones": milestones,
        "raw": raw,
        "usage_metrics": {**usage, "estimated_cost_usd": round(cost, 6)},
    }


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "service": "pmagent"}


@app.post("/plan", response_model=ProjectPlanResponse, tags=["planning"])
def generate_plan(payload: ProjectInput):
    user_content = f"""\
Project: {payload.project_type}
Objective: {payload.project_objectives}
Industry: {payload.industry}
Deadline: {payload.deadline}

Team members:
{payload.team_members}

Requirements:
{payload.project_requirements}
"""
    result = _call_openai(user_content)
    return ProjectPlanResponse(**result)

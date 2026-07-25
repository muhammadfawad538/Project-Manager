"""
Vercel serverless entrypoint for pmagent.

Vercel's Python runtime will serve this as a WSGI/ASGI app.
We use FastAPI here because it's easy to work with and Vercel supports it via
an internal WSGI/ASGI adapter (the `vercel` package / python-bridge).
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import sys
import os
import traceback

# Make the project root + src/ importable when this file lives in /api/
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_src_dir = os.path.join(_project_root, "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

app = FastAPI(title="pmagent – AI Project Planning API")

# ── Request / response schemas ───────────────────────────────────────────────

class ProjectInput(BaseModel):
    project_type: str = Field(default="Website", description="Type of project")
    project_objectives: str = Field(
        default="Create a website for a small business",
        description="High-level project objectives",
    )
    industry: str = Field(default="Technology", description="Industry sector")
    team_members: str = Field(
        default="",
        description="Plain-text list of team members with roles",
    )
    project_requirements: str = Field(
        default="",
        description="Plain-text list of requirements",
    )

class ProjectPlanResponse(BaseModel):
    tasks: list = Field(..., description="List of estimated tasks")
    milestones: list = Field(..., description="List of project milestones")
    usage_metrics: dict = Field(default_factory=dict, description="LLM usage / cost info")
    raw: str = Field(default="", description="Raw crew kickoff output text")

# ── Lazy runtime init ────────────────────────────────────────────────────────
# Importing `pmagent.main` at module level would run crew.kickoff() at import
# time (because of the `if __name__ == "__main__"` guard it doesn't, but some
# CrewAI versions emit warnings). Importing inside the request handler ensures
# nothing heavy runs until a real request arrives.
# We cache the crew + config so we only initialise once per serverless instance.

_crew = None
_inputs_defaults = None


def _get_crew():
    """Lazily import and (re)use the crew object."""
    global _crew, _inputs_defaults
    if _crew is not None:
        return _crew, _inputs_defaults

    from pmagent.main import crew, inputs as _inp  # noqa: WPS433
    _crew = crew
    _inputs_defaults = _inp
    return _crew, _inputs_defaults


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", tags=["health"])
def health():
    """Lightweight health check — no LLM calls."""
    return {"status": "ok", "service": "pmagent"}


@app.post("/plan", response_model=ProjectPlanResponse, tags=["planning"])
def generate_plan(payload: ProjectInput):
    """
    Run the CrewAI planning pipeline and return a structured project plan.

    Takes project context (type, requirements, team, etc.) and returns
    task estimates, milestones, and usage metrics.
    """
    try:
        crew, defaults = _get_crew()
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialise crew: {exc}",
        ) from exc

    # Merge incoming payload with YAML defaults
    run_inputs = dict(defaults)
    run_inputs["project_type"] = payload.project_type or run_inputs.get("project_type", "")
    run_inputs["project_objectives"] = (
        payload.project_objectives or run_inputs.get("project_objectives", "")
    )
    run_inputs["industry"] = payload.industry or run_inputs.get("industry", "")
    run_inputs["team_members"] = (
        payload.team_members or run_inputs.get("team_members", "")
    )
    run_inputs["project_requirements"] = (
        payload.project_requirements or run_inputs.get("project_requirements", "")
    )

    try:
        result = crew.kickoff(inputs=run_inputs)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(
            status_code=502,
            detail=f"LLM call failed: {exc}",
        ) from exc

    # ── Build response ────────────────────────────────────────────────────────
    plan = {}
    raw = ""
    if hasattr(result, "pydantic") and result.pydantic is not None:
        plan = result.pydantic.dict()
    raw = str(result.raw if hasattr(result, "raw") else result)

    usage = {}
    try:
        um = crew.usage_metrics
        usage = um.dict() if hasattr(um, "dict") else dict(um)
    except Exception:
        pass

    cost = 0.0
    try:
        pt = usage.get("prompt_tokens", 0)
        ct = usage.get("completion_tokens", 0)
        cost = 0.050 * (pt + ct) / 1_000_000
    except Exception:
        pass

    usage["estimated_cost_usd"] = round(cost, 6)

    return ProjectPlanResponse(
        tasks=plan.get("tasks", []),
        milestones=plan.get("milestones", []),
        usage_metrics=usage,
        raw=raw,
    )

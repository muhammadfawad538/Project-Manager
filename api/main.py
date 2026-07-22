"""
Vercel serverless function — runs the L1 project planning crew inline.

POST /api/plan
Body JSON: { project_type, project_requirements, team_members, industry }
Returns: { tasks, milestones, usage }
"""
import json
import os
import sys
from pathlib import Path


def _fix_crewai_for_vercel():
    """Apply SQLite + Groq workarounds before any crewai import."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

    # SQLite storage workaround for CrewAI 1.x on Vercel
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

    # Disable LiteLLM prompt caching for Groq
    try:
        import crewai.llms.cache as _cache_mod
        _cache_mod.mark_cache_breakpoint = lambda msg: msg
    except Exception:
        pass


def handler(request):
    """Vercel Python serverless entry point."""
    _fix_crewai_for_vercel()

    try:
        body = json.loads(request.get_data(as_text=True) or "{}")
    except Exception:
        body = {}

    # Lazy import here so patching above takes effect
    from pmagent.main import crew, DEFAULT_INPUTS  # noqa: E402
    from pmagent.main import kickoff  # noqa: E402

    inputs = {
        "project_type": body.get("project_type", DEFAULT_INPUTS["project_type"]),
        "project_requirements": body.get("project_requirements", DEFAULT_INPUTS["project_requirements"]),
        "team_members": body.get("team_members", DEFAULT_INPUTS["team_members"]),
        "industry": body.get("industry", DEFAULT_INPUTS["industry"]),
    }

    try:
        result = kickoff()
        plan = getattr(result, "pydantic", None)
        output = plan.model_dump() if plan is not None else {"raw": getattr(result, "raw", str(result))}

        try:
            usage = crew.usage_metrics
            total = usage.prompt_tokens + usage.completion_tokens
            output["usage"] = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": total,
                "cost_usd": round(0.05 * total / 1_000_000, 6),
            }
        except Exception:
            pass
    except Exception as exc:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(exc)}),
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(output),
    }

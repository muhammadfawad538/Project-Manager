"""
Vercel serverless function — runs the L1 project planning crew inline
to avoid import-time crashes from CrewAI.

POST /api/plan
Body JSON: { project_type, project_requirements, team_members, industry }
Returns: { tasks, milestones, usage }
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# ── SQLite workaround ─────────────────────────────────────────────────
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

# ── Groq cache workaround ────────────────────────────────────────────
try:
    import crewai.llms.cache as _cache_mod

    def _noop_mark(msg):
        return msg

    _cache_mod.mark_cache_breakpoint = _noop_mark
except Exception:
    pass

# ── Entry point ───────────────────────────────────────────────────────
from pmagent.main import crew, DEFAULT_INPUTS  # noqa: E402


def run_crew(inputs):
    """Run the crew inline to avoid importing __main__ logic."""
    return crew.kickoff(inputs=inputs)


def handler(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except Exception:
        body = {}

    inputs = {
        "project_type": body.get("project_type", DEFAULT_INPUTS["project_type"]),
        "project_requirements": body.get("project_requirements", DEFAULT_INPUTS["project_requirements"]),
        "team_members": body.get("team_members", DEFAULT_INPUTS["team_members"]),
        "industry": body.get("industry", DEFAULT_INPUTS["industry"]),
    }

    try:
        result = run_crew(inputs)
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

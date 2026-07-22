"""
Vercel serverless function — runs the L1 project planning crew.

POST /api/plan
Body (JSON):
{
  "project_type": "Website",
  "project_requirements": "...",
  "team_members": "...",
  "industry": "Technology"
}

Returns JSON:
{
  "tasks": [...],
  "milestones": [...],
  "usage": { "prompt_tokens": ..., "completion_tokens": ..., "cost_usd": ... }
}
"""
from __future__ import annotations

import json
import os
import sys

# Add src/ to path so pmagent resolves
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---- SQLite workaround (same as main.py) ----
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

# ---- Groq cache workaround (same as main.py) ----
try:
    import crewai.llms.cache as _cache_mod

    def _noop_mark(message):
        return message

    _cache_mod.mark_cache_breakpoint = _noop_mark
except Exception:
    pass

from pmagent.main import crew, kickoff  # noqa: E402


def handler(request):
    """Vercel Python function entry point."""
    try:
        body = request.json() if hasattr(request, "json") else {}
    except Exception:
        body = {}

    inputs = {
        "project_type": body.get("project_type", "Website"),
        "project_requirements": body.get("project_requirements", ""),
        "team_members": body.get("team_members", ""),
        "industry": body.get("industry", "Technology"),
    }

    result = kickoff()

    plan = getattr(result, "pydantic", None)
    if plan is not None:
        output = plan.model_dump()
    else:
        output = {"raw": getattr(result, "raw", str(result))}

    try:
        usage = crew.usage_metrics
        total_tokens = usage.prompt_tokens + usage.completion_tokens
        cost = 0.05 * total_tokens / 1_000_000
        output["usage"] = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": total_tokens,
            "cost_usd": round(cost, 6),
        }
    except Exception:
        pass

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(output),
    }

# Line ending: LF
# Encoding: UTF-8

"""
pmagent — AI-powered project management with CrewAI.

Entry point: run the planning crew from the CLI, or import kickoff()
from another module.

Usage:
    python -m pmagent.main
    from pmagent.main import kickoff
    result = kickoff(inputs={...})
"""

from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

import os

from dotenv import load_dotenv

load_dotenv()

# ── 0. Env ────────────────────────────────────────────────────────────────────

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key or api_key == "your_openai_key_here":
    warnings.warn(
        "OPENAI_API_KEY is not set — crew.kickoff() will fail until you set it in .env",
        RuntimeWarning,
        stacklevel=2,
    )
os.environ.setdefault("OPENAI_MODEL_NAME", os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini"))


# ── 1. CrewAI imports ─────────────────────────────────────────────────────────

from crewai import Crew, Process


# ── 2. Load agents and tasks from config package ──────────────────────────────

from pmagent.config.models import (  # noqa: E402
    WBSOutput,
    RiskRegisterOutput,
    ResourceAllocationOutput,
)
from pmagent.config import (  # noqa: E402
    project_planner_agent,
    risk_analyst_agent,
    resource_allocator_agent,
    manager_agent,
    task_breakdown,
    risk_analysis,
    resource_allocation,
    manager_synthesis,
)
from pmagent.tools.pm_tools import (  # noqa: E402
    ListProjectsTool,
    GetProjectTool,
    CreateProjectTool,
    FindBlockersTool,
    CheckTeamWorkloadTool,
    UpdateTaskStatusTool,
    LogDailyTool,
    CreateIssueTool,
    ListIssuesTool,
    UpdateIssueStatusTool,
    AssignIssueTool,
    CreateChangeRequestTool,
    ListChangeRequestsTool,
    UpdateChangeRequestStatusTool,
)


# ── 3. Wire tools onto the manager agent ─────────────────────────────────────

manager_agent.tools = [
    ListProjectsTool(),
    GetProjectTool(),
    CreateProjectTool(),
    FindBlockersTool(),
    CheckTeamWorkloadTool(),
    UpdateTaskStatusTool(),
    LogDailyTool(),
    # Issue/CR tools available via API; CrewAI integration pending schema fix
]


# ── 4. Attach Pydantic output models to tasks ─────────────────────────────────
# (done here, after models are imported, to avoid circular imports)

task_breakdown.output_pydantic = WBSOutput
risk_analysis.output_pydantic = RiskRegisterOutput
resource_allocation.output_pydantic = ResourceAllocationOutput
manager_synthesis.context = [task_breakdown, risk_analysis, resource_allocation]


# ── 5. Assemble the crew ──────────────────────────────────────────────────────

crew = Crew(
    agents=[
        project_planner_agent,
        risk_analyst_agent,
        resource_allocator_agent,
        manager_agent,
    ],
    tasks=[
        task_breakdown,
        risk_analysis,
        resource_allocation,
        manager_synthesis,
    ],
    process=Process.sequential,
    verbose=True,
)


# ── 6. Default inputs ─────────────────────────────────────────────────────────

DEFAULT_INPUTS = {
    "project_type": "Enterprise CRM System Implementation",
    "project_objectives": "Implement a CRM system for 500+ users across 3 departments within 6 months",
    "industry": "Technology / Software",
    "deadline": "6 months",
    "country": "Saudi Arabia",
    "currency": "SAR",
    "output_language": "English",
    "team_members": """
- Sara (Project Manager)
- Khalid (Backend Developer)
- Noura (Frontend Developer)
- Faisal (QA Engineer)
- Laila (DevOps Engineer)
- Omar (Business Analyst)
""",
    "project_requirements": """
- Requirements gathering and stakeholder interviews
- Backend RESTful API development
- Frontend React dashboard development
- Database design and migration
- User authentication and RBAC
- Integration with ERP and email systems
- Automated testing and CI/CD pipeline
- User training and documentation
- Phased rollout to 3 departments
- Post-launch support and bug fixing
""",
}


# ── 7. Critical Path Computation ──────────────────────────────────────────────

def compute_critical_path(tasks: list[dict]) -> dict:
    """Algorithmically compute the critical path from WBS tasks.

    Uses forward/backward pass (CPM — Critical Path Method):
    - Forward pass: compute Earliest Start (ES) and Earliest Finish (EF)
    - Backward pass: compute Latest Start (LS) and Latest Finish (LF)
    - Float = LS - ES.  Zero float = critical path.

    Args:
        tasks: list of task dicts with keys:
            id (str): hierarchical task ID like "1.1"
            estimated_hours (float): effort estimate
            dependencies (list[str]): task IDs this task depends on

    Returns:
        dict with keys: critical_path (list[str]), total_duration_days (float),
        all_floats (dict[id -> float]), total_estimated_hours (float)
    """
    # Build lookup by id
    task_map = {t["id"]: t for t in tasks}

    # Convert hours to days (8-hour workday), default 1 day if 0
    def _duration(task):
        hrs = task.get("estimated_hours", 0) or 0
        return max(hrs / 8.0, 0.5)  # minimum 0.5 day

    # Topological order via Kahn's algorithm
    in_degree = {tid: 0 for tid in task_map}
    successors = {tid: [] for tid in task_map}

    for tid, task in task_map.items():
        deps = task.get("dependencies", []) or []
        for dep in deps:
            dep = str(dep)
            if dep in task_map:
                in_degree[tid] += 1
                successors[dep].append(tid)

    # Forward pass: ES, EF
    es = {}
    ef = {}
    queue = [tid for tid, deg in in_degree.items() if deg == 0]
    processed = set()

    while queue:
        # Sort for deterministic order
        queue.sort()
        tid = queue.pop(0)
        if tid in processed:
            continue
        processed.add(tid)

        task = task_map[tid]
        dur = _duration(task)

        # ES = max EF of all predecessors
        deps = task.get("dependencies", []) or []
        pred_ef = [ef.get(str(d), 0) for d in deps if str(d) in ef]
        es[tid] = max(pred_ef) if pred_ef else 0
        ef[tid] = es[tid] + dur

        # Update successors
        for succ in successors[tid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0 and succ not in processed:
                queue.append(succ)

    # Project end = max EF
    project_end = max(ef.values()) if ef else 0

    # Backward pass: LS, LF
    lf = {tid: project_end for tid in task_map}
    ls = {}

    # Process in reverse topological order
    reverse_order = sorted(task_map.keys(), key=lambda x: ef.get(x, 0), reverse=True)
    for tid in reverse_order:
        task = task_map[tid]
        dur = _duration(task)
        succ_ls = [ls.get(s, project_end) for s in successors[tid] if s in ls]
        lf[tid] = min(succ_ls) if succ_ls else project_end
        ls[tid] = lf[tid] - dur

    # Float = LS - ES
    floats = {}
    for tid in task_map:
        floats[tid] = round(ls.get(tid, 0) - es.get(tid, 0), 2)

    # Critical path: tasks with zero float, sorted by ES
    critical = sorted([tid for tid, f in floats.items() if f == 0], key=lambda x: es.get(x, 0))

    return {
        "critical_path": critical,
        "total_duration_days": round(project_end, 1),
        "all_floats": floats,
        "total_estimated_hours": round(sum(_duration(t) * 8 for t in tasks), 1),
    }


# ── 8. Kickoff ────────────────────────────────────────────────────────────────

def kickoff(inputs: dict | None = None) -> dict:
    """Run the planning crew and return structured results.

    Args:
        inputs: Project description dict. Falls back to DEFAULT_INPUTS if not provided.

    Returns:
        Dict with keys: raw_output, wbs, risks, resources, critical_path,
        usage, cost_usd
    """
    _inputs = inputs or DEFAULT_INPUTS

    print("=" * 60)
    print("  pmagent — AI Project Planning, Estimation & Allocation")
    print("=" * 60)
    print()

    try:
        import crewai.llms.cache as _cache_mod  # noqa: E402

        _cache_mod.mark_cache_breakpoint = lambda message: message
    except Exception:
        pass

    result = crew.kickoff(inputs=_inputs)

    # Usage metrics
    costs = 0.050 * (
        crew.usage_metrics.prompt_tokens + crew.usage_metrics.completion_tokens
    ) / 1_000_000
    usage = crew.usage_metrics.dict() if hasattr(crew.usage_metrics, "dict") else dict(crew.usage_metrics)

    # Raw output from the manager synthesis task
    raw_output = result.raw if hasattr(result, "raw") else str(result)

    # Structured outputs from each specialist (via output_pydantic)
    wbs: dict = {}
    risks: dict = {}
    resources: dict = {}

    if hasattr(result, "tasks_output"):
        for task_out in result.tasks_output:
            agent_role = (task_out.agent or "").lower()
            try:
                pyd = task_out.pydantic.dict() if task_out.pydantic else {}
            except Exception:
                pyd = {}

            if "planner" in agent_role or "breakdown" in agent_role:
                wbs = pyd or {"raw": getattr(task_out, "raw", "")[:2000]}
            elif "risk" in agent_role:
                risks = pyd or {"raw": getattr(task_out, "raw", "")[:2000]}
            elif "resource" in agent_role or "allocation" in agent_role:
                resources = pyd or {"raw": getattr(task_out, "raw", "")[:2000]}

    # ── Algorithmic critical path computation ──────────────────────────────────
    critical_path_result = {"critical_path": [], "total_duration_days": 0, "all_floats": {}}
    wbs_tasks = wbs.get("tasks", [])
    if wbs_tasks:
        try:
            critical_path_result = compute_critical_path(wbs_tasks)
            cp = critical_path_result["critical_path"]
            print(f"\nComputed critical path ({len(cp)} tasks): {' -> '.join(cp)}")
            print(f"Project duration: {critical_path_result['total_duration_days']} days")
        except Exception as exc:
            print(f"\nCritical path computation failed: {exc}")

    print(f"\nTotal costs: ${costs:.4f}")
    print(f"Structured output: WBS={bool(wbs)}, Risks={bool(risks)}, Resources={bool(resources)}")

    return {
        "raw_output": raw_output,
        "wbs": wbs,
        "risks": risks,
        "resources": resources,
        "critical_path": critical_path_result,
        "usage": usage,
        "cost_usd": round(costs, 4),
    }


# ── 8. CLI entry point ────────────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="pmagent — AI Project Planning")
    parser.add_argument("--inputs", "-i", help="Path to JSON file with project inputs")
    parser.add_argument("--output", "-o", help="Path to save the result JSON")
    args = parser.parse_args()

    inputs = None
    if args.inputs:
        with open(args.inputs, "r", encoding="utf-8") as fh:
            inputs = json.load(fh)

    result = kickoff(inputs=inputs)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nResults saved to {args.output}")
    else:
        print("\n" + "=" * 60)
        print("  Manager Synthesis Output")
        print("=" * 60)
        print(result.get("raw_output", "(no output)"))


if __name__ == "__main__":
    main()

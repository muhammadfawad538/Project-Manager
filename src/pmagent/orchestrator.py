# Line ending: LF
# Encoding: UTF-8

"""
PM Manager — the agentic orchestrator for pmagent.

This crew sits *above* L1 (planning) and L2 (reporting).  It acts as the
project manager that:
  1. Creates and manages projects (status, team, scope)
  2. Tracks daily work (standup logs, progress updates)
  3. Runs the L1 crew when a new plan is needed
  4. Runs the L2 crew for sprint reports
  5. Detects problems (blockers, overruns, overdue tasks)
  6. Makes decisions: reassign, replan, escalate
  7. Coaches the team through daily standups

All of the manager's knowledge comes from the database via its tools — it
never hallucinates project state because every answer is backed by a SQL query.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import sys
import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

from crewai import Agent, Task, Crew
from crewai.tools import BaseTool
from dotenv import load_dotenv
import yaml

load_dotenv()
os.environ.setdefault("OPENAI_MODEL_NAME", "gpt-4o-mini")

# ── Helpers ───────────────────────────────────────────────────────────────────

_COL_DASH = "—"  # —


def _to_plain_dicts(rows):
    """Serialize ORM rows to plain dicts inside the session to avoid DetachedInstanceError."""
    return [
        {c.name: getattr(r, c.name) for c in r.__table__.columns}
        for r in rows
    ]


# ── Tools ─────────────────────────────────────────────────────────────────────

class ListProjectsTool(BaseTool):
    name: str = "list_projects"
    description: str = "List all projects. Optional filter by status: active, completed, paused, archived."

    def _run(self, status: str = "") -> str:
        from pmagent.db.models import ProjectStatus
        from pmagent.db.repository import list_projects
        from pmagent.db.session import get_session

        st = None
        if status:
            try:
                st = ProjectStatus(status)
            except ValueError:
                return f"Unknown status '{status}'. Use: active, completed, paused, archived"

        with get_session() as session:
            # materialize while session is hot — prevents lazy load after close
            rows = list_projects(session, status=st)
            data = _to_plain_dicts(rows)

        if not data:
            return "No projects found."
        return "\n".join(
            f"  [{r['id']}] {r['name']} ({r['status']}) {_COL_DASH} {r['project_type']}"
            for r in data
        )


class GetProjectTool(BaseTool):
    name: str = "get_project"
    description: str = "Get full details of a project by ID: team, tasks, milestones, progress."

    def _run(self, project_id: int) -> str:
        from pmagent.db.models import TaskStatus
        from pmagent.db.repository import (
            get_project, get_team_members, get_project_tasks,
            get_project_milestones, get_project_daily_logs,
        )
        from pmagent.db.session import get_session

        with get_session() as session:
            p = get_project(session, project_id)
            if not p:
                return f"No project with id={project_id}"

            # Materialize everything while the session is open
            p_name      = p.name
            p_type      = p.project_type
            p_industry  = p.industry
            p_status    = p.status
            p_created   = p.created_at.date()
            p_id        = p.id

            members_raw = list(get_team_members(session, project_id))
            members = [
                {"name": m.name, "role": m.role, "avail": m.availability_hours_per_week}
                for m in members_raw
            ]

            tasks = list(get_project_tasks(session, project_id))
            tasks_plain = _to_plain_dicts(tasks)

            assignee_map = {m.id: m.name for m in members_raw}

            # Build plain-dict task view — avoids accessing relationship attrs after session close
            task_infos = [{
                "id":      t["id"],
                "name":    t["name"],
                "status":  t["status"],
                "progress": t["progress_pct"],
                "assignee": assignee_map.get(t["assigned_to_id"]) or "Unassigned",
                "due":     str(t["due_date"].date()) if t["due_date"] else "TBD",
            } for t in tasks_plain]

            # Also capture milestone and log data as plain dicts before session closes
            milestones_raw = list(get_project_milestones(session, project_id))
            milestones_plain = _to_plain_dicts(milestones_raw)

            logs_raw = list(get_project_daily_logs(session, project_id))
            log_infos = [{
                "date":    l.log_date.date().isoformat(),
                "task_id": l.task_id,
                "note":    (l.yesterday_progress or "")[:60],
            } for l in logs_raw]

        # Counts are derived purely from plain-dicts — no session needed here
        DONE_VAL    = TaskStatus.done.value
        BLOCKED_VAL = TaskStatus.blocked.value
        done    = sum(1 for t in tasks_plain if t["status"] == DONE_VAL)
        blocked = sum(1 for t in tasks_plain if t["status"] == BLOCKED_VAL)
        total   = len(tasks_plain)

        lines = [
            f"Project: {p_name} (id={p_id})",
            f"  Type: {p_type}  |  Industry: {p_industry or 'N/A'}",
            f"  Status: {p_status.value}",
            f"  Created: {p_created}",
            "",
            f"Team ({len(members)} members):",
        ]
        for m in members:
            lines.append(f"  - {m['name']} ({m['role']}) – {m['avail']}h/week")
        lines += [
            "",
            f"Progress: {done}/{total} tasks done ({done * 100 // max(total, 1)}%)",
        ]
        if blocked:
            lines.append(f"  WARNING: {blocked} task(s) BLOCKED")
        lines += ["", "Tasks:"]
        for ti in task_infos[:20]:
            lines.append(
                f"  [{ti['id']}] {ti['name']} – {ti['status']} | "
                f"{ti['progress']:.0f}% | {ti['assignee']} | due {ti['due']}"
            )
        lines += ["", "Milestones:"]
        for ms in milestones_plain[:10]:
            status_val = ms.get("status", "pending")
            due_val = ms["due_date"].date() if ms["due_date"] else "TBD"
            lines.append(f"  [{ms['id']}] {ms['name']} – {status_val} – due {due_val}")
        if log_infos:
            lines += ["", f"Recent logs ({len(log_infos)} total, showing last 3):"]
            for log in log_infos[:3]:
                lines.append(
                    f"  [{log['date']}] Task#{log['task_id']}: {log['note'] or '(no note)'}"
                )
        return "\n".join(lines)


class CreateProjectTool(BaseTool):
    name: str = "create_project"
    description: str = "Create a new project. Args: name, project_type, industry (opt), objectives (opt), requirements (opt), team_members as '- Name (Role)' lines."

    def _run(
        self,
        name: str = "",
        project_type: str = "",
        industry: str = "",
        objectives: str = "",
        requirements: str = "",
        team_members: str = "",
    ) -> str:
        from pmagent.db.models import ProjectStatus
        from pmagent.db.repository import create_project, add_team_member
        from pmagent.db.session import get_session
        if not name or not project_type:
            return "Error: name and project_type are required."
        with get_session() as session:
            project = create_project(
                session=session,
                name=name,
                project_type=project_type,
                industry=industry,
                objectives=objectives,
                requirements=requirements,
            )
            pid = project.id  # capture while session is live
            added = 0
            if team_members:
                for line in team_members.splitlines():
                    line = line.strip().lstrip("-").strip()
                    if not line:
                        continue
                    n, r = line, "Team Member"
                    if "(" in line:
                        idx = line.index("(")
                        n = line[:idx].strip()
                        r = line[idx + 1:].rstrip(")").strip()
                    add_team_member(session=session, project_id=project.id, name=n, role=r)
                    added += 1
        return f"Project '{name}' created with id={pid}. {added} team member(s) added."


class RunL1PlanTool(BaseTool):
    name: str = "run_l1_plan"
    description: str = "Trigger the L1 AI planning crew for a project. Provides a fresh task breakdown + estimates + allocations. Args: project_id."

    def _run(self, project_id: int = 0) -> str:
        try:
            from pmagent.main import crew
            from pmagent.persistence import save_l1_plan
            from pmagent.db.session import get_session
            from pmagent.db.models import ProjectStatus
            from pmagent.db.repository import get_project
        except ImportError as exc:
            return f"Error importing modules: {exc}"

        with get_session() as session:
            project = get_project(session, project_id)
        if not project:
            return f"No project with id={project_id}"

        # We need project fields AFTER closing the session — capture them now
        l1_inputs = project.l1_inputs
        project_type   = project.project_type
        project_objectives = project.objectives
        industry       = project.industry

        # Materialize team_members relationship while session is open
        from pmagent.db.repository import get_team_members
        members_raw = list(get_team_members(session, project_id))
        team_members_block = "\n".join(
            f"- {m.name} ({m.role})" for m in members_raw
        )

        import json as _json
        inputs = _json.loads(l1_inputs or "{}")
        if not inputs:
            inputs = {
                "project_type":         project_type,
                "project_objectives":   project_objectives or "",
                "industry":             industry or "",
                "deadline":             "3 days",
                "team_members":         team_members_block,
                "project_requirements": project.requirements or "",
            }

        try:
            result = crew.kickoff(inputs=inputs)
            plan = result.pydantic.dict() if hasattr(result, "pydantic") and result.pydantic else {}
            tasks_count = len(plan.get("tasks", []))
            ms_count = len(plan.get("milestones", []))
            save_l1_plan(inputs=inputs, plan_data=plan)
            return f"L1 plan generated: {tasks_count} tasks, {ms_count} milestones. Saved to DB for project_id={project_id}."
        except Exception as exc:
            return f"L1 crew failed: {exc}"


class RunL2ReportTool(BaseTool):
    name: str = "run_l2_report"
    description: str = "Trigger the L2 AI progress report crew. Reads board/project data and generates a sprint report. Args: project_id."

    def _run(self, project_id: int = 0) -> str:
        try:
            from pmagent.main_l2 import crew as l2_crew
        except ImportError as exc:
            return f"Cannot import L2 crew: {exc}"

        from pmagent.db.repository import get_project
        from pmagent.db.session import get_session
        with get_session() as session:
            project = get_project(session, project_id)
            p_name = project.name if project else None
        if not project:
            return f"No project with id={project_id}"

        try:
            result = l2_crew.kickoff()
            raw = str(result.raw if hasattr(result, "raw") else result)
            usage = {}
            try:
                um = l2_crew.usage_metrics
                usage = um.dict() if hasattr(um, "dict") else dict(um)
            except Exception:
                pass
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            cost = 0.150 * (pt + ct) / 1_000_000

            from pmagent.persistence import save_l2_report
            save_l2_report(
                project_id=project_id,
                raw_report=raw,
                prompt_tokens=pt,
                completion_tokens=ct,
                estimated_cost_usd=cost,
                summary=raw[:500],
            )
            return f"L2 report generated and saved for '{p_name}'."
        except Exception as exc:
            return f"L2 crew failed: {exc}"


class LogDailyTool(BaseTool):
    name: str = "log_daily_standup"
    description: str = "Log a daily standup entry for a task. Args: task_id, team_member_id, yesterday, today, blockers, hours."

    def _run(
        self,
        task_id: int = 0,
        team_member_id: int = 0,
        yesterday: str = "",
        today: str = "",
        blockers: str = "",
        hours: float = 0.0,
    ) -> str:
        from pmagent.db.models import TeamMember
        from pmagent.db.repository import create_daily_log, get_team_member
        from pmagent.db.session import get_session
        if not task_id or not team_member_id:
            return "Error: task_id and team_member_id required."

        with get_session() as session:
            member = get_team_member(session, team_member_id)
            member_name = member.name if member else f"Member#{team_member_id}"
            log = create_daily_log(
                session=session,
                task_id=task_id,
                team_member_id=team_member_id,
                yesterday_progress=yesterday,
                today_plan=today,
                blockers=blockers,
                hours_logged=hours,
            )
            log_id = log.id
        return f"Daily log #{log_id} saved for Task#{task_id} by {member_name}"


class UpdateTaskStatusTool(BaseTool):
    name: str = "update_task_status"
    description: str = "Update a task's status. Args: task_id, status (todo/in_progress/in_review/done/blocked/cancelled)."

    def _run(self, task_id: int = 0, status: str = "") -> str:
        from pmagent.db.models import TaskStatus
        from pmagent.db.repository import update_task_status, get_task
        from pmagent.db.session import get_session
        try:
            ts = TaskStatus(status)
        except ValueError:
            return f"Invalid status '{status}'. Use: todo, in_progress, in_review, done, blocked, cancelled"
        with get_session() as session:
            update_task_status(session, task_id, ts)
            task = get_task(session, task_id)
        if not task:
            return f"No task with id={task_id}"
        return f"Task #{task_id} marked as '{ts.value}'"


class FindBlockersTool(BaseTool):
    name: str = "find_blockers"
    description: str = "Find all blocked or overdue tasks across a project. Args: project_id."

    def _run(self, project_id: int = 0) -> str:
        from pmagent.db.models import TaskStatus
        from pmagent.db.repository import get_project_tasks, get_team_members
        from pmagent.db.session import get_session

        with get_session() as session:
            tasks = list(get_project_tasks(session, project_id))
            members = list(get_team_members(session, project_id))
            tasks_plain    = _to_plain_dicts(tasks)
            members_plain  = _to_plain_dicts(members)

        member_map = {m["id"]: m["name"] for m in members_plain}
        today = date.today()

        BLOCKED = TaskStatus.blocked.value
        DONE    = TaskStatus.done.value
        blocked = [t for t in tasks_plain if t["status"] == BLOCKED]
        overdue = [
            t for t in tasks_plain
            if t["due_date"]
            and t["due_date"].date() < today
            and t["status"] != DONE
        ]

        def fmt(t):
            who = member_map.get(t["assigned_to_id"]) or "Unassigned"
            due = f" – due {t['due_date'].date()}" if t["due_date"] else ""
            return f"  [{t['id']}] {t['name']} – {who}{due}"

        lines = []
        if blocked:
            lines.append(f"BLOCKED ({len(blocked)}):")
            lines.extend(fmt(t) for t in blocked)
        if overdue:
            lines.append(f"\nOVERDUE ({len(overdue)}):")
            lines.extend(fmt(t) for t in overdue)
        if not lines:
            return f"No blockers or overdue tasks in project {project_id}."
        return "\n".join(lines)


class ReassignTaskTool(BaseTool):
    name: str = "reassign_task"
    description: str = "Reassign a task to a different team member. Args: task_id, new_member_id."

    def _run(self, task_id: int = 0, new_member_id: int = 0) -> str:
        from pmagent.db.repository import reassign_task, get_team_member
        from pmagent.db.session import get_session
        if not task_id or not new_member_id:
            return "Error: task_id and new_member_id required."
        with get_session() as session:
            task = reassign_task(session, task_id, new_member_id)
            member = get_team_member(session, new_member_id)
            member_name = member.name if member else f"Member#{new_member_id}"
            if not task:
                return f"No task with id={task_id}"
        return f"Task #{task_id} reassigned to {member_name}."


class CheckTeamWorkloadTool(BaseTool):
    name: str = "check_team_workload"
    description: str = "Show workload for all team members in a project. Args: project_id. Returns member name, role, and count of assigned tasks."

    def _run(self, project_id: int = 0) -> str:
        from pmagent.db.repository import get_team_members, get_project_tasks
        from pmagent.db.session import get_session
        with get_session() as session:
            members = list(get_team_members(session, project_id))
            tasks   = list(get_project_tasks(session, project_id))
            members_plain = _to_plain_dicts(members)
            tasks_plain   = _to_plain_dicts(tasks)

        member_map = {m["id"]: m["name"] for m in members_plain}
        workload: dict[int, int] = {}
        for t in tasks_plain:
            mid = t.get("assigned_to_id")
            if mid:
                workload[mid] = workload.get(mid, 0) + 1

        lines = [f"Team workload (project {project_id}):"]
        for m in members_plain:
            name = m["name"]
            role = m["role"]
            count = workload.get(m["id"], 0)
            lines.append(f"  {name} ({role}): {count} task(s)")
        return "\n".join(lines)


class UpdateMilestoneStatusTool(BaseTool):
    name: str = "update_milestone_status"
    description: str = "Update a milestone's status. Args: milestone_id, status (pending/on_track/at_risk/missed/achieved)."

    def _run(self, milestone_id: int = 0, status: str = "") -> str:
        from pmagent.db.models import MilestoneStatus
        from pmagent.db.repository import update_milestone_status
        from pmagent.db.session import get_session
        try:
            ms = MilestoneStatus(status)
        except ValueError:
            return f"Invalid status '{status}'. Use: pending, on_track, at_risk, missed, achieved"
        with get_session() as session:
            milestone = update_milestone_status(session, milestone_id, ms)
            if not milestone:
                return f"No milestone with id={milestone_id}"
        return f"Milestone #{milestone_id} marked as '{ms.value}'."


# ── Manager Agent ─────────────────────────────────────────────────────────────

def build_manager_agent() -> Agent:
    tools = [
        ListProjectsTool(),
        GetProjectTool(),
        CreateProjectTool(),
        RunL1PlanTool(),
        RunL2ReportTool(),
        LogDailyTool(),
        UpdateTaskStatusTool(),
        FindBlockersTool(),
        ReassignTaskTool(),
        CheckTeamWorkloadTool(),
        UpdateMilestoneStatusTool(),
    ]

    _config_dir = Path(__file__).resolve().parent / "config"
    with open(_config_dir / "agents.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    manager_cfg = cfg["manager_agent"]
    return Agent(
        role=manager_cfg["role"],
        goal=manager_cfg["goal"],
        backstory=manager_cfg["backstory"],
        allow_delegation=False,
        verbose=True,
        tools=tools,
    )


def build_manager_task() -> Task:
    _config_dir = Path(__file__).resolve().parent / "config"
    with open(_config_dir / "tasks.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    task_cfg = cfg["daily_management"]
    return Task(
        description=task_cfg["description"],
        expected_output=task_cfg["expected_output"],
        agent=build_manager_agent(),
    )


def build_manager_crew() -> Crew:
    return Crew(
        agents=[build_manager_agent()],
        tasks=[build_manager_task()],
        verbose=True,
    )


# ── Quick-run entrypoint ───────────────────────────────────────────────────────

if __name__ == "__main__":
    from pmagent.db.session import create_db
    create_db()
    print("Database created.\n")

    crew = build_manager_crew()
    result = crew.kickoff()
    print(result.raw)

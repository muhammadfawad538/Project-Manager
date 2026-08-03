# Line ending: LF
# Encoding: UTF-8

"""
Custom CrewAI tools for pmagent.

Each tool wraps a database operation so the manager agent can query and
update project state during crew runs.  Tools are registered in the agent
definition in agents.yaml and wired up in main.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from crewai.tools import BaseTool

from pmagent.db.models import ProjectStatus, TaskStatus, IssueStatus, IssuePriority, ChangeRequestStatus
from pmagent.db.repository import (
    create_project,
    add_team_member,
    get_project,
    list_projects,
    get_team_members,
    get_project_tasks,
    get_project_milestones,
    get_project_daily_logs,
    find_blockers,
    update_task_status,
    create_daily_log,
)
from pmagent.db.session import get_session


# ── Helpers ────────────────────────────────────────────────────────────────────

_COL = "—"


def _member_names(project_id: int) -> dict[int, str]:
    with get_session() as s:
        members = get_team_members(s, project_id)
    return {m.id: m.name for m in members}


def _fmt_date(d) -> str:
    return d.date().isoformat() if d else "TBD"


# ── Tools ──────────────────────────────────────────────────────────────────────


class ListProjectsTool(BaseTool):
    name: str = "list_projects"
    description: str = "List all projects with id, name, type, and status."

    def _run(self) -> str:
        with get_session() as s:
            projects = list_projects(s)
        if not projects:
            return "No projects found."
        return "\n".join(
            f"  [{p.id}] {p.name} ({p.project_type}) {_COL} {p.status.value}"
            for p in projects
        )


class GetProjectTool(BaseTool):
    name: str = "get_project"
    description: str = (
        "Get full project details by ID: team, tasks, milestones, daily logs. "
        "Arg: project_id (int)."
    )

    def _run(self, project_id: int = 0) -> str:
        if not project_id:
            return "Error: project_id is required."
        with get_session() as s:
            p = get_project(s, project_id)
        if not p:
            return f"No project with id={project_id}."
        members = get_team_members(s, project_id)
        tasks = get_project_tasks(s, project_id)
        milestones = get_project_milestones(s, project_id)
        logs = get_project_daily_logs(s, project_id)
        m_map = {m.id: m.name for m in members}
        lines = [
            f"Project: {p.name} (id={p.id})",
            f"  Type: {p.project_type} | Industry: {p.industry or 'N/A'}",
            f"  Status: {p.status.value} | Created: {_fmt_date(p.created_at)}",
            "",
            f"Team ({len(members)}):",
        ]
        lines.extend(f"  - {m.name} ({m.role}) — {m.availability_hours_per_week}h/wk" for m in members)
        lines += [
            "",
            f"Tasks ({len(tasks)}):",
        ]
        for t in tasks:
            assignee = m_map.get(t.assigned_to_id, "Unassigned")
            lines.append(
                f"  [{t.id}] {t.name} — {t.status.value} | "
                f"{t.progress_pct:.0f}% | {assignee} | due {_fmt_date(t.due_date)}"
            )
        lines += [
            "",
            f"Milestones ({len(milestones)}):",
        ]
        for m in milestones:
            lines.append(f"  [{m.id}] {m.name} — {m.status.value} — due {_fmt_date(m.due_date)}")
        lines += [
            "",
            f"Recent logs ({len(logs)}):",
        ]
        for l in logs[-5:]:
            lines.append(
                f"  [{_fmt_date(l.log_date)}] Task#{l.task_id}: "
                f"{(l.yesterday_progress or '(no note)')[:60]}"
            )
        return "\n".join(lines)


class FindBlockersTool(BaseTool):
    name: str = "find_blockers"
    description: str = (
        "Find all blocked or overdue tasks in a project. "
        "Arg: project_id (int)."
    )

    def _run(self, project_id: int = 0) -> str:
        if not project_id:
            return "Error: project_id is required."
        with get_session() as s:
            blockers = find_blockers(s, project_id)
        if not blockers:
            return f"No blockers or overdue tasks in project {project_id}."
        m_map = _member_names(project_id)
        lines = [f"Blockers in project {project_id}:"]
        for b in blockers:
            who = m_map.get(b.get("assigned_to_id"), "Unassigned")
            due = _fmt_date(b.get("due_date"))
            kind = "🔴 BLOCKED" if b.get("status") == TaskStatus.blocked.value else "⚠️ OVERDUE"
            lines.append(f"  {kind} [{b['id']}] {b['name']} — {who} — due {due}")
        return "\n".join(lines)


class CheckTeamWorkloadTool(BaseTool):
    name: str = "check_team_workload"
    description: str = (
        "Show workload for all team members in a project. "
        "Arg: project_id (int)."
    )

    def _run(self, project_id: int = 0) -> str:
        if not project_id:
            return "Error: project_id is required."
        with get_session() as s:
            members = get_team_members(s, project_id)
            tasks = get_project_tasks(s, project_id)
        m_map = {m.id: m.name for m in members}
        workload: dict[str, int] = {}
        for t in tasks:
            mid = t.assigned_to_id
            if mid and mid in m_map:
                workload[m_map[mid]] = workload.get(m_map[mid], 0) + 1
        lines = [f"Team workload (project {project_id}):"]
        for m in members:
            count = workload.get(m.name, 0)
            lines.append(f"  {m.name} ({m.role}): {count} task(s)")
        return "\n".join(lines)


class UpdateTaskStatusTool(BaseTool):
    name: str = "update_task_status"
    description: str = (
        "Update a task's status. "
        "Args: task_id (int), status (todo/in_progress/in_review/done/blocked/cancelled)."
    )

    def _run(self, task_id: int = 0, status: str = "") -> str:
        if not task_id or not status:
            return "Error: task_id and status are required."
        try:
            ts = TaskStatus(status.lower())
        except ValueError:
            return (
                f"Invalid status '{status}'. "
                "Use: todo, in_progress, in_review, done, blocked, cancelled"
            )
        with get_session() as s:
            update_task_status(s, task_id, ts)
        return f"Task #{task_id} marked as '{ts.value}'."


class LogDailyTool(BaseTool):
    name: str = "log_daily_standup"
    description: str = (
        "Log a daily standup entry. "
        "Args: task_id (int), team_member_id (int), yesterday (str), "
        "today (str), blockers (str), hours (float)."
    )

    def _run(
        self,
        task_id: int = 0,
        team_member_id: int = 0,
        yesterday: str = "",
        today: str = "",
        blockers: str = "",
        hours: float = 0.0,
    ) -> str:
        if not task_id or not team_member_id:
            return "Error: task_id and team_member_id are required."
        with get_session() as s:
            log = create_daily_log(
                s,
                task_id=task_id,
                team_member_id=team_member_id,
                yesterday_progress=yesterday,
                today_plan=today,
                blockers=blockers,
                hours_logged=hours,
            )
        return f"Daily log #{log.id} saved for Task#{task_id}."


class CreateProjectTool(BaseTool):
    name: str = "create_project"
    description: str = (
        "Create a new project in the database. "
        "Args: name, project_type, industry (opt), objectives (opt), "
        "requirements (opt), team_members as '- Name (Role)' lines (opt). "
        "Returns: project ID and confirmation."
    )

    def _run(
        self,
        name: str = "",
        project_type: str = "",
        industry: str = "",
        objectives: str = "",
        requirements: str = "",
        team_members: str = "",
    ) -> str:
        if not name or not project_type:
            return "Error: name and project_type are required."
        with get_session() as s:
            project = create_project(
                s,
                name=name,
                project_type=project_type,
                industry=industry,
                objectives=objectives,
                requirements=requirements,
            )
            pid = project.id
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
                    add_team_member(s, project_id=project.id, name=n, role=r)
                    added += 1
        return f"Project '{name}' created with id={pid}. {added} team member(s) added."


# ── Issue Log Tools ────────────────────────────────────────────────────────────


class CreateIssueTool(BaseTool):
    name: str = "create_issue"
    description: str = (
        "Log a new issue in the project. "
        "Args: project_id, title, description (opt), priority (low/medium/high/critical), "
        "task_id (opt), reported_by_id (opt). "
        "Returns: issue ID and confirmation."
    )

    def _run(
        self,
        project_id: int = 0,
        title: str = "",
        description: str = "",
        priority: str = "medium",
        task_id: int = 0,
        reported_by_id: int = 0,
    ) -> str:
        if not project_id or not title:
            return "Error: project_id and title are required."
        with get_session() as s:
            issue = create_issue(
                s,
                project_id=project_id,
                title=title,
                description=description,
                priority=priority,
                task_id=task_id or None,
                reported_by_id=reported_by_id or None,
            )
        return f"Issue #{issue.id} logged: '{title}' (priority: {priority})"


class ListIssuesTool(BaseTool):
    name: str = "list_issues"
    description: str = (
        "List issues for a project. "
        "Args: project_id, status (opt: open/in_progress/resolved/closed). "
        "Returns: issue summary with title, status, priority, assignee."
    )

    def _run(self, project_id: int = 0, status: str = "") -> str:
        if not project_id:
            return "Error: project_id is required."
        st = None
        if status:
            try:
                st = IssueStatus(status.lower())
            except ValueError:
                return f"Invalid status '{status}'. Use: open, in_progress, resolved, closed"
        with get_session() as s:
            issues = get_project_issues(s, project_id, status=st)
        if not issues:
            return f"No issues found for project {project_id}."
        lines = [f"Issues in project {project_id}:"]
        for i in issues:
            assignee = i.assigned_to.name if i.assigned_to else "Unassigned"
            lines.append(
                f"  [{i.id}] {i.title} — {i.status.value} | {i.priority.value} | {assignee}"
            )
        return "\n".join(lines)


class UpdateIssueStatusTool(BaseTool):
    name: str = "update_issue_status"
    description: str = (
        "Update an issue's status. "
        "Args: issue_id, status (open/in_progress/resolved/closed), resolution_notes (opt)."
    )

    def _run(self, issue_id: int = 0, status: str = "", resolution_notes: str = "") -> str:
        if not issue_id or not status:
            return "Error: issue_id and status are required."
        try:
            st = IssueStatus(status.lower())
        except ValueError:
            return f"Invalid status '{status}'. Use: open, in_progress, resolved, closed"
        with get_session() as s:
            issue = update_issue_status(s, issue_id, st, resolution_notes=resolution_notes)
        if not issue:
            return f"Issue #{issue_id} not found."
        return f"Issue #{issue_id} marked as '{st.value}'."


class AssignIssueTool(BaseTool):
    name: str = "assign_issue"
    description: str = (
        "Assign an issue to a team member. "
        "Args: issue_id, member_id."
    )

    def _run(self, issue_id: int = 0, member_id: int = 0) -> str:
        if not issue_id or not member_id:
            return "Error: issue_id and member_id are required."
        with get_session() as s:
            issue = assign_issue(s, issue_id, member_id)
        if not issue:
            return f"Issue #{issue_id} not found."
        return f"Issue #{issue_id} assigned to team member #{member_id}."


# ── Change Request Tools ──────────────────────────────────────────────────────


class CreateChangeRequestTool(BaseTool):
    name: str = "create_change_request"
    description: str = (
        "Create a formal change request for a project. "
        "Args: project_id, title, description (opt), justification (opt), "
        "impact_scope (opt: budget/schedule/scope), submitted_by_id (opt). "
        "Returns: change request ID and confirmation."
    )

    def _run(
        self,
        project_id: int = 0,
        title: str = "",
        description: str = "",
        justification: str = "",
        impact_scope: str = "",
        submitted_by_id: int = 0,
    ) -> str:
        if not project_id or not title:
            return "Error: project_id and title are required."
        with get_session() as s:
            cr = create_change_request(
                s,
                project_id=project_id,
                title=title,
                description=description,
                justification=justification,
                impact_scope=impact_scope,
                submitted_by_id=submitted_by_id or None,
            )
        return f"Change Request #{cr.id} submitted: '{title}' (status: {cr.status.value})"


class ListChangeRequestsTool(BaseTool):
    name: str = "list_change_requests"
    description: str = (
        "List change requests for a project. "
        "Args: project_id, status (opt: submitted/under_review/approved/rejected/implemented). "
        "Returns: CR summary with title, status, impact, submitter."
    )

    def _run(self, project_id: int = 0, status: str = "") -> str:
        if not project_id:
            return "Error: project_id is required."
        st = None
        if status:
            try:
                st = ChangeRequestStatus(status.lower())
            except ValueError:
                return f"Invalid status '{status}'. Use: submitted, under_review, approved, rejected, implemented"
        with get_session() as s:
            crs = get_project_change_requests(s, project_id, status=st)
        if not crs:
            return f"No change requests found for project {project_id}."
        lines = [f"Change Requests in project {project_id}:"]
        for cr in crs:
            submitter = cr.submitted_by.name if cr.submitted_by else "Unknown"
            lines.append(
                f"  [{cr.id}] {cr.title} — {cr.status.value} | Impact: {cr.impact_scope or 'Not specified'} | By: {submitter}"
            )
        return "\n".join(lines)


class UpdateChangeRequestStatusTool(BaseTool):
    name: str = "update_change_request_status"
    description: str = (
        "Update a change request status (approve/reject/etc). "
        "Args: cr_id, status (submitted/under_review/approved/rejected/implemented), "
        "approved_by_id (opt)."
    )

    def _run(self, cr_id: int = 0, status: str = "", approved_by_id: int = 0) -> str:
        if not cr_id or not status:
            return "Error: cr_id and status are required."
        try:
            st = ChangeRequestStatus(status.lower())
        except ValueError:
            return f"Invalid status '{status}'. Use: submitted, under_review, approved, rejected, implemented"
        with get_session() as s:
            cr = update_change_request_status(
                s, cr_id, st, approved_by_id=approved_by_id or None
            )
        if not cr:
            return f"Change Request #{cr_id} not found."
        return f"Change Request #{cr_id} updated to '{st.value}'."

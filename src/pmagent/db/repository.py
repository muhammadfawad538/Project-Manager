# Line ending: LF
# Encoding: UTF-8

"""
Database repository functions for pmagent.

Each function encapsulates a database operation so callers never touch
the session directly.  Import these from tools, crews, or API handlers.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from pmagent.db.models import (
    ProjectStatus,
    TaskStatus,
    MilestoneStatus,
    Priority,
    IssueStatus,
    IssuePriority,
    ChangeRequestStatus,
    Project,
    Task,
    TeamMember,
    Milestone,
    DailyLog,
    SprintReport,
    Issue,
    ChangeRequest,
)
from pmagent.db.session import get_session


# ── Projects ──────────────────────────────────────────────────────────────────


def create_project(
    session,
    *,
    name: str,
    project_type: str,
    industry: str = "",
    objectives: str = "",
    requirements: str = "",
    l1_inputs: str = "",
) -> Project:
    project = Project(
        name=name,
        project_type=project_type,
        industry=industry,
        objectives=objectives,
        requirements=requirements,
        l1_inputs=l1_inputs,
    )
    session.add(project)
    session.flush()
    return project


def get_project(session, project_id: int) -> Optional[Project]:
    return session.query(Project).filter(Project.id == project_id).first()


def list_projects(session, status: Optional[ProjectStatus] = None):
    query = session.query(Project)
    if status:
        query = query.filter(Project.status == status)
    return query.order_by(Project.created_at.desc()).all()


def update_project_status(session, project_id: int, status: ProjectStatus) -> Optional[Project]:
    project = get_project(session, project_id)
    if project:
        project.status = status
        session.flush()
    return project


# ── Team Members ───────────────────────────────────────────────────────────────


def add_team_member(
    session,
    *,
    project_id: int,
    name: str,
    role: str,
    availability_hours_per_week: float = 40.0,
) -> TeamMember:
    member = TeamMember(
        project_id=project_id,
        name=name,
        role=role,
        availability_hours_per_week=availability_hours_per_week,
    )
    session.add(member)
    session.flush()
    return member


def get_team_members(session, project_id: int):
    return session.query(TeamMember).filter(TeamMember.project_id == project_id).all()


def get_team_member(session, member_id: int) -> Optional[TeamMember]:
    return session.query(TeamMember).filter(TeamMember.id == member_id).first()


# ── Tasks ─────────────────────────────────────────────────────────────────────


def create_task(
    session,
    *,
    project_id: int,
    name: str,
    description: str = "",
    estimated_hours: float = 0.0,
    priority: str = "medium",
    due_date: Optional[datetime] = None,
    assigned_to_id: Optional[int] = None,
    dependencies: str = "",
) -> Task:
    task = Task(
        project_id=project_id,
        name=name,
        description=description,
        estimated_hours=estimated_hours,
        priority=Priority(priority),
        due_date=due_date,
        assigned_to_id=assigned_to_id,
        dependencies=dependencies,
    )
    session.add(task)
    session.flush()
    return task


def get_task(session, task_id: int) -> Optional[Task]:
    return session.query(Task).filter(Task.id == task_id).first()


def get_project_tasks(session, project_id: int):
    return session.query(Task).filter(Task.project_id == project_id).all()


def update_task_status(session, task_id: int, status: TaskStatus) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.status = status
        session.flush()
    return task


def update_task_progress(session, task_id: int, progress_pct: float) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.progress_pct = max(0.0, min(100.0, progress_pct))
        session.flush()
    return task


def reassign_task(session, task_id: int, new_member_id: int) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.assigned_to_id = new_member_id
        session.flush()
    return task


def find_blockers(session, project_id: int) -> list[dict]:
    """Return tasks that are blocked or overdue for a project."""
    today = datetime.utcnow().date()
    tasks = get_project_tasks(session, project_id)
    results = []
    for t in tasks:
        if t.status == TaskStatus.blocked:
            results.append({
                "id": t.id,
                "name": t.name,
                "status": t.status.value,
                "assigned_to_id": t.assigned_to_id,
                "due_date": t.due_date,
            })
        elif t.due_date and t.due_date.date() < today and t.status not in (
            TaskStatus.done,
            TaskStatus.cancelled,
        ):
            results.append({
                "id": t.id,
                "name": t.name,
                "status": t.status.value,
                "assigned_to_id": t.assigned_to_id,
                "due_date": t.due_date,
            })
    return results


# ── Milestones ────────────────────────────────────────────────────────────────


def create_milestone(
    session,
    *,
    project_id: int,
    name: str,
    description: str = "",
    due_date: Optional[datetime] = None,
) -> Milestone:
    milestone = Milestone(
        project_id=project_id,
        name=name,
        description=description,
        due_date=due_date,
    )
    session.add(milestone)
    session.flush()
    return milestone


def get_project_milestones(session, project_id: int):
    return session.query(Milestone).filter(Milestone.project_id == project_id).all()


def update_milestone_status(
    session, milestone_id: int, status: MilestoneStatus
) -> Optional[Milestone]:
    milestone = session.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone:
        milestone.status = status
        session.flush()
    return milestone


# ── Daily Logs ────────────────────────────────────────────────────────────────


def create_daily_log(
    session,
    *,
    task_id: int,
    team_member_id: int,
    project_id: int,
    yesterday_progress: str = "",
    today_plan: str = "",
    blockers: str = "",
    hours_logged: float = 0.0,
) -> DailyLog:
    log = DailyLog(
        project_id=project_id,
        task_id=task_id,
        team_member_id=team_member_id,
        yesterday_progress=yesterday_progress,
        today_plan=today_plan,
        blockers=blockers,
        hours_logged=hours_logged,
    )
    session.add(log)
    session.flush()
    return log


def get_project_daily_logs(session, project_id: int):
    return session.query(DailyLog).filter(DailyLog.project_id == project_id).order_by(DailyLog.log_date.desc()).all()


# ── Sprint Reports ────────────────────────────────────────────────────────────


def save_sprint_report(
    session,
    *,
    project_id: int,
    raw_report: str = "",
    summary: str = "",
    blockers: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    report_period_end: Optional[datetime] = None,
) -> SprintReport:
    report = SprintReport(
        project_id=project_id,
        raw_report=raw_report,
        summary=summary,
        blockers=blockers,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost_usd,
        report_period_end=report_period_end,
    )
    session.add(report)
    session.flush()
    return report


def get_sprint_reports(session, project_id: int):
    return session.query(SprintReport).filter(SprintReport.project_id == project_id).order_by(SprintReport.created_at.desc()).all()


# ── Issues ────────────────────────────────────────────────────────────────────


def create_issue(
    session,
    *,
    project_id: int,
    title: str,
    description: str = "",
    priority: str = "medium",
    task_id: int | None = None,
    reported_by_id: int | None = None,
) -> Issue:
    issue = Issue(
        project_id=project_id,
        title=title,
        description=description,
        priority=IssuePriority(priority),
        task_id=task_id,
        reported_by_id=reported_by_id,
    )
    session.add(issue)
    session.flush()
    return issue


def get_project_issues(session, project_id: int, status: IssueStatus | None = None):
    query = session.query(Issue).filter(Issue.project_id == project_id)
    if status:
        query = query.filter(Issue.status == status)
    return query.order_by(
        Issue.priority.desc(), Issue.created_at.desc()
    ).all()


def get_issue(session, issue_id: int) -> Issue | None:
    return session.query(Issue).filter(Issue.id == issue_id).first()


def update_issue_status(
    session, issue_id: int, status: IssueStatus, resolution_notes: str = ""
) -> Issue | None:
    issue = get_issue(session, issue_id)
    if issue:
        issue.status = status
        if resolution_notes:
            issue.resolution_notes = resolution_notes
        if status in (IssueStatus.resolved, IssueStatus.closed) and not issue.resolved_at:
            from datetime import datetime as dt
            issue.resolved_at = dt.utcnow()
        session.flush()
    return issue


def assign_issue(session, issue_id: int, member_id: int) -> Issue | None:
    issue = get_issue(session, issue_id)
    if issue:
        issue.assigned_to_id = member_id
        session.flush()
    return issue


# ── Change Requests ───────────────────────────────────────────────────────────


def create_change_request(
    session,
    *,
    project_id: int,
    title: str,
    description: str = "",
    justification: str = "",
    impact_scope: str = "",
    submitted_by_id: int | None = None,
) -> ChangeRequest:
    cr = ChangeRequest(
        project_id=project_id,
        title=title,
        description=description,
        justification=justification,
        impact_scope=impact_scope,
        submitted_by_id=submitted_by_id,
    )
    session.add(cr)
    session.flush()
    return cr


def get_project_change_requests(session, project_id: int, status: ChangeRequestStatus | None = None):
    query = session.query(ChangeRequest).filter(ChangeRequest.project_id == project_id)
    if status:
        query = query.filter(ChangeRequest.status == status)
    return query.order_by(ChangeRequest.created_at.desc()).all()


def get_change_request(session, cr_id: int) -> ChangeRequest | None:
    return session.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()


def update_change_request_status(
    session,
    cr_id: int,
    status: ChangeRequestStatus,
    approved_by_id: int | None = None,
) -> ChangeRequest | None:
    cr = get_change_request(session, cr_id)
    if cr:
        cr.status = status
        if approved_by_id:
            cr.approved_by_id = approved_by_id
        if status == ChangeRequestStatus.approved:
            from datetime import datetime as dt
            cr.decision_date = dt.utcnow()
        if status == ChangeRequestStatus.implemented:
            from datetime import datetime as dt
            cr.implemented_at = dt.utcnow()
        session.flush()
    return cr


def delete_issue(session, issue_id: int) -> bool:
    issue = get_issue(session, issue_id)
    if issue:
        session.delete(issue)
        session.flush()
        return True
    return False


def delete_change_request(session, cr_id: int) -> bool:
    cr = get_change_request(session, cr_id)
    if cr:
        session.delete(cr)
        session.flush()
        return True
    return False

# Line ending: LF
# Encoding: UTF-8

"""
CRUD helpers for the pmagent database.

All functions accept an optional ``session`` parameter.  If omitted, a
new session is opened and closed automatically.
"""

from datetime import datetime
from typing import Optional

from pmagent.db.models import (
    Project,
    Task,
    TeamMember,
    TaskDependency,
    DailyLog,
    SprintReport,
    Milestone,
    ProjectStatus,
    TaskStatus,
    MilestoneStatus,
)

# ── Projects ────────────────────────────────────────────────────────────────────

def create_project(
    *,
    session,
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
        status=ProjectStatus.active,
    )
    session.add(project)
    session.flush()
    return project


def get_project(session, project_id: int) -> Optional[Project]:
    return session.query(Project).filter(Project.id == project_id).first()


def get_project_by_name(session, name: str) -> Optional[Project]:
    return session.query(Project).filter(Project.name == name).first()


def list_projects(session, status: Optional[ProjectStatus] = None) -> list[Project]:
    q = session.query(Project)
    if status:
        q = q.filter(Project.status == status)
    return q.order_by(Project.updated_at.desc()).all()


def update_project_status(session, project_id: int, status: ProjectStatus) -> Optional[Project]:
    project = get_project(session, project_id)
    if project:
        project.status = status
    return project


# ── Team Members ────────────────────────────────────────────────────────────────

def add_team_member(
    *,
    session,
    project_id: int,
    name: str,
    role: str,
    skills: str = "",
    availability_hours_per_week: float = 40.0,
) -> TeamMember:
    member = TeamMember(
        project_id=project_id,
        name=name,
        role=role,
        skills=skills,
        availability_hours_per_week=availability_hours_per_week,
    )
    session.add(member)
    session.flush()
    return member


def get_team_members(session, project_id: int) -> list[TeamMember]:
    return session.query(TeamMember).filter(TeamMember.project_id == project_id).all()


def get_team_member(session, member_id: int) -> Optional[TeamMember]:
    return session.query(TeamMember).filter(TeamMember.id == member_id).first()


# ── Tasks ───────────────────────────────────────────────────────────────────────

def create_task(
    *,
    session,
    project_id: int,
    name: str,
    description: str = "",
    estimated_hours: Optional[float] = None,
    priority: str = "medium",
    due_date: Optional[datetime] = None,
    assigned_to_id: Optional[int] = None,
) -> Task:
    task = Task(
        project_id=project_id,
        name=name,
        description=description,
        estimated_hours=estimated_hours,
        status=TaskStatus.todo,
    )
    if due_date:
        task.due_date = due_date
    if assigned_to_id:
        task.assigned_to_id = assigned_to_id
    session.add(task)
    session.flush()
    return task


def get_task(session, task_id: int) -> Optional[Task]:
    return session.query(Task).filter(Task.id == task_id).first()


def get_project_tasks(session, project_id: int) -> list[Task]:
    return session.query(Task).filter(Task.project_id == project_id).order_by(Task.id).all()


def update_task_status(session, task_id: int, status: TaskStatus) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.status = status
        if status == TaskStatus.done and not task.completion_date:
            task.completion_date = datetime.utcnow()
            task.progress_pct = 100.0
    return task


def update_task_progress(session, task_id: int, progress_pct: float) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.progress_pct = max(0.0, min(100.0, progress_pct))
        if task.progress_pct >= 100.0:
            task.status = TaskStatus.done
            task.completion_date = datetime.utcnow()
        elif task.progress_pct > 0.0 and task.status == TaskStatus.todo:
            task.status = TaskStatus.in_progress
    return task


def set_task_actual_hours(session, task_id: int, actual_hours: float) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.actual_hours = actual_hours
    return task


def reassign_task(session, task_id: int, new_member_id: int) -> Optional[Task]:
    task = get_task(session, task_id)
    if task:
        task.assigned_to_id = new_member_id
    return task


def delete_task(session, task_id: int) -> bool:
    task = get_task(session, task_id)
    if not task:
        return False
    session.delete(task)
    return True


# ── Task Dependencies ──────────────────────────────────────────────────────────

def add_dependency(
    *,
    session,
    project_id: int,
    task_id: int,
    depends_on_task_id: int,
) -> TaskDependency:
    dep = TaskDependency(
        project_id=project_id,
        task_id=task_id,
        depends_on_task_id=depends_on_task_id,
    )
    session.add(dep)
    session.flush()
    return dep


def get_task_dependencies(session, task_id: int) -> list[TaskDependency]:
    return session.query(TaskDependency).filter(TaskDependency.task_id == task_id).all()


# ── Daily Logs ──────────────────────────────────────────────────────────────────

def create_daily_log(
    *,
    session,
    task_id: int,
    team_member_id: int,
    yesterday_progress: str = "",
    today_plan: str = "",
    blockers: str = "",
    hours_logged: float = 0.0,
    log_date: Optional[datetime] = None,
) -> DailyLog:
    log = DailyLog(
        task_id=task_id,
        team_member_id=team_member_id,
        yesterday_progress=yesterday_progress,
        today_plan=today_plan,
        blockers=blockers,
        hours_logged=hours_logged,
        log_date=log_date or datetime.utcnow(),
    )
    session.add(log)
    session.flush()
    return log


def get_task_daily_logs(session, task_id: int) -> list[DailyLog]:
    return session.query(DailyLog).filter(DailyLog.task_id == task_id).order_by(DailyLog.log_date.desc()).all()


def get_project_daily_logs(session, project_id: int) -> list[DailyLog]:
    return (
        session.query(DailyLog)
        .join(Task, DailyLog.task_id == Task.id)
        .filter(Task.project_id == project_id)
        .order_by(DailyLog.log_date.desc())
        .all()
    )


# ── Sprint Reports ──────────────────────────────────────────────────────────────

def save_sprint_report(
    *,
    session,
    project_id: int,
    raw_report: str,
    summary: str = "",
    blockers: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    report_period_start: Optional[datetime] = None,
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
        report_period_start=report_period_start,
        report_period_end=report_period_end,
    )
    session.add(report)
    session.flush()
    return report


def get_sprint_reports(session, project_id: int) -> list[SprintReport]:
    return (
        session.query(SprintReport)
        .filter(SprintReport.project_id == project_id)
        .order_by(SprintReport.created_at.desc())
        .all()
    )


# ── Milestones ─────────────────────────────────────────────────────────────────

def create_milestone(
    *,
    session,
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
        status=MilestoneStatus.pending,
    )
    session.add(milestone)
    session.flush()
    return milestone


def get_project_milestones(session, project_id: int) -> list[Milestone]:
    return (
        session.query(Milestone)
        .filter(Milestone.project_id == project_id)
        .order_by(Milestone.due_date.asc().nullsfirst())
        .all()
    )


def update_milestone_status(
    session, milestone_id: int, status: MilestoneStatus, completion_date: Optional[datetime] = None
) -> Optional[Milestone]:
    milestone = session.query(Milestone).filter(Milestone.id == milestone_id).first()
    if milestone:
        milestone.status = status
        if completion_date:
            milestone.completion_date = completion_date
        elif status == MilestoneStatus.achieved:
            milestone.completion_date = datetime.utcnow()
    return milestone

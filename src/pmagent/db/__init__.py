# Line ending: LF
# Encoding: UTF-8
"""Database package — models, session, and CRUD helpers."""

from pmagent.db.models import (
    Base,
    ProjectStatus,
    TaskStatus,
    MilestoneStatus,
    Priority,
    Project,
    TeamMember,
    Task,
    TaskDependency,
    DailyLog,
    SprintReport,
    Milestone,
)
from pmagent.db.session import (
    DATABASE_URL,
    engine,
    SessionLocal,
    create_db,
    drop_db,
    get_session,
    list_tables,
)
from pmagent.db.repository import (
    # Projects
    create_project,
    get_project,
    get_project_by_name,
    list_projects,
    update_project_status,
    # Team
    add_team_member,
    get_team_members,
    get_team_member,
    # Tasks
    create_task,
    get_task,
    get_project_tasks,
    update_task_status,
    update_task_progress,
    set_task_actual_hours,
    reassign_task,
    delete_task,
    # Dependencies
    add_dependency,
    get_task_dependencies,
    # Daily Logs
    create_daily_log,
    get_task_daily_logs,
    get_project_daily_logs,
    # Sprint Reports
    save_sprint_report,
    get_sprint_reports,
    # Milestones
    create_milestone,
    get_project_milestones,
    update_milestone_status,
)

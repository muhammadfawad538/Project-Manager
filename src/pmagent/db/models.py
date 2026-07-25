# Line ending: LF
# Encoding: UTF-8

"""
Database layer for pmagent.

Tables:
  projects         – top-level project records
  team_members     – people assigned to a project
  tasks            – task breakdown, estimates, actuals, status
  task_dependencies – blocker / predecessor links between tasks
  daily_logs       – daily standup entries per task
  sprint_reports   – L2 progress reports stored per run
  milestones       – milestone deadlines with status tracking
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, WriteOnlyMapped, mapped_column, relationship
import enum

Base = declarative_base()
Base.__allow_unmapped__ = True


# ── Enums ──────────────────────────────────────────────────────────────────────

class ProjectStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    paused = "paused"
    archived = "archived"


class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    in_review = "in_review"
    done = "done"
    blocked = "blocked"
    cancelled = "cancelled"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class MilestoneStatus(str, enum.Enum):
    pending = "pending"
    on_track = "on_track"
    at_risk = "at_risk"
    missed = "missed"
    achieved = "achieved"


# ── Models ─────────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(255), nullable=False)
    project_type: str = Column(String(255), nullable=False)
    industry: str = Column(String(100), nullable=True)
    objectives: str = Column(Text, nullable=True)
    requirements: str = Column(Text, nullable=True)

    # L1 inputs snapshot (stored so we can re-run crew with same data)
    l1_inputs: str = Column(Text, nullable=True)

    status: ProjectStatus = Column(Enum(ProjectStatus), default=ProjectStatus.active, nullable=False)
    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    team_members: list["TeamMember"] = relationship("TeamMember", back_populates="project", cascade="all, delete-orphan")
    tasks: list["Task"] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    milestones: list["Milestone"] = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    sprint_reports: list["SprintReport"] = relationship("SprintReport", back_populates="project", cascade="all, delete-orphan")


class TeamMember(Base):
    __tablename__ = "team_members"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    project_id: int = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name: str = Column(String(100), nullable=False)
    role: str = Column(String(100), nullable=False)
    skills: str = Column(Text, nullable=True)
    availability_hours_per_week: float = Column(Float, default=40.0, nullable=False)

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project: Project = relationship("Project", back_populates="team_members")
    tasks_assigned: list["Task"] = relationship("Task", back_populates="assigned_to")
    daily_logs: list["DailyLog"] = relationship("DailyLog", back_populates="team_member")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_task_project_name"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    project_id: int = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name: str = Column(String(255), nullable=False)
    description: str = Column(Text, nullable=True)

    # Estimates (from L1 crew)
    estimated_hours: float = Column(Float, nullable=True)

    # Actuals (updated during daily work)
    actual_hours: float = Column(Float, default=0.0, nullable=False)

    # Dates
    start_date: Optional[datetime] = Column(DateTime, nullable=True)
    due_date: Optional[datetime] = Column(DateTime, nullable=True)
    completion_date: Optional[datetime] = Column(DateTime, nullable=True)

    # Status tracking
    status: TaskStatus = Column(Enum(TaskStatus), default=TaskStatus.todo, nullable=False)
    priority: Priority = Column(Enum(Priority), default=Priority.medium, nullable=False)
    progress_pct: float = Column(Float, default=0.0, nullable=False)  # 0–100

    # Assignment
    assigned_to_id: Optional[int] = Column(Integer, ForeignKey("team_members.id"), nullable=True)

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project: Project = relationship("Project", back_populates="tasks")
    assigned_to: Optional[TeamMember] = relationship("TeamMember", back_populates="tasks_assigned")
    dependencies_as_blocker: list["TaskDependency"] = relationship(
        "TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="blocker_task", cascade="all, delete-orphan"
    )
    dependencies_as_blocked: list["TaskDependency"] = relationship(
        "TaskDependency", foreign_keys="TaskDependency.depends_on_task_id", back_populates="blocked_task", cascade="all, delete-orphan"
    )
    daily_logs: list["DailyLog"] = relationship("DailyLog", back_populates="task")


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint("task_id", "depends_on_task_id", name="uq_dependency"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    project_id: int = Column(Integer, ForeignKey("projects.id"), nullable=False)
    task_id: int = Column(Integer, ForeignKey("tasks.id"), nullable=False)  # the task that is blocked
    depends_on_task_id: int = Column(Integer, ForeignKey("tasks.id"), nullable=False)  # the task that must finish first

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    blocker_task: Task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies_as_blocker")
    blocked_task: Task = relationship("Task", foreign_keys=[depends_on_task_id], back_populates="dependencies_as_blocked")


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    task_id: int = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    team_member_id: int = Column(Integer, ForeignKey("team_members.id"), nullable=False)
    log_date: datetime = Column(DateTime, nullable=False, server_default=func.now())

    yesterday_progress: str = Column(Text, nullable=True)
    today_plan: str = Column(Text, nullable=True)
    blockers: str = Column(Text, nullable=True)
    hours_logged: float = Column(Float, default=0.0, nullable=False)

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    task: Task = relationship("Task", back_populates="daily_logs")
    team_member: TeamMember = relationship("TeamMember", back_populates="daily_logs")


class SprintReport(Base):
    __tablename__ = "sprint_reports"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    project_id: int = Column(Integer, ForeignKey("projects.id"), nullable=False)

    # Report metadata
    report_period_start: Optional[datetime] = Column(DateTime, nullable=True)
    report_period_end: Optional[datetime] = Column(DateTime, nullable=True)

    # Raw output from L2 crew
    raw_report: str = Column(Text, nullable=True)

    # Parsed summary (filled by analysis agent or post-processing)
    summary: str = Column(Text, nullable=True)
    blockers: str = Column(Text, nullable=True)

    # Usage metrics from crew run
    prompt_tokens: int = Column(Integer, default=0, nullable=False)
    completion_tokens: int = Column(Integer, default=0, nullable=False)
    estimated_cost_usd: float = Column(Float, default=0.0, nullable=False)

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)

    # Relationships
    project: Project = relationship("Project", back_populates="sprint_reports")


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_milestone_project_name"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    project_id: int = Column(Integer, ForeignKey("projects.id"), nullable=False)

    name: str = Column(String(255), nullable=False)
    description: str = Column(Text, nullable=True)

    due_date: Optional[datetime] = Column(DateTime, nullable=True)
    completion_date: Optional[datetime] = Column(DateTime, nullable=True)

    status: MilestoneStatus = Column(Enum(MilestoneStatus), default=MilestoneStatus.pending, nullable=False)

    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project: Project = relationship("Project", back_populates="milestones")

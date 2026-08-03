# Line ending: LF
# Encoding: UTF-8

"""
SQLAlchemy ORM models for pmagent.

Tables: projects, team_members, tasks, milestones, daily_logs, sprint_reports,
        issues, change_requests.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    Date,
    Boolean,
    ForeignKey,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────


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


class MilestoneStatus(str, enum.Enum):
    pending = "pending"
    on_track = "on_track"
    at_risk = "at_risk"
    missed = "missed"
    achieved = "achieved"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ── Models ────────────────────────────────────────────────────────────────────


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), default=ProjectStatus.active, nullable=False
    )
    objectives: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    l1_inputs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    team_members: Mapped[list["TeamMember"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    milestones: Mapped[list["Milestone"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    daily_logs: Mapped[list["DailyLog"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sprint_reports: Mapped[list["SprintReport"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    issues: Mapped[list["Issue"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    change_requests: Mapped[list["ChangeRequest"]] = relationship(back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_projects_status", "status"),)


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    availability_hours_per_week: Mapped[float] = mapped_column(Float, default=40.0)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="team_members")
    assigned_tasks: Mapped[list["Task"]] = relationship(back_populates="assigned_to")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus), default=TaskStatus.todo, nullable=False
    )
    priority: Mapped[Priority] = mapped_column(SAEnum(Priority), default=Priority.medium, nullable=False)
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0)
    actual_hours: Mapped[float] = mapped_column(Float, default=0.0)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)
    due_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    dependencies: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="tasks")
    assigned_to: Mapped[Optional["TeamMember"]] = relationship(back_populates="assigned_tasks")
    daily_logs: Mapped[list["DailyLog"]] = relationship(back_populates="task")

    __table_args__ = (
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_due_date", "due_date"),
    )


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[MilestoneStatus] = mapped_column(
        SAEnum(MilestoneStatus), default=MilestoneStatus.pending, nullable=False
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="milestones")


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    team_member_id: Mapped[int] = mapped_column(ForeignKey("team_members.id"), nullable=False)
    log_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    yesterday_progress: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    today_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hours_logged: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="daily_logs")
    task: Mapped["Task"] = relationship(back_populates="daily_logs")


class SprintReport(Base):
    __tablename__ = "sprint_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    report_period_end: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="sprint_reports")


# ── Issue Log ─────────────────────────────────────────────────────────────────


class IssueStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    closed = "closed"


class IssuePriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        SAEnum(IssueStatus), default=IssueStatus.open, nullable=False
    )
    priority: Mapped[IssuePriority] = mapped_column(
        SAEnum(IssuePriority), default=IssuePriority.medium, nullable=False
    )
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="issues")
    task: Mapped[Optional["Task"]] = relationship()
    reported_by: Mapped[Optional["TeamMember"]] = relationship(foreign_keys=[reported_by_id])
    assigned_to: Mapped[Optional["TeamMember"]] = relationship(foreign_keys=[assigned_to_id])


# ── Change Requests ───────────────────────────────────────────────────────────


class ChangeRequestStatus(str, enum.Enum):
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    implemented = "implemented"


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        SAEnum(ChangeRequestStatus), default=ChangeRequestStatus.submitted, nullable=False
    )
    impact_scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # budget, schedule, scope impact
    submitted_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("team_members.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decision_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    implemented_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="change_requests")
    submitted_by: Mapped[Optional["TeamMember"]] = relationship(foreign_keys=[submitted_by_id])
    approved_by: Mapped[Optional["TeamMember"]] = relationship(foreign_keys=[approved_by_id])

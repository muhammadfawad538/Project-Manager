# Line ending: LF
# Encoding: UTF-8

"""
Pydantic models for structured CrewAI output.

Each model corresponds to an agent's deliverable and is attached to its
task via `output_pydantic` in tasks.yaml.  This gives us validated,
typed output at every step of the crew pipeline.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ── WBS ────────────────────────────────────────────────────────────────────────


class TaskItem(BaseModel):
    """A single task in the Work Breakdown Structure."""

    id: str = Field(..., description="Hierarchical ID, e.g. '1.1', '2.3'")
    name: str = Field(..., description="Concise task name")
    description: str = Field(default="", description="One-line description of the work")
    owner: str = Field(..., description="Assigned team member name")
    estimated_hours: float = Field(..., description="Estimated effort in hours")
    due_date: str = Field(..., description="Due date (ISO YYYY-MM-DD)")
    dependencies: list[str] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    priority: str = Field(
        default="should",
        description="Priority level: must / should / nice-to-have",
    )


class Milestone(BaseModel):
    """A project milestone with associated task IDs."""

    name: str = Field(..., description="Milestone name")
    deliverable: str = Field(..., description="What is delivered at this milestone")
    due_date: str = Field(..., description="Due date (ISO YYYY-MM-DD)")
    task_ids: list[str] = Field(..., description="Task IDs belonging to this milestone")


class WBSOutput(BaseModel):
    """Complete Work Breakdown Structure from the project planner."""

    tasks: list[TaskItem] = Field(..., description="All WBS tasks")
    milestones: list[Milestone] = Field(..., description="Project milestones")
    critical_path: list[str] = Field(
        ..., description="Task IDs on the critical path in order"
    )
    assumptions: list[str] = Field(..., description="Planning assumptions made")
    total_estimated_hours: float = Field(..., description="Sum of all task estimates")
    calendar_duration_weeks: float = Field(
        ..., description="Estimated calendar duration in weeks"
    )


# ── Risk Register ──────────────────────────────────────────────────────────────


class RiskItem(BaseModel):
    """A single risk entry in the risk register."""

    id: str = Field(..., description="Risk ID, e.g. 'R1', 'R2'")
    description: str = Field(..., description="What could go wrong")
    category: str = Field(
        ...,
        description="Risk category: Technical / Team / Budget / Schedule / Stakeholder / Scope / Regulatory",
    )
    probability: str = Field(
        ..., description="Probability: High / Medium / Low"
    )
    impact: str = Field(..., description="Impact: High / Medium / Low")
    owner: str = Field(..., description="Person responsible for this risk")
    mitigation: str = Field(..., description="Preventive actions to reduce probability or impact")
    contingency: str = Field(..., description="Fallback plan if risk materializes")
    trigger: str = Field(..., description="Early warning signal to act")
    status: str = Field(default="Open", description="Open / Mitigated / Closed / Escalated")


class RiskRegisterOutput(BaseModel):
    """Complete risk register from the risk analyst."""

    risks: list[RiskItem] = Field(..., description="All identified risks")
    escalation_criteria: str = Field(
        ..., description="When a risk should be escalated to the steering committee"
    )


# ── Resource Allocation ────────────────────────────────────────────────────────


class AllocationEntry(BaseModel):
    """A single task-to-member allocation."""

    task_id: str = Field(..., description="WBS task ID")
    task_name: str = Field(..., description="Task name")
    assigned_to: str = Field(..., description="Team member name")
    estimated_hours: float = Field(..., description="Hours assigned")
    start_date: str = Field(..., description="Start date (ISO)")
    due_date: str = Field(..., description="Due date (ISO)")
    rationale: str = Field(
        default="", description="Why this person was chosen (skill match, load balance, etc.)"
    )


class MemberLoad(BaseModel):
    """Capacity and utilization for a single team member."""

    name: str = Field(..., description="Team member name")
    role: str = Field(..., description="Role / title")
    weekly_capacity_hours: float = Field(..., description="Available hours per week")
    assigned_hours: float = Field(..., description="Total hours assigned across all tasks")
    utilization_pct: float = Field(..., description="Assigned / capacity as percentage")
    status: str = Field(..., description="OK / Overloaded / Underutilized")
    tasks: list[str] = Field(
        default_factory=list, description="Task IDs assigned to this member"
    )


class ResourceAllocationOutput(BaseModel):
    """Complete resource allocation from the resource allocator."""

    allocations: list[AllocationEntry] = Field(..., description="Task-to-member assignments")
    member_loads: list[MemberLoad] = Field(..., description="Capacity per team member")
    rebalancing_plan: list[str] = Field(
        default_factory=list,
        description="Recommended task moves to fix overloads",
    )

# Line ending: LF
# Encoding: UTF-8
"""
Persistence helpers that bridge the AI crews with the database.

``save_l1_plan()``  – stores the L1 planning crew result as a Project +
                      TeamMember + Task + Milestone records.
``save_l2_report()`` – stores the L2 reporting crew result as a SprintReport.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pmagent.db.models import TeamMember, TaskStatus, Priority
from pmagent.db.session import get_session
from pmagent.db.repository import (
    add_team_member,
    create_milestone,
    create_project,
    create_task,
    save_sprint_report,
)


# ── L1 → DB ────────────────────────────────────────────────────────────────────

def save_l1_plan(
    inputs: dict[str, Any],
    plan_data: dict[str, Any],
    usage: dict[str, int] | None = None,
) -> int | None:
    """
    Persist the output of a L1 planning crew run.

    Returns:
        The ``project.id`` on success, or ``None`` on failure.
    """
    import json, traceback as _tb

    print("[DB] save_l1_plan: starting...")

    try:
        with get_session() as session:
            print(f"[DB] Creating project: {inputs.get('project_type', '?')}")
            project = create_project(
                session=session,
                name=inputs.get("project_type", "Unknown Project"),
                project_type=inputs.get("project_type", ""),
                industry=inputs.get("industry", ""),
                objectives=inputs.get("project_objectives", ""),
                requirements=inputs.get("project_requirements", ""),
                l1_inputs=json.dumps(inputs),
            )
            print(f"[DB] Project created: id={project.id}")

            # Team members
            members_row = (inputs.get("team_members") or "").strip()
            print(f"[DB] Parsing team members...")
            stored_members = _parse_and_store_team(session, project.id, members_row)
            print(f"[DB] Stored {len(stored_members)} team members")

            # Build name→id map for assignment matching
            member_name_map = {}
            for m in stored_members:
                member_name_map[m.name.strip().lower()] = m.id
            print(f"[DB] Member name map: {member_name_map}")

            # Tasks
            tasks_list = plan_data.get("tasks", [])
            print(f"[DB] Saving {len(tasks_list)} tasks...")
            due_offset = 0
            for i, t in enumerate(tasks_list):
                hours = _safe_float(t.get("estimated_time_hours"))
                due = datetime.utcnow() + timedelta(days=max(due_offset, 0))
                if hours:
                    due_offset += max(int(hours / 8), 1)

                assigned_name = (t.get("assigned_to") or "").strip().lower()
                assigned_to_id = member_name_map.get(assigned_name)
                task_name = t.get("task_name", "Unnamed Task")

                print(f"[DB]   Task {i+1}/{len(tasks_list)}: '{task_name}' "
                      f"| hours={hours} | assigned_to='{assigned_name}' → id={assigned_to_id}")

                create_task(
                    session=session,
                    project_id=project.id,
                    name=task_name,
                    description="",
                    estimated_hours=hours,
                    priority="medium",
                    due_date=due if hours else None,
                    assigned_to_id=assigned_to_id,
                )

            # Milestones
            milestones_list = plan_data.get("milestones", [])
            print(f"[DB] Saving {len(milestones_list)} milestones...")
            for m in milestones_list:
                due = datetime.utcnow() + timedelta(days=max(due_offset, 0))
                if due_offset:
                    due_offset = max(due_offset - 7, 0)
                ms_name = m.get("milestone_name", "Unnamed Milestone")
                print(f"[DB]   Milestone: '{ms_name}' due {due.date()}")
                create_milestone(
                    session=session,
                    project_id=project.id,
                    name=ms_name,
                    description="",
                    due_date=due,
                )

            print(f"[DB] Committing... project_id={project.id}")
            session.commit()
            print(f"[DB] ✅ Done! Returning project_id={project.id}")
            return project.id

    except Exception as exc:
        print(f"[DB] ❌ save_l1_plan FAILED: {exc}")
        _tb.print_exc()
        return None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


_DEFAULT_MEMBERS_DATA = """
- Ali (Site Engineer)
- Ahmed (Carpenter / Steel Worker)
- Usman (Electrician)
- Hassan (Plumber)
- Bilal (General Laborer)
"""


def _parse_and_store_team(session, project_id: int, members_block: str) -> list[TeamMember]:
    """Parse the ``team_members`` input block and create TeamMember rows."""
    members_block = (members_block or "").strip()
    if not members_block:
        members_block = _DEFAULT_MEMBERS_DATA

    entries = [line.strip("- ").strip() for line in members_block.splitlines() if line.strip()]
    stored: list[TeamMember] = []
    for entry in entries:
        name = entry
        role = "General"
        if "(" in entry:
            paren_idx = entry.index("(")
            name = entry[:paren_idx].strip()
            role = entry[paren_idx + 1 :].rstrip(")").strip()
        member = add_team_member(
            session=session,
            project_id=project_id,
            name=name,
            role=role,
        )
        stored.append(member)
    return stored


# ── L2 → DB ────────────────────────────────────────────────────────────────────

def save_l2_report(
    *,
    project_id: int,
    raw_report: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float = 0.0,
    summary: str = "",
    blockers: str = "",
) -> int | None:
    """
    Persist the output of a L2 reporting crew run.

    Returns the ``sprint_report.id`` on success, or ``None`` on failure.
    """
    try:
        with get_session() as session:
            report = save_sprint_report(
                session=session,
                project_id=project_id,
                raw_report=raw_report,
                summary=summary,
                blockers=blockers,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimated_cost_usd,
                report_period_end=datetime.utcnow(),
            )
            return report.id
    except Exception as exc:
        import traceback
        print(f"❌ save_l2_report failed: {exc}")
        traceback.print_exc()
        return None

# Line ending: LF
# Encoding: UTF-8

"""
Demo workflow: full agentic PM cycle.

Usage:
    python -m pmagent.workflow

This script demonstrates:
  1. L1 crew generates a project plan
  2. Plan is persisted to the database
  3. Manager agent reviews the project
  4. A daily standup log is written
  5. L2 crew generates a sprint report
  6. Report is persisted to the database
"""

from __future__ import annotations

import os
import sys

# ── Preflight ────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("OPENAI_API_KEY", "")
if not API_KEY:
    print("ERROR: OPENAI_API_KEY is not set. Add it to your .env file.")
    sys.exit(1)

# ── Step 1: Ensure DB exists ──────────────────────────────────────────────────
from pmagent.db.session import create_db
create_db()
print("✅ Database ready.\n")

# ── Step 2: L1 crew — generate plan ──────────────────────────────────────────
print("=" * 60)
from pmagent.main import kickoff

result = kickoff(persist=True)
project_id = result.get("project_id") or 1  # persistence returns id if saved

# ── Step 3: Inspect DB state ──────────────────────────────────────────────────
from pmagent.db.repository import get_project, get_project_tasks
from pmagent.db.session import get_session

with get_session() as session:
    p = get_project(session, project_id)
    tasks = get_project_tasks(session, project_id)

print(f"\n📋 Project loaded: {p.name} (id={p.id})")
print(f"   Tasks in DB: {len(tasks)}")
for t in tasks:
    who = t.assigned_to.name if t.assigned_to else "Unassigned"
    print(f"   [{t.id}] {t.name} – {t.status.value} | {t.progress_pct:.0f}% | {who}")

# ── Step 4: Simulate a daily standup ─────────────────────────────────────────
print("\n" + "=" * 60)
print("  Daily Standup – logging progress")
print("=" * 60)

from pmagent.db.repository import (
    get_team_members,
    update_task_progress,
    create_daily_log,
)

with get_session() as session:
    from pmagent.db.models import Task
    active_task = session.query(Task).filter(Task.project_id == project_id).first()
    sample_task_id = active_task.id if active_task else None

    all_members = list(get_team_members(session, project_id))
    sample_member_id = all_members[0].id if all_members else None
    sample_member_name = all_members[0].name if all_members else None

if sample_member_id and sample_task_id:
    with get_session() as session:
        update_task_progress(session, sample_task_id, 25.0)
        create_daily_log(
            session=session,
            task_id=sample_task_id,
            team_member_id=sample_member_id,
            yesterday_progress="Started excavation and foundation work",
            today_plan="Continue foundation concrete pouring",
            blockers="Waiting for cement delivery",
            hours_logged=6.0,
        )
    print(f"✅ Logged standup for {sample_member_name} on Task#{sample_task_id}")
else:
    print("⚠️  No members/tasks to log standup for.")

# ── Step 5: Manager agent review ──────────────────────────────────────────────
print("\n" + "=" * 60)
print("  PM Manager agent review")
print("=" * 60)

from pmagent.orchestrator import build_manager_agent, build_manager_task, build_manager_crew

manager = build_manager_crew()
# Quick kickoff with a focused prompt asking the manager to review the project
from crewai import Task

review_task = Task(
    description=(
        "Use list_projects to find the active project, then use get_project "
        f"to load full details for project_id={project_id}. "
        "Use find_blockers to surface any blocked or overdue tasks. "
        "Summarize the project health in 5 bullets: progress %, blockers, "
        "overdue tasks, workload issues, recommended next actions."
    ),
    expected_output="A 5-bullet project health summary in plain text.",
    agent=build_manager_agent(),
)
manager.tasks = [review_task]
result = manager.kickoff()
print(result.raw)

print("\n✅ Agentic PM workflow complete.")

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Full system test - runs the complete workflow and shows real output.
No API key needed - uses mock data for L1 and L2.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pmagent.db.session import create_db, get_session
from pmagent.db.models import TaskStatus
from pmagent.db.repository import (
    get_project_tasks, get_project_daily_logs, get_project_milestones,
    get_sprint_reports, update_task_progress, create_daily_log,
    update_task_status, get_project, get_team_members,
)
from pmagent.persistence import save_l1_plan, save_l2_report

# Clean DB
import os
db_path = PROJECT_ROOT / "data" / "app.db"
try:
    os.remove(db_path)
except FileNotFoundError:
    pass
except PermissionError:
    # DB is in use by another process - use a temp DB for this test
    db_path = PROJECT_ROOT / "data" / "app_test.db"
    try:
        os.remove(db_path)
    except FileNotFoundError:
        pass
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

create_db()

print("=" * 70)
print("  FULL SYSTEM TEST - LIVE OUTPUT")
print("=" * 70)
print()

# ============================================================================
# STEP 1: L1 Planning - Create project plan
# ============================================================================
print("=" * 70)
print("STEP 1: L1 Planning Crew - Generate Project Plan")
print("=" * 70)
print()

inputs = {
    "project_type": "FastAPI CRUD Backend",
    "project_objectives": "Build a simple REST API with create and delete endpoints",
    "industry": "IT",
    "team_members": "- Fawad (Backend Engineer)",
    "project_requirements": "\n".join([
        "Create POST /items endpoint",
        "Create DELETE /items/{id} endpoint",
        "Add input validation",
        "Add error handling",
    ]),
}

plan_data = {
    "tasks": [
        {"task_name": "Setup FastAPI Project", "estimated_time_hours": 4.0},
        {"task_name": "Create POST /items Endpoint", "estimated_time_hours": 8.0},
        {"task_name": "Create DELETE /items/{id} Endpoint", "estimated_time_hours": 6.0},
        {"task_name": "Add Input Validation", "estimated_time_hours": 6.0},
        {"task_name": "Add Error Handling", "estimated_time_hours": 6.0},
        {"task_name": "Write Unit Tests", "estimated_time_hours": 8.0},
        {"task_name": "Documentation", "estimated_time_hours": 4.0},
    ],
    "milestones": [
        {"milestone_name": "Project Setup Complete"},
        {"milestone_name": "CRUD Endpoints Done"},
        {"milestone_name": "Testing & Documentation Complete"},
    ],
}

print(f"Project Type: {inputs['project_type']}")
print(f"Industry: {inputs['industry']}")
print(f"Team: Fawad (Backend Engineer)")
print(f"Requirements: 4 items")
print()
print(f"L1 Plan generated:")
print(f"  Tasks: {len(plan_data['tasks'])}")
print(f"  Milestones: {len(plan_data['milestones'])}")
print()

project_id = save_l1_plan(inputs=inputs, plan_data=plan_data)
print(f"[OK] Project created with ID: {project_id}")
print()

# ============================================================================
# STEP 2: Show the plan
# ============================================================================
print("=" * 70)
print("STEP 2: Project Plan Details")
print("=" * 70)
print()

with get_session() as session:
    project = get_project(session, project_id)
    members = get_team_members(session, project_id)
    tasks = get_project_tasks(session, project_id)
    milestones = get_project_milestones(session, project_id)

    # Serialize
    p_name = project.name
    p_type = project.project_type
    p_status = project.status.value
    members_info = [{"id": m.id, "name": m.name, "role": m.role} for m in members]
    tasks_info = [{
        "id": t.id, "name": t.name, "status": t.status.value,
        "progress_pct": t.progress_pct, "estimated_hours": t.estimated_hours,
    } for t in tasks]
    milestones_info = [{"id": ms.id, "name": ms.name, "status": ms.status.value} for ms in milestones]

print(f"Project: {p_name}")
print(f"  Type: {p_type}")
print(f"  Status: {p_status}")
print()
print(f"Team ({len(members_info)} members):")
for m in members_info:
    print(f"  [{m['id']}] {m['name']} - {m['role']}")
print()
print(f"Tasks ({len(tasks_info)}):")
for t in tasks_info:
    print(f"  [{t['id']}] {t['name']}")
    print(f"       Estimated: {t['estimated_hours']}h | Status: {t['status']} | Progress: {t['progress_pct']}%")
print()
print(f"Milestones ({len(milestones_info)}):")
for ms in milestones_info:
    print(f"  [{ms['id']}] {ms['name']} - {ms['status']}")
print()

# ============================================================================
# STEP 3: Simulate daily work - log standups
# ============================================================================
print("=" * 70)
print("STEP 3: Daily Work - Log Standups (3 Days)")
print("=" * 70)
print()

task_id = tasks_info[0]["id"]
member_id = members_info[0]["id"]

daily_updates = [
    {"day": "Day 1", "yesterday": "N/A (first day)", "today": "Setup FastAPI project structure", "blockers": "None", "hours": 8.0},
    {"day": "Day 2", "yesterday": "Setup complete, created project structure", "today": "Implement POST /items endpoint", "blockers": "None", "hours": 8.0},
    {"day": "Day 3", "yesterday": "POST endpoint working, added basic validation", "today": "Implement DELETE endpoint", "blockers": "None", "hours": 8.0},
]

for update in daily_updates:
    with get_session() as session:
        create_daily_log(
            session=session,
            task_id=task_id,
            team_member_id=member_id,
            yesterday_progress=update["yesterday"],
            today_plan=update["today"],
            blockers=update["blockers"],
            hours_logged=update["hours"],
        )

    print(f"[{update['day']}]")
    print(f"  Yesterday: {update['yesterday']}")
    print(f"  Today: {update['today']}")
    print(f"  Blockers: {update['blockers']}")
    print(f"  Hours: {update['hours']}h")
    print()

print("[OK] 3 days of standups logged")
print()

# ============================================================================
# STEP 4: Update some tasks to show progress
# ============================================================================
print("=" * 70)
print("STEP 4: Update Task Progress")
print("=" * 70)
print()

with get_session() as session:
    # Mark first task as done
    update_task_status(session, tasks_info[0]["id"], TaskStatus.done)
    update_task_progress(session, tasks_info[0]["id"], 100.0)

    # Mark second task as in_progress
    update_task_status(session, tasks_info[1]["id"], TaskStatus.in_progress)
    update_task_progress(session, tasks_info[1]["id"], 50.0)

    # Mark third task as in_progress
    update_task_status(session, tasks_info[2]["id"], TaskStatus.in_progress)
    update_task_progress(session, tasks_info[2]["id"], 30.0)

print(f"[OK] Task '{tasks_info[0]['name']}' marked as DONE (100%)")
print(f"[OK] Task '{tasks_info[1]['name']}' marked as IN_PROGRESS (50%)")
print(f"[OK] Task '{tasks_info[2]['name']}' marked as IN_PROGRESS (30%)")
print()

# ============================================================================
# STEP 5: L2 Report - Generate sprint report
# ============================================================================
print("=" * 70)
print("STEP 5: L2 Report Crew - Generate Sprint Report")
print("=" * 70)
print()

sprint_report = """# Sprint Progress Report

## Executive Summary
FastAPI CRUD Backend project is in active development. 1 of 7 tasks completed (14%).
Team is making good progress on endpoint implementation.

## Progress Overview
- **Total Tasks**: 7
- **Completed**: 1 (14%)
- **In Progress**: 2 (29%)
- **Todo**: 4 (57%)
- **Blocked**: 0

## Tasks Completed This Sprint
1. **Setup FastAPI Project** (100% complete)
   - Project structure created
   - Dependencies installed
   - Basic configuration done

## Tasks In Progress
1. **Create POST /items Endpoint** (50% complete)
   - Basic endpoint created
   - Input validation in progress

2. **Create DELETE /items/{id} Endpoint** (30% complete)
   - Endpoint structure created
   - Testing pending

## Blockers and Risks
- No blockers currently
- Risk: Team has only 1 backend engineer - capacity constraint

## Overdue Items
- None

## Recommended Next Actions
1. Complete POST and DELETE endpoints
2. Add comprehensive input validation
3. Implement error handling
4. Write unit tests for all endpoints
5. Create API documentation

## Team Performance
- Fawad (Backend Engineer): Good progress, managing workload well
"""

print("L2 Report generated:")
print("-" * 70)
print(sprint_report[:500])
print("... (truncated)")
print("-" * 70)
print()

report_id = save_l2_report(
    project_id=project_id,
    raw_report=sprint_report,
    prompt_tokens=0,
    completion_tokens=0,
    estimated_cost_usd=0.0,
    summary=sprint_report[:200],
)

print(f"[OK] Sprint report saved with ID: {report_id}")
print()

# ============================================================================
# STEP 6: Final database state
# ============================================================================
print("=" * 70)
print("STEP 6: Final Database State")
print("=" * 70)
print()

with get_session() as session:
    final_tasks = get_project_tasks(session, project_id)
    final_logs = get_project_daily_logs(session, project_id)
    final_milestones = get_project_milestones(session, project_id)
    final_reports = get_sprint_reports(session, project_id)

    # Serialize
    final_tasks_plain = [{
        "id": t.id, "name": t.name, "status": t.status.value,
        "progress_pct": t.progress_pct,
    } for t in final_tasks]
    final_logs_plain = [{
        "log_date": l.log_date.date().isoformat(),
        "task_id": l.task_id,
        "yesterday": (l.yesterday_progress or "")[:50],
    } for l in final_logs]
    final_milestones_plain = [{
        "id": ms.id, "name": ms.name, "status": ms.status.value,
    } for ms in final_milestones]
    final_reports_plain = [{
        "id": r.id, "summary": (r.summary or "")[:60],
    } for r in final_reports]

print(f"Project ID: {project_id}")
print(f"Tasks: {len(final_tasks_plain)}")
print(f"Daily Logs: {len(final_logs_plain)}")
print(f"Milestones: {len(final_milestones_plain)}")
print(f"Sprint Reports: {len(final_reports_plain)}")
print()

print("Tasks:")
for t in final_tasks_plain:
    status_icon = {
        "todo": "[ ]", "in_progress": "[>]", "in_review": "[?]",
        "done": "[x]", "blocked": "[!]", "cancelled": "[-]",
    }.get(t["status"], "[?]")
    print(f"  {status_icon} [{t['id']}] {t['name']}")
    print(f"      Status: {t['status']} | Progress: {t['progress_pct']}%")
print()

print("Daily Logs:")
for l in final_logs_plain:
    print(f"  [{l['log_date']}] Task#{l['task_id']}: {l['yesterday']}")
print()

print("Milestones:")
for ms in final_milestones_plain:
    print(f"  [{ms['id']}] {ms['name']} - {ms['status']}")
print()

print("Sprint Reports:")
for r in final_reports_plain:
    print(f"  Report #{r['id']}: {r['summary']}...")
print()

# ============================================================================
# DONE
# ============================================================================
print("=" * 70)
print("  FULL SYSTEM TEST COMPLETE")
print("=" * 70)
print()
print("What just happened:")
print("  1. L1 crew generated a project plan (7 tasks, 3 milestones)")
print("  2. Plan saved to database")
print("  3. You saw the plan details")
print("  4. 3 days of standups logged")
print("  5. Tasks updated to show progress")
print("  6. L2 crew generated a sprint report")
print("  7. Report saved to database")
print("  8. Final database state shown")
print()
print(f"Database file: {PROJECT_ROOT / 'data' / 'app.db'}")
print(f"Project ID: {project_id}")
print()
print("Next steps:")
print("  - Run 'python run_manager_demo.py' to test tools without LLM")
print("  - Run 'python test_full_system.py' to run automated tests")
print("  - Run 'python status_dashboard.py' to see visual dashboard")
print("  - Run 'python run_daily_cycle.py' to run daily PM workflow")
print("  - Run 'python inspect_db.py' to see database contents")

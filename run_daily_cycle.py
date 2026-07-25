#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Daily PM Cycle — runs the manager's daily workflow against the database.

Usage:
    python run_daily_cycle.py [project_id]

If no project_id is given, uses project_id=1.

Steps:
  1. Morning check — read yesterday's logs, check task statuses
  2. Find blockers — surface blocked/overdue tasks
  3. Check team workload — see who's overloaded
  4. Reassign if needed — move tasks from overloaded members
  5. Log today's standup — record what each active task did yesterday
  6. Update milestones — mark milestones based on progress
  7. Daily report — print a summary of the day's decisions
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pmagent.db.session import get_session
from pmagent.db.repository import (
    get_project, get_project_tasks, get_project_daily_logs,
    get_team_members, get_project_milestones,
    update_task_progress, update_task_status, create_daily_log,
    reassign_task,
)
from pmagent.db.models import TaskStatus, MilestoneStatus


def get_project_id() -> int:
    """Get project_id from CLI args or default to 1."""
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            pass
    return 1


def section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def morning_check(project_id: int) -> dict:
    """Step 1: Read yesterday's logs and current task states."""
    section("STEP 1: Morning Check")

    with get_session() as session:
        project = get_project(session, project_id)
        tasks = list(get_project_tasks(session, project_id))
        logs  = list(get_project_daily_logs(session, project_id))
        members = list(get_team_members(session, project_id))

    print(f"Project: {project.name} (ID: {project_id})")
    print(f"Status: {project.status.value}")
    print()

    # Show yesterday's last log
    today = date.today()
    recent = sorted(logs, key=lambda l: l.log_date, reverse=True)[:3]
    print(f"Recent logs ({len(logs)} total):")
    for l in recent:
        print(f"  [{l.log_date.date()}] Task#{l.task_id}: {(l.yesterday_progress or '(no note)')[:60]}")
    print()

    # Show current task states
    done     = sum(1 for t in tasks if t.status == TaskStatus.done)
    progress = sum(1 for t in tasks if t.status == TaskStatus.in_progress)
    blocked  = sum(1 for t in tasks if t.status == TaskStatus.blocked)
    todo     = sum(1 for t in tasks if t.status == TaskStatus.todo)
    print(f"Tasks: {len(tasks)} total")
    print(f"  Done: {done} | In Progress: {progress} | Blocked: {blocked} | Todo: {todo}")
    print()

    return {
        "project": project,
        "tasks": tasks,
        "logs": logs,
        "members": members,
        "done": done,
        "progress": progress,
        "blocked": blocked,
        "todo": todo,
    }


def find_blockers_step(project_id: int) -> list:
    """Step 2: Find blocked or overdue tasks."""
    section("STEP 2: Find Blockers")

    with get_session() as session:
        tasks = list(get_project_tasks(session, project_id))

    today = date.today()
    blocked = [t for t in tasks if t.status == TaskStatus.blocked]
    overdue = [
        t for t in tasks
        if t.due_date and t.due_date.date() < today and t.status != TaskStatus.done
    ]

    issues = []
    if blocked:
        print(f"BLOCKED ({len(blocked)}):")
        for t in blocked:
            print(f"  [{t.id}] {t.name}")
            issues.append({"type": "blocked", "task_id": t.id, "name": t.name})
    else:
        print("No blocked tasks.")

    if overdue:
        print(f"\nOVERDUE ({len(overdue)}):")
        for t in overdue:
            print(f"  [{t.id}] {t.name} — due {t.due_date.date()}")
            issues.append({"type": "overdue", "task_id": t.id, "name": t.name})
    else:
        print("No overdue tasks.")

    if not issues:
        print("\n[OK] No blockers found. Project is healthy.")

    print()
    return issues


def check_workload_step(project_id: int) -> dict:
    """Step 3: Check team member workloads."""
    section("STEP 3: Check Team Workload")

    with get_session() as session:
        members = list(get_team_members(session, project_id))
        tasks   = list(get_project_tasks(session, project_id))

    workload: dict[int, int] = {}
    member_map = {}
    for m in members:
        member_map[m.id] = {"name": m.name, "role": m.role, "count": 0}
    for t in tasks:
        mid = t.assigned_to_id
        if mid and mid in member_map:
            member_map[mid]["count"] += 1

    print("Team workload:")
    overloaded = []
    for mid, info in member_map.items():
        print(f"  {info['name']} ({info['role']}): {info['count']} task(s)")
        if info["count"] > 3:
            overloaded.append(mid)

    if overloaded:
        names = [member_map[m]["name"] for m in overloaded]
        print(f"\n[WARN] Overloaded: {', '.join(names)}")
    else:
        print("\n[OK] No team members overloaded.")

    print()
    return {"members": member_map, "overloaded": overloaded}


def reassign_step(project_id: int, overloaded: list[int], tasks: list) -> None:
    """Step 4: Reassign tasks from overloaded members to those with capacity."""
    section("STEP 4: Reassign Tasks")

    if not overloaded:
        print("[OK] No reassignments needed.")
        print()
        return

    with get_session() as session:
        members = list(get_team_members(session, project_id))
        all_tasks = list(get_project_tasks(session, project_id))

    member_map = {m.id: m for m in members}
    workload = {m.id: 0 for m in members}
    for t in all_tasks:
        if t.assigned_to_id:
            workload[t.assigned_to_id] = workload.get(t.assigned_to_id, 0) + 1

    # Find members with capacity
    underutilized = [m for m in members if workload.get(m.id, 0) < 2]

    if not underutilized:
        print("[WARN] No team members with capacity to take on more work.")
        print()
        return

    reassigned = []
    for overloaded_id in overloaded:
        overloaded_name = member_map[overloaded_id].name
        # Find tasks assigned to this member
        overloaded_tasks = [t for t in all_tasks if t.assigned_to_id == overloaded_id]
        for t in overloaded_tasks:
            if len(reassigned) >= len(overloaded_tasks):
                break
            # Pick first underutilized member
            new_member = underutilized[0]
            with get_session() as session:
                reassign_task(session, t.id, new_member.id)
            print(f"  [{t.id}] {t.name}: {overloaded_name} -> {new_member.name}")
            reassigned.append(t.id)
            workload[overloaded_id] -= 1
            workload[new_member.id] += 1

    if reassigned:
        print(f"\n[OK] Reassigned {len(reassigned)} task(s).")
    else:
        print("[OK] No tasks to reassign.")

    print()


def log_standups_step(project_id: int, tasks: list, members: list) -> None:
    """Step 5: Log today's standup for each active task."""
    section("STEP 5: Log Daily Standups")

    active_tasks = [t for t in tasks if t.status in (TaskStatus.in_progress, TaskStatus.todo)]
    if not active_tasks:
        print("[OK] No active tasks to log standups for.")
        print()
        return

    today_str = date.today().isoformat()
    logged = 0
    for t in active_tasks[:5]:  # limit to 5 tasks per day
        member_id = t.assigned_to_id
        if not member_id:
            continue
        with get_session() as session:
            create_daily_log(
                session=session,
                task_id=t.id,
                team_member_id=member_id,
                yesterday_progress=f"Worked on {t.name}",
                today_plan=f"Continue {t.name}",
                blockers="",
                hours_logged=8.0,
            )
        logged += 1

    print(f"[OK] Logged standups for {logged} task(s) today ({today_str}).")
    print()


def update_milestones_step(project_id: int, tasks: list) -> None:
    """Step 6: Update milestone statuses based on progress."""
    section("STEP 6: Update Milestones")

    with get_session() as session:
        milestones = list(get_project_milestones(session, project_id))

    if not milestones:
        print("[OK] No milestones to update.")
        print()
        return

    total = len(tasks)
    done  = sum(1 for t in tasks if t.status == TaskStatus.done)
    pct   = (done / total * 100) if total else 0

    # Determine milestone status
    if pct >= 50:
        new_status = MilestoneStatus.on_track
    elif pct >= 25:
        new_status = MilestoneStatus.at_risk
    else:
        new_status = MilestoneStatus.pending

    updated = 0
    with get_session() as session:
        for ms in milestones:
            if ms.status != new_status:
                from pmagent.db.repository import update_milestone_status
                update_milestone_status(session, ms.id, new_status)
                print(f"  [{ms.id}] {ms.name}: {ms.status.value} -> {new_status.value}")
                updated += 1

    if updated:
        print(f"\n[OK] Updated {updated} milestone(s) to '{new_status.value}'.")
    else:
        print(f"[OK] All milestones already '{new_status.value}'.")

    print()


def daily_report(project_id: int, state: dict, blockers: list, workload: dict) -> None:
    """Step 7: Print a daily PM report."""
    section("DAILY PM REPORT")

    tasks = state["tasks"]
    done     = state["done"]
    progress = state["progress"]
    blocked  = state["blocked"]
    todo     = state["todo"]
    total    = len(tasks)
    pct      = (done / total * 100) if total else 0

    print(f"Project: {state['project'].name}")
    print(f"Date: {date.today().isoformat()}")
    print()
    print(f"Progress: {done}/{total} tasks done ({pct:.1f}%)")
    print(f"  In Progress: {progress} | Blocked: {blocked} | Todo: {todo}")
    print()

    if blockers:
        print("Blockers:")
        for b in blockers:
            print(f"  - [{b['type'].upper()}] {b['name']}")
    else:
        print("Blockers: None")
    print()

    print("Team Workload:")
    for mid, info in workload.get("members", {}).items():
        print(f"  {info['name']} ({info['role']}): {info['count']} task(s)")
    print()

    print("Decisions Made:")
    if blockers:
        print("  - Blockers identified, needs investigation")
    if workload.get("overloaded"):
        names = [workload["members"][m]["name"] for m in workload["overloaded"]]
        print(f"  - Overloaded: {', '.join(names)}")
    if not blockers and not workload.get("overloaded"):
        print("  - Project on track, no action needed")
    print()

    print("Next Steps:")
    print("  1. Follow up on blockers")
    print("  2. Check team capacity for tomorrow")
    print("  3. Update stakeholders if needed")
    print()


def main():
    project_id = get_project_id()

    # Step 1: Morning check
    state = morning_check(project_id)

    # Step 2: Find blockers
    blockers = find_blockers_step(project_id)

    # Step 3: Check team workload
    workload = check_workload_step(project_id)

    # Step 4: Reassign if needed
    reassign_step(project_id, workload.get("overloaded", []), state["tasks"])

    # Step 5: Log standups
    log_standups_step(project_id, state["tasks"], state["members"])

    # Step 6: Update milestones
    update_milestones_step(project_id, state["tasks"])

    # Step 7: Daily report
    daily_report(project_id, state, blockers, workload)


if __name__ == "__main__":
    main()

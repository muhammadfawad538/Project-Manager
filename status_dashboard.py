#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick status dashboard - see what's happening in your project right now.

Usage:
    python status_dashboard.py [project_id]
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pmagent.db.session import get_session
from pmagent.db.repository import (
    get_project, get_project_tasks, get_project_daily_logs,
    get_team_members, get_project_milestones, get_sprint_reports,
)
from pmagent.db.models import TaskStatus
from datetime import date


def get_project_id() -> int:
    if len(sys.argv) > 1:
        try:
            return int(sys.argv[1])
        except ValueError:
            pass
    return 1


def bar(pct: float, width: int = 20) -> str:
    filled = int(width * pct / 100)
    return "=" * filled + " " * (width - filled)


def main():
    project_id = get_project_id()

    with get_session() as session:
        project = get_project(session, project_id)
        if not project:
            print(f"No project with id={project_id}")
            return

        # Serialize everything while session is open
        p_name = project.name
        p_type = project.project_type
        p_industry = project.industry
        p_status = project.status.value
        p_created = project.created_at.date()

        members = list(get_team_members(session, project_id))
        member_map = {m.id: m.name for m in members}
        members_plain = [{"id": m.id, "name": m.name, "role": m.role} for m in members]

        tasks = list(get_project_tasks(session, project_id))
        tasks_plain = []
        for t in tasks:
            tasks_plain.append({
                "id": t.id,
                "name": t.name,
                "status": t.status.value,
                "progress_pct": t.progress_pct,
                "assigned_to_id": t.assigned_to_id,
            })

        logs = list(get_project_daily_logs(session, project_id))
        logs_plain = []
        for l in logs:
            logs_plain.append({
                "log_date": l.log_date.date().isoformat(),
                "task_id": l.task_id,
                "team_member_id": l.team_member_id,
                "yesterday_progress": l.yesterday_progress or "",
                "today_plan": l.today_plan or "",
                "blockers": l.blockers or "",
            })

        milestones = list(get_project_milestones(session, project_id))
        milestones_plain = []
        for ms in milestones:
            milestones_plain.append({
                "id": ms.id,
                "name": ms.name,
                "status": ms.status.value,
                "due_date": ms.due_date.date().isoformat() if ms.due_date else "TBD",
            })

        reports = list(get_sprint_reports(session, project_id))
        reports_plain = []
        for r in reports:
            reports_plain.append({
                "id": r.id,
                "summary": (r.summary or "")[:70],
            })

    # Now print everything using plain dicts - no ORM access
    print("=" * 70)
    print(f"  PROJECT DASHBOARD: {p_name}")
    print("=" * 70)
    print(f"  ID      : {project_id}")
    print(f"  Type    : {p_type}")
    print(f"  Industry: {p_industry or 'N/A'}")
    print(f"  Status  : {p_status}")
    print(f"  Created : {p_created}")
    print()

    # Tasks summary
    total = len(tasks_plain)
    done = sum(1 for t in tasks_plain if t["status"] == "done")
    in_progress = sum(1 for t in tasks_plain if t["status"] == "in_progress")
    blocked = sum(1 for t in tasks_plain if t["status"] == "blocked")
    todo = sum(1 for t in tasks_plain if t["status"] == "todo")
    pct = (done / total * 100) if total else 0

    print("-" * 70)
    print("  TASKS")
    print("-" * 70)
    print(f"  Total: {total} | Done: {done} | In Progress: {in_progress} | Blocked: {blocked} | Todo: {todo}")
    print(f"  Progress: [{bar(pct)}] {pct:.1f}%")
    print()

    # Task list
    print("  Task List:")
    for t in tasks_plain:
        status_icon = {
            "todo": "[ ]", "in_progress": "[>]", "in_review": "[?]",
            "done": "[x]", "blocked": "[!]", "cancelled": "[-]",
        }.get(t["status"], "[?]")
        assignee = member_map.get(t["assigned_to_id"]) or "Unassigned"
        print(f"    {status_icon} [{t['id']}] {t['name']}")
        print(f"        Status: {t['status']} | Progress: {t['progress_pct']}% | Assigned: {assignee}")
    print()

    # Team
    print("-" * 70)
    print("  TEAM")
    print("-" * 70)
    for m in members_plain:
        task_count = sum(1 for t in tasks_plain if t["assigned_to_id"] == m["id"])
        print(f"  [{m['id']}] {m['name']} - {m['role']} ({task_count} task(s))")
    print()

    # Daily logs
    print("-" * 70)
    print("  DAILY LOGS (last 5)")
    print("-" * 70)
    recent = sorted(logs_plain, key=lambda l: l["log_date"], reverse=True)[:5]
    for l in recent:
        member_name = member_map.get(l["team_member_id"], "Unknown")
        print(f"  [{l['log_date']}] Task#{l['task_id']} by {member_name}")
        print(f"      Yesterday: {(l['yesterday_progress'] or '(none)')[:60]}")
        print(f"      Today    : {(l['today_plan'] or '(none)')[:60]}")
        if l["blockers"]:
            print(f"      Blockers : {l['blockers'][:60]}")
    print()

    # Milestones
    print("-" * 70)
    print("  MILESTONES")
    print("-" * 70)
    if milestones_plain:
        for ms in milestones_plain:
            status_icon = {
                "pending": "[ ]", "on_track": "[>]", "at_risk": "[!]",
                "missed": "[x]", "achieved": "[*]",
            }.get(ms["status"], "[?]")
            print(f"  {status_icon} [{ms['id']}] {ms['name']} - {ms['status']} - due {ms['due_date']}")
    else:
        print("  No milestones.")
    print()

    # Sprint reports
    print("-" * 70)
    print("  SPRINT REPORTS")
    print("-" * 70)
    if reports_plain:
        for r in reports_plain:
            print(f"  [{r['id']}] {r['summary']}...")
    else:
        print("  No reports yet.")
    print()

    # Blockers alert
    today_str = date.today().isoformat()
    blocked_tasks = [t for t in tasks_plain if t["status"] == "blocked"]
    overdue_tasks = [
        t for t in tasks_plain
        if t.get("due_date") and t["due_date"] < today_str and t["status"] != "done"
    ]

    print("-" * 70)
    print("  ALERTS")
    print("-" * 70)
    if blocked_tasks:
        print(f"  [!] {len(blocked_tasks)} blocked task(s)")
    if overdue_tasks:
        print(f"  [!] {len(overdue_tasks)} overdue task(s)")
    if not blocked_tasks and not overdue_tasks:
        print("  [OK] No alerts - project is healthy.")
    print()

    print("=" * 70)


if __name__ == "__main__":
    main()

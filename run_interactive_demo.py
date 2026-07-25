#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interactive full-system demo.

Walkthrough:
  1. You enter project details
  2. L1 crew generates a plan (saved to DB)
  3. You see the plan
  4. You log daily standups
  5. L2 crew generates a sprint report (saved to DB)
  6. You see the final DB state

Needs OPENAI_API_KEY in .env for steps 2 and 5.
Run with: python run_interactive_demo.py
"""

from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# ── Setup ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    from pmagent.db.session import create_db, get_session
    from pmagent.db.models import TaskStatus
    from pmagent.db.repository import (
        get_project_tasks, get_project_daily_logs, get_project_milestones,
        get_sprint_reports, update_task_progress, create_daily_log,
        update_task_status, get_project, get_team_members,
    )

    create_db()

    # ═══════════════════════════════════════════════════════════════════════════
    # UTILS
    # ═══════════════════════════════════════════════════════════════════════════

    def pause(message: str = "Press Enter to continue..."):
        input(f"\n{message}")

    def section(title: str):
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70 + "\n")

    def check_api_key() -> bool:
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        return bool(key) and not key.startswith("your_")


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 1: YOU ENTER PROJECT DETAILS
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 1: Enter Project Details")

    print("Enter your project details below. Press Enter to accept defaults.\n")

    project_type = input("Project type [Residential Construction - 20-Marla Plot]: ").strip()
    if not project_type:
        project_type = "Residential Construction - 20-Marla Plot"

    industry = input("Industry [Construction]: ").strip() or "Construction"

    objectives = input("Project objectives [Complete construction of a 2-story house]: ").strip()
    if not objectives:
        objectives = "Complete construction of a 2-story house"

    deadline = input("Project deadline [e.g. 2025-08-30]: ").strip()

    print("\nEnter requirements (one per line, empty line to finish):")
    requirements_lines = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        requirements_lines.append(line)
    if not requirements_lines:
        requirements_lines = [
            "Excavation and foundation work",
            "Column and beam reinforcement",
            "Brick masonry and wall construction",
            "Roof slab casting",
            "Electrical wiring",
            "Plumbing pipework",
            "Window and door frame installation",
            "Interior and exterior plastering",
            "Flooring (marble/tiles)",
            "Paint and finishing",
        ]

    print("\nEnter team members (format: Name (Role), one per line, empty line to finish):")
    team_lines = []
    while True:
        line = input("  > ").strip()
        if not line:
            break
        team_lines.append(line)
    if not team_lines:
        team_lines = [
            "Ali (Site Engineer)",
            "Ahmed (Carpenter / Steel Worker)",
            "Usman (Electrician)",
            "Hassan (Plumber)",
            "Bilal (General Laborer)",
        ]

    requirements = "\n".join(requirements_lines)
    team_members_str = "\n".join(f"- {line}" for line in team_lines)

    inputs = {
        "project_type": project_type,
        "project_objectives": objectives,
        "industry": industry,
        "team_members": team_members_str,
        "project_requirements": requirements,
    }
    if deadline:
        inputs["deadline"] = deadline

    print("\n[OK] Project details captured.")
    print(f"  Type    : {project_type}")
    print(f"  Industry: {industry}")
    print(f"  Deadline: {deadline or 'not specified'}")
    print(f"  Team    : {len(team_lines)} members")
    print(f"  Requirements: {len(requirements_lines)} items")


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 2: L1 CREW - GENERATE PLAN
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 2: L1 Planning Crew - Generating Project Plan")

    if check_api_key():
        print("[INFO] API key found - running real L1 crew...\n")
        try:
            from pmagent.main import kickoff
            result = kickoff(persist=True, inputs=inputs)
            project_id = result.get("project_id") or 1
            print(f"\n[OK] L1 crew finished. Project saved with ID: {project_id}")
        except Exception as exc:
            print(f"[ERROR] L1 crew failed: {exc}")
            print("[FALLBACK] Using mock plan instead...\n")
            project_id = _save_mock_l1_plan(inputs)
    else:
        print("[WARN] No API key - using mock L1 plan instead.\n")
        project_id = _save_mock_l1_plan(inputs)

    pause()


    def _save_mock_l1_plan(inputs: dict) -> int:
        """Save a mock L1 plan to the DB."""
        from pmagent.persistence import save_l1_plan

        plan_data = {
            "tasks": [
                {"task_name": "Site Survey & Excavation", "estimated_time_hours": 40.0},
                {"task_name": "Foundation Concrete Pouring", "estimated_time_hours": 60.0},
                {"task_name": "Column & Beam Reinforcement", "estimated_time_hours": 80.0},
                {"task_name": "Brick Masonry Walls", "estimated_time_hours": 120.0},
                {"task_name": "Roof Slab Casting", "estimated_time_hours": 100.0},
                {"task_name": "Electrical Rough-in", "estimated_time_hours": 50.0},
                {"task_name": "Plumbing Rough-in", "estimated_time_hours": 45.0},
                {"task_name": "Window & Door Installation", "estimated_time_hours": 35.0},
                {"task_name": "Interior Plastering", "estimated_time_hours": 70.0},
                {"task_name": "Flooring Installation", "estimated_time_hours": 55.0},
                {"task_name": "Painting & Finishing", "estimated_time_hours": 65.0},
            ],
            "milestones": [
                {"milestone_name": "Foundation Complete"},
                {"milestone_name": "Structure Complete"},
                {"milestone_name": "MEP Complete"},
                {"milestone_name": "Finishing Complete"},
                {"milestone_name": "Project Handover"},
            ],
        }
        pid = save_l1_plan(inputs=inputs, plan_data=plan_data)
        print(f"[OK] Mock L1 plan saved. Project ID: {pid}")
        return pid


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 3: YOU SEE THE PLAN
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 3: Your Project Plan")

    with get_session() as session:
        project = get_project(session, project_id)
        members = get_team_members(session, project_id)
        tasks = get_project_tasks(session, project_id)
        milestones = get_project_milestones(session, project_id)

        # Capture as plain data while session is open
        p_name = project.name
        p_type = project.project_type
        p_industry = project.industry
        p_status = project.status.value
        members_info = [
            {"id": m.id, "name": m.name, "role": m.role}
            for m in members
        ]
        tasks_info = [
            {
                "id": t.id,
                "name": t.name,
                "estimated_hours": t.estimated_hours,
                "status": t.status.value,
                "progress_pct": t.progress_pct,
                "assignee": t.assigned_to.name if t.assigned_to else "Unassigned",
            }
            for t in tasks
        ]
        milestones_info = [
            {"id": ms.id, "name": ms.name, "status": ms.status.value}
            for ms in milestones
        ]

    print(f"Project: {p_name}")
    print(f"  ID      : {project_id}")
    print(f"  Type    : {p_type}")
    print(f"  Industry: {p_industry}")
    print(f"  Status  : {p_status}")
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

    total_hours = sum(t["estimated_hours"] for t in tasks_info if t["estimated_hours"])
    print(f"\nTotal estimated hours: {total_hours}h")
    print(f"Estimated duration: ~{int(total_hours / 8)} working days")

    pause()


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 4: LOG DAILY STANDUPS
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 4: Log Daily Standups")

    print("You will now log standups for the first task.")
    print("This simulates the Manager Agent logging daily work.\n")

    with get_session() as session:
        first_task = get_project_tasks(session, project_id)[0]
        first_member = get_team_members(session, project_id)[0]
        task_id = first_task.id
        member_id = first_member.id
        task_name = first_task.name
        member_name = first_member.name
        member_role = first_member.role

    print(f"Task: {task_name}")
    print(f"Team Member: {member_name} ({member_role})")
    print()

    num_days = 3
    for day in range(1, num_days + 1):
        print(f"--- Day {day} ---")
        yesterday = input("Yesterday's progress: ").strip()
        today = input("Today's plan: ").strip()
        blockers = input("Blockers: ").strip()
        hours_str = input("Hours worked: ").strip()

        try:
            hours = float(hours_str) if hours_str else 8.0
        except ValueError:
            hours = 8.0

        with get_session() as session:
            create_daily_log(
                session=session,
                task_id=task_id,
                team_member_id=member_id,
                yesterday_progress=yesterday,
                today_plan=today,
                blockers=blockers,
                hours_logged=hours,
            )
            new_progress = min(100.0, (day / num_days) * 100.0)
            update_task_progress(session, task_id, new_progress)

        print(f"[OK] Day {day} standup logged - {hours}h worked\n")

    print(f"[OK] {num_days} days of standups logged.")


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 5: L2 CREW - GENERATE SPRINT REPORT
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 5: L2 Report Crew - Generating Sprint Report")

    if check_api_key():
        print("[INFO] API key found - running real L2 crew...\n")
        try:
            sys.path.insert(0, str(PROJECT_ROOT))
            from main_l2 import kickoff as l2_kickoff
            result = l2_kickoff(project_id=project_id)
            print(f"\n[OK] L2 report generated and saved.")
        except Exception as exc:
            print(f"[ERROR] L2 crew failed: {exc}")
            print("[FALLBACK] Using mock report instead.\n")
            _save_mock_l2_report(project_id)
    else:
        print("[WARN] No API key - using mock L2 report.\n")
        _save_mock_l2_report(project_id)


    def _save_mock_l2_report(project_id: int):
        """Save a mock sprint report."""
        from pmagent.persistence import save_l2_report

        report = """# Sprint Progress Report

## Executive Summary
Project is in early stages. Foundation work is in progress with no blockers.
Team is making steady progress.

## Progress Overview
- **Total Tasks**: 11
- **Completed**: 0 (0%)
- **In Progress**: 1 (9%)
- **Todo**: 10 (91%)
- **Blocked**: 0

## Tasks In Progress
1. **Site Survey & Excavation** - 100% complete (Day 3)
   - Assigned to: Ali (Site Engineer)
   - 3 days of work logged
   - Status: On track

## Blockers and Risks
- No blockers
- Risk: Rain delays possible (experienced on Day 3)

## Recommended Next Actions
1. Start Foundation Concrete Pouring
2. Assign Ahmed to prepare reinforcement
3. Schedule concrete delivery

## Team Performance
- Ali: 22+ hours logged, good progress
- Others: Awaiting task assignments
"""

        rid = save_l2_report(
            project_id=project_id,
            raw_report=report,
            prompt_tokens=0,
            completion_tokens=0,
            estimated_cost_usd=0.0,
            summary=report[:200],
        )
        print(f"[OK] Mock L2 report saved. Report ID: {rid}")


    pause()


    # ═══════════════════════════════════════════════════════════════════════════
    # STEP 6: FINAL DATABASE STATE
    # ═══════════════════════════════════════════════════════════════════════════

    section("STEP 6: Final Database State")

    with get_session() as session:
        final_tasks = get_project_tasks(session, project_id)
        final_logs = get_project_daily_logs(session, project_id)
        final_milestones = get_project_milestones(session, project_id)
        final_reports = get_sprint_reports(session, project_id)

    print(f"Project ID       : {project_id}")
    print(f"Tasks            : {len(final_tasks)}")
    print(f"Daily Logs       : {len(final_logs)}")
    print(f"Milestones       : {len(final_milestones)}")
    print(f"Sprint Reports   : {len(final_reports)}")
    print()

    print("Tasks:")
    for t in final_tasks:
        status_icon = {
            "todo": "[ ]", "in_progress": "[>]", "in_review": "[?]",
            "done": "[x]", "blocked": "[!]", "cancelled": "[-]",
        }.get(t.status.value, "[?]")
        print(f"  {status_icon} [{t.id}] {t.name}")
        print(f"      Status: {t.status.value} | Progress: {t.progress_pct}%")
    print()

    print("Daily Logs:")
    for log in final_logs:
        print(f"  [{log.log_date.date()}] Task#{log.task_id}: {log.yesterday_progress[:60]}")
    print()

    print("Milestones:")
    for ms in final_milestones:
        print(f"  [{ms.id}] {ms.name} - {ms.status.value}")
    print()

    print("Sprint Reports:")
    for r in final_reports:
        print(f"  Report #{r.id}: {r.summary[:80]}...")
    print()

    print("=" * 70)
    print("  FULL SYSTEM TEST COMPLETE")
    print("=" * 70)
    print()
    print("What just happened:")
    print("  1. You entered project details")
    print("  2. L1 crew generated a plan (mocked if no API key)")
    print("  3. Plan saved to database")
    print("  4. You logged 3 days of standups")
    print("  5. L2 crew generated a sprint report (mocked if no API key)")
    print("  6. Report saved to database")
    print()
    print(f"Database file: {PROJECT_ROOT / 'data' / 'app.db'}")
    print(f"Project ID   : {project_id}")
    print()
    print("Next steps:")
    print("  - Run 'python run_manager_demo.py' to test tools without LLM")
    print("  - Run 'python test_full_system.py' to run automated tests")
    print("  - Set OPENAI_API_KEY in .env to test with real AI crews")


    print()
    print("Next steps:")
    print("  - Run 'python run_manager_demo.py' to test tools without LLM")
    print("  - Run 'python test_full_system.py' to run automated tests")
    print("  - Run 'python status_dashboard.py' to see project status")
    print("  - Run 'python run_daily_cycle.py' to run the daily PM workflow")
    print("  - Set OPENAI_API_KEY in .env to test with real AI crews")


if __name__ == "__main__":
    main()

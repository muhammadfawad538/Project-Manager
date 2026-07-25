#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run the full pmagent system test suite."""
import sys
sys.path.insert(0, "src")

from pmagent.db.session import create_db, get_session, list_tables
from pmagent.db import (
    create_project, get_project, add_team_member, get_team_members,
    create_task, get_project_tasks, update_task_status, update_task_progress,
    reassign_task, set_task_actual_hours,
    create_daily_log, get_project_daily_logs,
    create_milestone, get_project_milestones,
    save_sprint_report, get_sprint_reports,
    ProjectStatus, TaskStatus, add_dependency, get_task_dependencies, get_task,
)
from pmagent.persistence import save_l1_plan, save_l2_report
import os
os.environ["OPENAI_API_KEY"] = "sk-test"
from pmagent.orchestrator import build_manager_agent
import json


def main() -> None:
    # Fresh DB
    import os as _os
    try:
        _os.remove("data/app.db")
    except FileNotFoundError:
        pass
    create_db()

    # TEST 1: DB tables
    tables = sorted(list_tables())
    assert tables == ["daily_logs", "milestones", "projects", "sprint_reports",
                      "task_dependencies", "tasks", "team_members"], tables
    print(f"[OK] 7 tables: {tables}")

    # TEST 2: CRUD round-trip
    with get_session() as s:
        p = create_project(session=s, name="TestCo Tower", project_type="Construction", industry="Building")
        pid = p.id
        m1 = add_team_member(session=s, project_id=pid, name="Ali", role="Site Engineer")
        m2 = add_team_member(session=s, project_id=pid, name="Sara", role="Electrician")
        t1 = create_task(session=s, project_id=pid, name="Foundation", estimated_hours=40.0, assigned_to_id=m1.id)
        t2 = create_task(session=s, project_id=pid, name="Wiring", estimated_hours=25.0, assigned_to_id=m2.id)
        update_task_progress(s, t1.id, 75.0)
        reassign_task(s, t2.id, m1.id)
        set_task_actual_hours(s, t1.id, 30.0)
        create_daily_log(session=s, task_id=t1.id, team_member_id=m1.id,
                         yesterday_progress="Half done", today_plan="Finish pour",
                         blockers="Cement late", hours_logged=8.0)
        create_milestone(session=s, project_id=pid, name="Foundation Complete")
        s.flush()
    print("[OK] CRUD: 1 project, 2 members, 2 tasks, 1 log, 1 milestone saved")

    # TEST 3: Fresh-session reads
    with get_session() as s:
        px = get_project(s, pid)
        assert px.name == "TestCo Tower"
        members = get_team_members(s, pid)
        assert len(members) == 2
        tasks = get_project_tasks(s, pid)
        assert len(tasks) == 2
        assert tasks[0].status == TaskStatus.in_progress
        assert tasks[0].actual_hours == 30.0
        logs = get_project_daily_logs(s, pid)
        assert len(logs) == 1
        milestones = get_project_milestones(s, pid)
        assert len(milestones) == 1
        rpt = save_sprint_report(session=s, project_id=pid, raw_report="OK",
                                 summary="OK", prompt_tokens=100, completion_tokens=50)
        rpt_id = rpt.id  # capture before session closes
        s.flush()
    print(f"[OK] Fresh reads: team=2 tasks=2 logs={len(logs)} milestones={len(milestones)} report={rpt_id}")

    # TEST 4: Task lifecycle
    with get_session() as s:
        t = create_task(session=s, project_id=pid, name="Review")
        tid = t.id
        update_task_status(s, tid, TaskStatus.in_progress)
        update_task_status(s, tid, TaskStatus.in_review)
        update_task_status(s, tid, TaskStatus.done)
        tx = get_task(s, tid)
        assert tx.status == TaskStatus.done
        assert tx.progress_pct == 100.0
        assert tx.completion_date is not None
    print("[OK] Task lifecycle: todo -> in_progress -> in_review -> done")

    # TEST 5: Dependencies
    with get_session() as s:
        ta = create_task(session=s, project_id=pid, name="Task A")
        tb = create_task(session=s, project_id=pid, name="Task B")
        ta_id = ta.id
        tb_id = tb.id
        dep = add_dependency(session=s, project_id=pid, task_id=tb_id, depends_on_task_id=ta_id)
        deps = get_task_dependencies(s, tb_id)
        assert len(deps) == 1
        assert deps[0].depends_on_task_id == ta_id
    print(f"[OK] Dependency: Task#{tb_id} blocked by Task#{ta_id}")

    # TEST 6: L1 persistence
    plan_data = {
        "tasks": [{"task_name": "Excavation", "estimated_time_hours": 20.0}],
        "milestones": [{"milestone_name": "Phase 1"}],
    }
    new_pid = save_l1_plan(
        inputs={"project_type": "T", "project_objectives": "B", "industry": "X",
                "team_members": "- Ali (E)"},
        plan_data=plan_data,
    )
    assert new_pid and new_pid > 0
    print(f"[OK] L1 persistence: project_id={new_pid}")

    # TEST 7: L2 persistence
    new_rid = save_l2_report(
        project_id=new_pid, raw_report="# Sprint", prompt_tokens=200,
        completion_tokens=100, estimated_cost_usd=0.05,
    )
    assert new_rid and new_rid > 0
    print(f"[OK] L2 persistence: report_id={new_rid}")

    # TEST 8: Sprint reports readable
    with get_session() as s:
        reports = get_sprint_reports(s, new_pid)
        assert len(reports) >= 1
    print(f"[OK] Sprint reports for project {new_pid}: {len(reports)}")

    # TEST 9: Manager agent tools
    agent = build_manager_agent()
    tool_names = [t.name for t in agent.tools]
    expected = ["list_projects", "get_project", "create_project", "run_l1_plan",
                "run_l2_report", "log_daily_standup", "update_task_status", "find_blockers"]
    assert tool_names == expected, f"Tool mismatch: {tool_names}"
    print(f"[OK] Manager agent: {len(tool_names)} tools wired")

    # TEST 10: L2 DB fetcher
    sys.path.insert(0, ".")
    from main_l2 import DbProjectFetcherTool
    fetcher = DbProjectFetcherTool()
    raw = fetcher._run(project_id=new_pid)
    data = json.loads(raw)
    assert "tasks" in data and "milestones" in data
    assert data["total_tasks"] >= 1
    print(f"[OK] L2 DB fetcher: {data['total_tasks']} tasks, {len(data['milestones'])} milestones")

    print()
    print("=" * 60)
    print("ALL 10 TESTS PASSED — system is ready for local testing")
    print("=" * 60)
    print(f"  DB file  : data/app.db")
    print(f"  Projects : {len(list(new_pid for _ in [0]))} created in tests")
    print(f"  Tables   : {tables}")
    print(f"  Manager tools : {expected}")


if __name__ == "__main__":
    main()

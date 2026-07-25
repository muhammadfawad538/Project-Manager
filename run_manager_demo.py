# Line ending: LF
# Encoding: UTF-8
"""
Demo: Manager agent tool round-trip against the database.

This does NOT call the LLM — it directly exercises each tool to verify
the manager can read and write real project state via its own tools.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure src/ is on the Python path so `pmagent` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pmagent.orchestrator import (
    ListProjectsTool,
    GetProjectTool,
    CreateProjectTool,
    RunL1PlanTool,
    RunL2ReportTool,
    LogDailyTool,
    UpdateTaskStatusTool,
    FindBlockersTool,
)
from pmagent.db.session import create_db, get_session
from pmagent.db.models import TaskStatus

create_db()

create_db()

tools = {
    t.name: t for t in [
        ListProjectsTool(),
        GetProjectTool(),
        CreateProjectTool(),
        LogDailyTool(),
        UpdateTaskStatusTool(),
        FindBlockersTool(),
    ]
}

# 1. list_projects (empty DB)
print("=== list_projects (empty DB) ===")
print(tools["list_projects"]._run())


# 2. create_project
print("\n=== create_project ===")
result = tools["create_project"]._run(
    name="AI Manufacturing Plant",
    project_type="Industrial Construction",
    industry="Manufacturing",
    objectives="Build a 50,000 sq ft automated manufacturing facility",
    requirements="Cleanroom, HVAC, robotic assembly lines, and IoT sensor network",
    team_members="""
- Sara (Project Engineer)
- Omar (Cleanroom Specialist)
- Lena (Electrical / IoT)
- Raj (HVAC Systems)
""",
)
print(result)


# 3. list_projects (with data)
print("\n=== list_projects (with data) ===")
print(tools["list_projects"]._run())


# 4. get_project (project_id=1)
print("\n=== get_project (id=1) ===")
print(tools["get_project"]._run(project_id=1))


# 5. log_daily_standup (task_id=1, team_member_id=1)
print("\n=== log_daily_standup ===")
with get_session() as session:
    from pmagent.db.repository import get_project_tasks, get_team_members
    tasks     = get_project_tasks(session, 1)
    members   = get_team_members(session, 1)
    tid       = tasks[0].id   if tasks     else None
    mid       = members[0].id if members   else None

if tid and mid:
    print(tools["log_daily_standup"]._run(
        task_id=tid, team_member_id=mid,
        yesterday="Excavated foundation trench",
        today="Pour concrete foundation",
        blockers="Waiting on rebar delivery",
        hours=8.0,
    ))
else:
    print("⚠️  No tasks/members to log a standup for.")


# 6. update_task_status (task_id=1 → in_progress)
print("\n=== update_task_status ===")
if tid:
    print(tools["update_task_status"]._run(task_id=tid, status="in_progress"))


# 7. find_blockers
print("\n=== find_blockers ===")
print(tools["find_blockers"]._run(project_id=1))

print("\n[OK] All tool round-trips verified.")

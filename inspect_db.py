import sys
sys.path.insert(0, "src")

from pmagent.db.session import get_session
from pmagent.db.repository import (
    get_project_tasks, get_project_daily_logs,
    get_project_milestones, get_sprint_reports,
)

with get_session() as s:
    tasks = list(get_project_tasks(s, 1))
    logs = list(get_project_daily_logs(s, 1))
    milestones = list(get_project_milestones(s, 1))
    reports = list(get_sprint_reports(s, 1))

    # Serialize while session is open to avoid DetachedInstanceError
    task_rows = [
        {
            "id": t.id,
            "name": t.name,
            "status": t.status.value if t.status else "unknown",
            "progress": t.progress_pct,
        }
        for t in tasks
    ]
    log_rows = [
        {
            "id": l.id,
            "date": l.log_date.date().isoformat(),
            "task_id": l.task_id,
            "note": (l.yesterday_progress or "")[:60],
        }
        for l in logs
    ]
    milestone_rows = [
        {
            "id": m.id,
            "name": m.name,
            "status": m.status.value if m.status else "unknown",
        }
        for m in milestones
    ]
    report_rows = [
        {
            "id": r.id,
            "summary": (r.summary or "")[:80],
        }
        for r in reports
    ]

print(f"Tasks: {len(task_rows)}")
for t in task_rows:
    print(f"  [{t['id']}] {t['name']} - {t['status']} - {t['progress']}%")

print(f"\nDaily Logs: {len(log_rows)}")
for l in log_rows:
    print(f"  [{l['id']}] {l['date']} Task#{l['task_id']}: {l['note']}")

print(f"\nMilestones: {len(milestone_rows)}")
for m in milestone_rows:
    print(f"  [{m['id']}] {m['name']} - {m['status']}")

print(f"\nSprint Reports: {len(report_rows)}")
for r in report_rows:
    print(f"  [{r['id']}] {r['summary']}")

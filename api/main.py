# Line ending: LF
# Encoding: UTF-8

"""
pmagent API — FastAPI server for the AI project management crew.

Endpoints:
    POST /plan       Run the planning crew, return structured PM package
    GET  /health     Health check

Environment:
    OPENAI_API_KEY   Required. Set in .env or environment.
"""

from __future__ import annotations

import sys
import warnings

warnings.filterwarnings("ignore")

# Ensure UTF-8 stdout for Arabic output
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from api/)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

from pmagent.db.session import get_session

# ── 0. Env check ──────────────────────────────────────────────────────────────

api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key or api_key == "your_openai_key_here":
    # We don't hard-fail here so the server can start and return 500 on /plan
    pass

os.environ.setdefault("OPENAI_MODEL_NAME", os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-mini"))

# ── 1. App setup ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="pmagent API",
    description="AI-powered project planning, risk analysis, and resource allocation via CrewAI.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 2. Request / Response models ──────────────────────────────────────────────

class ProjectRequest(BaseModel):
    """Incoming project description from the client."""

    project_type: str = Field(..., description="Type of project (e.g. 'CRM Implementation')")
    project_objectives: str = Field(..., description="Primary goal and success criteria")
    industry: str = Field(..., description="Industry vertical")
    deadline: str = Field(..., description="Project deadline (e.g. '6 months')")
    country: str = Field(default="Saudi Arabia", description="GCC country for localization")
    currency: str = Field(default="SAR", description="Currency code: SAR, AED, QAR, KWD, BHD, OMR, USD")
    output_language: str = Field(default="English", description="Output language: 'English' or 'Arabic'")
    team_members: str = Field(
        default="",
        description="Newline-separated list: '- Name (Role)'",
    )
    project_requirements: str = Field(
        default="",
        description="Bullet list of deliverables and requirements",
    )


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ── 3. Lazy crew initialization ───────────────────────────────────────────────

# Import inside the endpoint so the server can start quickly;
# the crew is built on first request and cached thereafter.
_crew = None


def _get_crew():
    global _crew
    if _crew is None:
        from pmagent.main import crew
        _crew = crew
    return _crew


# ── 4. Routes ─────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "pmagent"}


@app.post(
    "/plan",
    responses={
        200: {"description": "Project plan generated successfully"},
        400: {"model": ErrorResponse, "description": "Missing required fields"},
        500: {"model": ErrorResponse, "description": "Server error during crew execution"},
    },
)
async def generate_plan(request: ProjectRequest) -> dict:
    """Run the CrewAI planning crew and return a structured PM package.

    Returns:
        JSON with keys:
            raw_output (str): Full markdown report from the manager agent
            wbs (dict): Structured WBS with tasks, milestones, critical path
            risks (dict): Structured risk register
            resources (dict): Structured resource allocation
            critical_path (dict): Algorithmic critical path (tasks, floats, duration)
            usage (dict): LLM token usage
            cost_usd (float): Estimated API cost
    """
    if not api_key or api_key == "your_openai_key_here":
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is not configured. Set it in .env or environment variables.",
        )

    crew = _get_crew()

    inputs = {
        "project_type": request.project_type,
        "project_objectives": request.project_objectives,
        "industry": request.industry,
        "deadline": request.deadline,
        "country": request.country,
        "currency": request.currency,
        "output_language": request.output_language,
        "team_members": request.team_members,
        "project_requirements": request.project_requirements,
    }

    try:
        from pmagent.main import kickoff

        result = kickoff(inputs=inputs)
        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Crew execution failed: {exc}",
        ) from exc


# ── 5. Export endpoints ────────────────────────────────────────────────────────


class ExportRequest(BaseModel):
    """Request body for export endpoints."""

    project_name: str = Field(default="Project", description="Name for the exported file")
    format: str = Field(default="xml", description="Export format: 'xml' (MS Project), 'csv', 'html' (Arabic PDF)")


@app.post("/plan/{project_id}/export")
async def export_plan(project_id: int, request: ExportRequest) -> dict:
    """Export a saved project plan in MS Project XML, CSV, or Arabic PDF.

    Args:
        project_id: ID of the saved project
        request: Export format and project name

    Returns:
        JSON with download_url, format, and file metadata
    """
    from pmagent.db.session import get_session
    from pmagent.db.repository import get_project_tasks
    from pmagent.exports import export_msproject_xml, export_wbs_csv, export_arabic_pdf
    from pathlib import Path

    fmt = request.format.lower()
    project_name = request.project_name or f"project_{project_id}"

    # Load tasks from DB
    with get_session() as s:
        tasks = get_project_tasks(s, project_id)
        if not tasks:
            raise HTTPException(status_code=404, detail=f"No tasks found for project {project_id}")

    # Convert ORM tasks to dicts
    task_dicts = []
    for t in tasks:
        deps = []
        if t.dependencies:
            deps = [d.strip() for d in t.dependencies.split(",") if d.strip()]
        task_dicts.append({
            "id": str(t.id),
            "name": t.name,
            "description": t.description or "",
            "owner": t.assigned_to.name if t.assigned_to else "",
            "estimated_hours": t.estimated_hours,
            "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
            "dependencies": deps,
            "priority": t.priority.value,
        })

    # Export directory
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "xml":
            content = export_msproject_xml(task_dicts, project_name)
            filename = f"{project_name.replace(' ', '_')}.xml"
            filepath = export_dir / filename
            filepath.write_text(content, encoding="utf-8")
            return {
                "format": "xml",
                "filename": filename,
                "download_url": f"/exports/{filename}",
                "task_count": len(task_dicts),
                "message": "MS Project XML exported successfully. Open in MS Project.",
            }

        elif fmt == "csv":
            content = export_wbs_csv(task_dicts)
            filename = f"{project_name.replace(' ', '_')}.csv"
            filepath = export_dir / filename
            filepath.write_text(content, encoding="utf-8")
            return {
                "format": "csv",
                "filename": filename,
                "download_url": f"/exports/{filename}",
                "task_count": len(task_dicts),
                "message": "CSV exported successfully. Open in Excel.",
            }

        elif fmt == "html":
            # Generate Arabic HTML from the latest plan
            from pmagent.db.repository import get_project
            with get_session() as s:
                project = get_project(s, project_id)

            if not project:
                raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

            # Build a simple Arabic HTML summary
            from pmagent.exports.arabic_pdf import markdown_to_html_rtl
            arabic_md = f"# {project_name}\n\n## ملخص المشروع\n\n{project.objectives or ''}\n\n## المهام\n\n"
            for t in task_dicts:
                arabic_md += f"- **{t['name']}** ({t['owner']}) - {t['estimated_hours']}h\n"

            filename = f"{project_name.replace(' ', '_')}_arabic.html"
            filepath = export_dir / filename
            html_content = markdown_to_html_rtl(arabic_md, project_name)
            filepath.write_text(html_content, encoding="utf-8")
            return {
                "format": "html",
                "filename": filename,
                "download_url": f"/exports/{filename}",
                "task_count": len(task_dicts),
                "message": "Arabic HTML generated. Open in browser or convert to PDF.",
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported format: {fmt}. Use 'xml', 'csv', or 'html'.",
            )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {exc}",
        ) from exc


# ── 6. Issue Log endpoints ─────────────────────────────────────────────────────


class IssueCreateRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    task_id: Optional[int] = None
    reported_by_id: Optional[int] = None


class IssueUpdateStatusRequest(BaseModel):
    status: str
    resolution_notes: str = ""


class IssueAssignRequest(BaseModel):
    member_id: int


@app.get("/projects/{project_id}/issues")
async def list_issues(project_id: int, status: Optional[str] = None) -> dict:
    """List all issues for a project."""
    from pmagent.db.repository import get_project_issues
    from pmagent.db.models import IssueStatus

    st = None
    if status:
        try:
            st = IssueStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")

    with get_session() as s:
        issues = get_project_issues(s, project_id, status=st)
        issues_data = [
            {
                "id": i.id,
                "title": i.title,
                "description": i.description,
                "priority": i.priority.value,
                "status": i.status.value,
                "task_id": i.task_id,
                "reported_by": i.reported_by.name if i.reported_by else None,
                "assigned_to": i.assigned_to.name if i.assigned_to else None,
                "resolution_notes": i.resolution_notes,
                "created_at": i.created_at.isoformat(),
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
            }
            for i in issues
        ]

    return {
        "project_id": project_id,
        "count": len(issues_data),
        "issues": issues_data,
    }


@app.post("/projects/{project_id}/issues")
async def create_issue(project_id: int, request: IssueCreateRequest) -> dict:
    """Create a new issue."""
    from pmagent.db.repository import create_issue

    with get_session() as s:
        issue = create_issue(
            s,
            project_id=project_id,
            title=request.title,
            description=request.description,
            priority=request.priority,
            task_id=request.task_id,
            reported_by_id=request.reported_by_id,
        )
        issue_id = issue.id
        status_val = issue.status.value
        priority_val = issue.priority.value
    return {
        "id": issue_id,
        "project_id": project_id,
        "title": request.title,
        "priority": priority_val,
        "status": status_val,
        "message": f"Issue #{issue_id} logged.",
    }


@app.put("/issues/{issue_id}/status")
async def update_issue_status(issue_id: int, request: IssueUpdateStatusRequest) -> dict:
    """Update an issue's status."""
    from pmagent.db.repository import update_issue_status
    from pmagent.db.models import IssueStatus

    try:
        st = IssueStatus(request.status.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status '{request.status}'")

    with get_session() as s:
        issue = update_issue_status(s, issue_id, st, resolution_notes=request.resolution_notes)
        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue #{issue_id} not found")
        status_val = issue.status.value

    return {"id": issue_id, "status": status_val, "message": f"Issue #{issue_id} updated."}


@app.put("/issues/{issue_id}/assign")
async def assign_issue(issue_id: int, request: IssueAssignRequest) -> dict:
    """Assign an issue to a team member."""
    from pmagent.db.repository import assign_issue

    with get_session() as s:
        issue = assign_issue(s, issue_id, request.member_id)
        if not issue:
            raise HTTPException(status_code=404, detail=f"Issue #{issue_id} not found")
        assigned_to_id = issue.assigned_to_id

    return {"id": issue_id, "assigned_to_id": assigned_to_id, "message": f"Issue #{issue_id} assigned."}


# ── 7. Change Request endpoints ───────────────────────────────────────────────


class ChangeRequestCreateRequest(BaseModel):
    title: str
    description: str = ""
    justification: str = ""
    impact_scope: str = ""
    submitted_by_id: Optional[int] = None


class ChangeRequestUpdateStatusRequest(BaseModel):
    status: str
    approved_by_id: Optional[int] = None


@app.get("/projects/{project_id}/change-requests")
async def list_change_requests(project_id: int, status: Optional[str] = None) -> dict:
    """List all change requests for a project."""
    from pmagent.db.repository import get_project_change_requests
    from pmagent.db.models import ChangeRequestStatus

    st = None
    if status:
        try:
            st = ChangeRequestStatus(status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")

    with get_session() as s:
        crs = get_project_change_requests(s, project_id, status=st)
        change_requests = [
            {
                "id": cr.id,
                "title": cr.title,
                "description": cr.description,
                "justification": cr.justification,
                "impact_scope": cr.impact_scope,
                "status": cr.status.value,
                "submitted_by": cr.submitted_by.name if cr.submitted_by else None,
                "approved_by": cr.approved_by.name if cr.approved_by else None,
                "created_at": cr.created_at.isoformat(),
                "decision_date": cr.decision_date.isoformat() if cr.decision_date else None,
                "implemented_at": cr.implemented_at.isoformat() if cr.implemented_at else None,
            }
            for cr in crs
        ]

    return {
        "project_id": project_id,
        "count": len(change_requests),
        "change_requests": change_requests,
    }


@app.post("/projects/{project_id}/change-requests")
async def create_change_request(project_id: int, request: ChangeRequestCreateRequest) -> dict:
    """Create a new change request."""
    from pmagent.db.repository import create_change_request

    with get_session() as s:
        cr = create_change_request(
            s,
            project_id=project_id,
            title=request.title,
            description=request.description,
            justification=request.justification,
            impact_scope=request.impact_scope,
            submitted_by_id=request.submitted_by_id,
        )
        cr_id = cr.id
        cr_status = cr.status.value

    return {
        "id": cr_id,
        "project_id": project_id,
        "title": request.title,
        "status": cr_status,
        "impact_scope": request.impact_scope,
        "message": f"Change Request #{cr_id} submitted.",
    }


@app.put("/change-requests/{cr_id}/status")
async def update_change_request_status(cr_id: int, request: ChangeRequestUpdateStatusRequest) -> dict:
    """Update a change request status (approve/reject/etc)."""
    from pmagent.db.repository import update_change_request_status
    from pmagent.db.models import ChangeRequestStatus

    try:
        st = ChangeRequestStatus(request.status.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status '{request.status}'")

    with get_session() as s:
        cr = update_change_request_status(s, cr_id, st, approved_by_id=request.approved_by_id)
        if not cr:
            raise HTTPException(status_code=404, detail=f"Change Request #{cr_id} not found")
        cr_status = cr.status.value

    return {"id": cr_id, "status": cr_status, "message": f"Change Request #{cr_id} updated."}


# ── 8. Project endpoints ────────────────────────────────────────────────────────


@app.get("/projects")
async def list_all_projects() -> dict:
    """List all projects."""
    from pmagent.db.repository import list_projects
    from pmagent.db.models import ProjectStatus

    with get_session() as s:
        projects = list_projects(s)
        projects_data = [
            {
                "id": p.id,
                "name": p.name,
                "project_type": p.project_type,
                "industry": p.industry,
                "status": p.status.value,
                "objectives": p.objectives,
                "requirements": p.requirements,
                "created_at": p.created_at.isoformat(),
            }
            for p in projects
        ]

    return {"count": len(projects_data), "projects": projects_data}


@app.get("/projects/{project_id}")
async def get_project_detail(project_id: int) -> dict:
    """Get full project details including tasks, milestones, team, blockers."""
    from pmagent.db.repository import (
        get_project, get_project_tasks, get_project_milestones,
        get_team_members, find_blockers, get_project_daily_logs,
        get_project_issues, get_project_change_requests,
    )
    from pmagent.db.models import TaskStatus

    with get_session() as s:
        project = get_project(s, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        tasks = get_project_tasks(s, project_id)
        milestones = get_project_milestones(s, project_id)
        members = get_team_members(s, project_id)
        blockers = find_blockers(s, project_id)
        daily_logs = get_project_daily_logs(s, project_id)
        issues = get_project_issues(s, project_id)
        crs = get_project_change_requests(s, project_id)

        # Calculate progress
        total_tasks = len(tasks)
        done_tasks = sum(1 for t in tasks if t.status == TaskStatus.done)
        progress = round((done_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0.0

        return {
            "id": project.id,
            "name": project.name,
            "project_type": project.project_type,
            "industry": project.industry,
            "status": project.status.value,
            "objectives": project.objectives,
            "requirements": project.requirements,
            "created_at": project.created_at.isoformat(),
            "progress_pct": progress,
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description or "",
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "estimated_hours": t.estimated_hours,
                    "actual_hours": t.actual_hours,
                    "progress_pct": t.progress_pct,
                    "due_date": t.due_date.strftime("%Y-%m-%d") if t.due_date else None,
                    "assigned_to": t.assigned_to.name if t.assigned_to else None,
                    "dependencies": t.dependencies or "",
                }
                for t in tasks
            ],
            "milestones": [
                {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description or "",
                    "status": m.status.value,
                    "due_date": m.due_date.strftime("%Y-%m-%d") if m.due_date else None,
                }
                for m in milestones
            ],
            "team": [
                {
                    "id": tm.id,
                    "name": tm.name,
                    "role": tm.role,
                    "availability_hours_per_week": tm.availability_hours_per_week,
                }
                for tm in members
            ],
            "blockers": blockers,
            "daily_logs": [
                {
                    "id": dl.id,
                    "task_id": dl.task_id,
                    "team_member": dl.team_member.name if dl.team_member else None,
                    "yesterday_progress": dl.yesterday_progress,
                    "today_plan": dl.today_plan,
                    "blockers": dl.blockers,
                    "hours_logged": dl.hours_logged,
                    "log_date": dl.log_date.isoformat(),
                }
                for dl in daily_logs
            ],
            "issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "description": i.description or "",
                    "priority": i.priority.value,
                    "status": i.status.value,
                    "assigned_to": i.assigned_to.name if i.assigned_to else None,
                    "resolution_notes": i.resolution_notes or "",
                    "created_at": i.created_at.isoformat(),
                }
                for i in issues
            ],
            "change_requests": [
                {
                    "id": cr.id,
                    "title": cr.title,
                    "justification": cr.justification,
                    "impact_scope": cr.impact_scope,
                    "status": cr.status.value,
                    "created_at": cr.created_at.isoformat(),
                }
                for cr in crs
            ],
        }


# ── 9. Task endpoints ───────────────────────────────────────────────────────────


class TaskStatusUpdate(BaseModel):
    status: str = Field(..., description="todo/in_progress/in_review/done/blocked/cancelled")


class TaskProgressUpdate(BaseModel):
    progress_pct: float = Field(..., ge=0, le=100, description="Progress percentage 0-100")


class TaskCreateRequest(BaseModel):
    name: str
    description: str = ""
    estimated_hours: float = 0.0
    priority: str = "medium"
    due_date: Optional[str] = None
    assigned_to_id: Optional[int] = None
    dependencies: str = ""


@app.post("/projects/{project_id}/tasks")
async def create_task_endpoint(project_id: int, request: TaskCreateRequest) -> dict:
    """Create a new task."""
    from pmagent.db.repository import create_task
    from pmagent.db.models import TaskStatus, Priority
    from datetime import datetime

    due = None
    if request.due_date:
        try:
            due = datetime.strptime(request.due_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")

    with get_session() as s:
        t = create_task(
            s,
            project_id=project_id,
            name=request.name,
            description=request.description,
            estimated_hours=request.estimated_hours,
            priority=request.priority,
            due_date=due,
            assigned_to_id=request.assigned_to_id,
            dependencies=request.dependencies,
        )
        tid = t.id

    return {
        "id": tid,
        "project_id": project_id,
        "name": request.name,
        "status": TaskStatus.todo.value,
        "message": f"Task '{request.name}' created.",
    }


@app.put("/tasks/{task_id}/status")
async def update_task_status_endpoint(task_id: int, request: TaskStatusUpdate) -> dict:
    """Update a task's status."""
    from pmagent.db.repository import update_task_status
    from pmagent.db.models import TaskStatus

    try:
        st = TaskStatus(request.status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Use: todo, in_progress, in_review, done, blocked, cancelled",
        )

    with get_session() as s:
        task = update_task_status(s, task_id, st)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task #{task_id} not found")

    return {"id": task_id, "status": st.value, "message": f"Task #{task_id} marked as '{st.value}'."}


@app.put("/tasks/{task_id}/progress")
async def update_task_progress_endpoint(task_id: int, request: TaskProgressUpdate) -> dict:
    """Update a task's progress percentage."""
    from pmagent.db.repository import update_task_progress

    with get_session() as s:
        task = update_task_progress(s, task_id, request.progress_pct)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task #{task_id} not found")
        pct = task.progress_pct

    return {"id": task_id, "progress_pct": pct, "message": f"Task #{task_id} progress updated to {pct}%."}


# ── 10. Milestone endpoints ─────────────────────────────────────────────────────


class MilestoneCreateRequest(BaseModel):
    name: str
    description: str = ""
    due_date: Optional[str] = None


class MilestoneStatusUpdate(BaseModel):
    status: str = Field(..., description="pending/on_track/at_risk/missed/achieved")


@app.post("/projects/{project_id}/milestones")
async def create_milestone_endpoint(project_id: int, request: MilestoneCreateRequest) -> dict:
    """Create a new milestone."""
    from pmagent.db.repository import create_milestone
    from pmagent.db.models import MilestoneStatus
    from datetime import datetime

    due = None
    if request.due_date:
        try:
            due = datetime.strptime(request.due_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_date format. Use YYYY-MM-DD")

    with get_session() as s:
        m = create_milestone(
            s,
            project_id=project_id,
            name=request.name,
            description=request.description,
            due_date=due,
        )
        mid = m.id

    return {
        "id": mid,
        "project_id": project_id,
        "name": request.name,
        "status": MilestoneStatus.pending.value,
        "message": f"Milestone '{request.name}' created.",
    }


@app.put("/milestones/{milestone_id}/status")
async def update_milestone_status_endpoint(milestone_id: int, request: MilestoneStatusUpdate) -> dict:
    """Update a milestone's status."""
    from pmagent.db.repository import update_milestone_status
    from pmagent.db.models import MilestoneStatus

    try:
        st = MilestoneStatus(request.status.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{request.status}'. Use: pending, on_track, at_risk, missed, achieved",
        )

    with get_session() as s:
        milestone = update_milestone_status(s, milestone_id, st)
        if not milestone:
            raise HTTPException(status_code=404, detail=f"Milestone #{milestone_id} not found")

    return {"id": milestone_id, "status": st.value, "message": f"Milestone #{milestone_id} updated to '{st.value}'."}


# ── 11. Daily Log endpoints ─────────────────────────────────────────────────────


class DailyLogCreateRequest(BaseModel):
    task_id: int
    team_member_id: int
    yesterday_progress: str = ""
    today_plan: str = ""
    blockers: str = ""
    hours_logged: float = 0.0


@app.post("/projects/{project_id}/daily-logs")
async def create_daily_log_endpoint(project_id: int, request: DailyLogCreateRequest) -> dict:
    """Create a daily standup log."""
    from pmagent.db.repository import create_daily_log

    with get_session() as s:
        log = create_daily_log(
            s,
            task_id=request.task_id,
            team_member_id=request.team_member_id,
            project_id=project_id,
            yesterday_progress=request.yesterday_progress,
            today_plan=request.today_plan,
            blockers=request.blockers,
            hours_logged=request.hours_logged,
        )
        lid = log.id

    return {"id": lid, "project_id": project_id, "message": f"Daily log #{lid} created."}


@app.get("/projects/{project_id}/daily-logs")
async def get_daily_logs(project_id: int) -> dict:
    """Get all daily logs for a project."""
    from pmagent.db.repository import get_project_daily_logs

    with get_session() as s:
        logs = get_project_daily_logs(s, project_id)
        logs_data = [
            {
                "id": dl.id,
                "task_id": dl.task_id,
                "team_member": dl.team_member.name if dl.team_member else None,
                "yesterday_progress": dl.yesterday_progress,
                "today_plan": dl.today_plan,
                "blockers": dl.blockers,
                "hours_logged": dl.hours_logged,
                "log_date": dl.log_date.isoformat(),
            }
            for dl in logs
        ]

    return {"project_id": project_id, "count": len(logs_data), "daily_logs": logs_data}


# ── 12. Blocker endpoint ───────────────────────────────────────────────────────


@app.get("/projects/{project_id}/blockers")
async def get_project_blockers(project_id: int) -> dict:
    """Get all blocked or overdue tasks for a project."""
    from pmagent.db.repository import find_blockers

    with get_session() as s:
        blockers = find_blockers(s, project_id)

    return {"project_id": project_id, "blockers": blockers, "count": len(blockers)}


# ── 13. Dashboard ──────────────────────────────────────────────────────────────


from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

_DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "static" / "index.html"


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    """Serve the project management dashboard."""
    if not _DASHBOARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(_DASHBOARD_PATH)

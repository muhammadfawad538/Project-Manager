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

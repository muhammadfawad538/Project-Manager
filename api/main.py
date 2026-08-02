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
from typing import Optional

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

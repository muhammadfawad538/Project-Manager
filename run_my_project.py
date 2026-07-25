#!/usr/bin/env python
"""Run pmagent with your own project inputs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pmagent.main import kickoff

inputs = {
    "project_type": "Personal To-Do REST API",
    "project_objectives": (
        "Build a working FastAPI CRUD API to manage a personal to-do list "
        "in exactly 3 days with a team of 2"
    ),
    "industry": "IT / Software",
    "deadline": "3 days",
    "team_members": """
- Fawad (Backend Engineer)
- Sara (Full-Stack Dev)
""",
    "project_requirements": """
1. Initialize FastAPI project with folder structure and dependencies
2. Set up SQLite database with a Task model (id, title, description, status, created_at)
3. Create POST /tasks endpoint with input validation and error handling
4. Create GET /tasks and GET /tasks/{id} endpoints
5. Create PUT /tasks/{id} and DELETE /tasks/{id} endpoints
6. Add Pydantic schemas for request/response validation
7. Write 5 unit tests covering all endpoints
8. Add API documentation with example requests
""",
}

if __name__ == "__main__":
    kickoff(persist=True, inputs=inputs)

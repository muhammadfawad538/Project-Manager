"""Tests for the L1 project planning crew."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pmagent.main import (  # noqa: E402
    ProjectPlan,
    TaskEstimate,
    Milestone,
    kickoff,
)
from pmagent.helper import load_env  # noqa: E402


# ── Helper ──────────────────────────────────────────────────────────

def _mock_dotenv(monkeypatch):
    """Prevent load_env from reading a real .env during tests."""
    monkeypatch.setattr("pmagent.helper.load_dotenv", lambda *a, **kw: None)


# ── Models ──────────────────────────────────────────────────────────

class TestProjectPlanModel:
    def test_valid_project_plan(self):
        plan = ProjectPlan(
            tasks=[
                TaskEstimate(
                    task_name="Design DB schema",
                    estimated_time_hours=8.0,
                    required_resources=["PostgreSQL", "Bob"],
                )
            ],
            milestones=[
                Milestone(
                    milestone_name="Sprint 1 complete",
                    tasks=["task-1"],
                )
            ],
        )
        assert len(plan.tasks) == 1
        assert plan.tasks[0].estimated_time_hours == 8.0
        assert plan.milestones[0].milestone_name == "Sprint 1 complete"

    def test_project_plan_roundtrip_json(self):
        import json
        plan = ProjectPlan(
            tasks=[TaskEstimate(task_name="Write tests", estimated_time_hours=4.0, required_resources=["pytest"])],
            milestones=[Milestone(milestone_name="Beta", tasks=["t1"])],
        )
        dumped = plan.model_dump()
        restored = ProjectPlan(**dumped)
        assert restored == plan

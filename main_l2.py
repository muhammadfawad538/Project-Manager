# L2: Sprint Progress Report
# Data source: Trello API (if creds present) OR local pmagent database.
# Run with: python main_l2.py

import warnings
warnings.filterwarnings('ignore')

import os
import sys
import json
from pathlib import Path
from datetime import date
from typing import Any

import yaml
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from crewai.tools import BaseTool

load_dotenv()
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "")
os.environ["OPENAI_MODEL_NAME"] = "gpt-4o-mini"

# ── Resolve config path ───────────────────────────────────────────────────────
_CONFIG_DIR = Path(__file__).resolve().parent / "config_l2"

# ── Data Source: Trello ───────────────────────────────────────────────────────
FALLBACK_CARDS = json.dumps([
    {
        "id": "66c3bfed69b473b8fe9d922e",
        "name": "Analysis of results from CSV",
        "idList": "66c308f676b057fdfbd5fdb3",
        "due": None,
        "dateLastActivity": "2024-08-19T21:58:05.062Z",
        "labels": [],
        "attachments": [],
        "actions": [],
    },
    {
        "id": "66c3c002bb1c337f3fdf1563",
        "name": "Approve the planning",
        "idList": "66c308f676b057fdfbd5fdb3",
        "due": "2024-08-16T21:58:00.000Z",
        "dateLastActivity": "2024-08-19T21:58:57.697Z",
        "labels": [{"name": "Urgent", "color": "red"}],
        "attachments": [],
        "actions": [
            {
                "id": "66c3c021f3c1bb157028f53d",
                "data": {"text": "This was harder then expects it is alte"},
                "type": "commentCard",
                "date": "2024-08-19T21:58:57.683Z",
                "memberCreator": {"fullName": "Joao Moura"},
            }
        ],
    },
    {
        "id": "66c3bff4a25b398ef1b6de78",
        "name": "Scaffold of the initial app UI",
        "idList": "66c3bfdfb851ad9ff7eee159",
        "due": None,
        "dateLastActivity": "2024-08-19T21:58:12.210Z",
        "labels": [],
        "attachments": [],
        "actions": [],
    },
    {
        "id": "66c3bffdb06faa1e69216c6f",
        "name": "Planning of the project",
        "idList": "66c3bfe3151c01425f366f4c",
        "due": None,
        "dateLastActivity": "2024-08-19T21:58:21.081Z",
        "labels": [],
        "attachments": [],
        "actions": [],
    },
])


class BoardDataFetcherTool(BaseTool):
    """Fetches all cards from a Trello board (or returns fallback data)."""
    name: str = "Trello Board Data Fetcher"
    description: str = "Fetches card data, comments, and activity from a Trello board."

    api_key: str = os.environ.get("TRELLO_API_KEY", "")
    api_token: str = os.environ.get("TRELLO_API_TOKEN", "")
    board_id: str = os.environ.get("TRELLO_BOARD_ID", "")

    def _run(self) -> dict:
        if not (self.api_key and self.api_token and self.board_id):
            return json.loads(FALLBACK_CARDS)
        url = (
            f"{os.getenv('DLAI_TRELLO_BASE_URL', 'https://api.trello.com')}"
            f"/1/boards/{self.board_id}/cards"
        )
        query = {
            "key": self.api_key,
            "token": self.api_token,
            "fields": "name,idList,due,dateLastActivity,labels",
            "attachments": "true",
            "actions": "commentCard",
        }
        try:
            import requests as _req
            response = _req.get(url, params=query, timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return json.loads(FALLBACK_CARDS)


class CardDataFetcherTool(BaseTool):
    """Fetches a single Trello card's details."""
    name: str = "Trello Card Data Fetcher"
    description: str = "Fetches card data from a Trello board."

    api_key: str = os.environ.get("TRELLO_API_KEY", "")
    api_token: str = os.environ.get("TRELLO_API_TOKEN", "")

    def _run(self, card_id: str) -> dict:
        if not (self.api_key and self.api_token):
            return {"error": "Trello creds not set"}
        url = (
            f"{os.getenv('DLAI_TRELLO_BASE_URL', 'https://api.trello.com')}"
            f"/1/cards/{card_id}"
        )
        query = {"key": self.api_key, "token": self.api_token}
        try:
            import requests as _req
            response = _req.get(url, params=query, timeout=15)
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return {"error": "Failed to fetch card data"}


# ── Data Source: Local Database ───────────────────────────────────────────────
class DbProjectFetcherTool(BaseTool):
    """
    Reads project data from the local pmagent SQLite database.

    Returns a JSON list of tasks shaped like Trello cards so the rest of
    the L2 pipeline can stay data-source agnostic.
    """
    name: str = "Database Project Fetcher"
    description: str = (
        "Fetches project tasks from the local pmagent database. "
        "Returns task data (name, status, due date, assignee, progress) "
        "as a JSON string. Use this when Trello is not configured."
    )

    def _run(self, project_id: int = 0) -> str:
        try:
            src_root = Path(__file__).resolve().parent.parent / "src"
            if str(src_root) not in sys.path:
                sys.path.insert(0, str(src_root))

            from pmagent.db.session import get_session
            from pmagent.db.models import TaskStatus
            from pmagent.db.repository import (
                get_project_tasks, get_team_members,
                get_project_milestones, get_project_daily_logs,
            )
        except ImportError as exc:
            return json.dumps({"error": f"Cannot import pmagent DB: {exc}"})

        with get_session() as session:
            tasks       = list(get_project_tasks(session, project_id))
            members     = list(get_team_members(session, project_id))
            milestones  = list(get_project_milestones(session, project_id))
            logs        = list(get_project_daily_logs(session, project_id))

            # Serialize everything to plain dicts while session is open
            tasks_plain = [
                {c.name: getattr(t, c.name) for c in t.__table__.columns}
                for t in tasks
            ]
            members_plain = [
                {c.name: getattr(m, c.name) for c in m.__table__.columns}
                for m in members
            ]
            member_map = {m["id"]: m["name"] for m in members_plain}
            milestones_plain = [
                {c.name: getattr(ms, c.name) for c in ms.__table__.columns}
                for ms in milestones
            ]

        today = date.today()
        DONE    = TaskStatus.done.value
        BLOCKED = TaskStatus.blocked.value

        cards = []
        for t in tasks_plain:
            task_logs = [l for l in logs if l.task_id == t["id"]]
            comments = [
                f"[{l.log_date.date()}] {l.yesterday_progress or '(no note)'}"
                for l in sorted(task_logs, key=lambda x: x.log_date)
            ]
            labels = [t["status"]]
            if t["due_date"] and t["due_date"].date() < today and t["status"] != DONE:
                labels.append("overdue")
            if t["status"] == BLOCKED:
                labels.append("blocked")
            if t["progress_pct"] >= 100:
                labels.append("completed")

            cards.append({
                "id":              str(t["id"]),
                "name":            t["name"],
                "idList":          t["status"],
                "due":             t["due_date"].isoformat() if t["due_date"] else None,
                "dateLastActivity": t["updated_at"].isoformat() if t["updated_at"] else None,
                "labels":          [{"name": lb} for lb in labels],
                "attachments":     [],
                "actions":         [{"data": {"text": c}} for c in comments],
                "assignee":        member_map.get(t["assigned_to_id"]) or "Unassigned",
                "progress_pct":    t["progress_pct"],
                "estimated_hours": t["estimated_hours"],
                "description":     t["description"] or "",
            })

        milestone_summaries = [
            f"Milestone: {m['name']} ({m['status']})"
            + (f" due {m['due_date'].date()}" if m["due_date"] else "")
            for m in milestones_plain
        ]

        return json.dumps({
            "tasks":       cards,
            "milestones":  milestone_summaries,
            "total_tasks": len(cards),
            "completed":   sum(1 for c in cards if "completed" in [l["name"] for l in c["labels"]]),
        })


# ── Load YAML configs ─────────────────────────────────────────────────────────
with open(_CONFIG_DIR / "agents.yaml", "r", encoding="utf-8") as f:
    agents_config = yaml.safe_load(f)

with open(_CONFIG_DIR / "tasks.yaml", "r", encoding="utf-8") as f:
    tasks_config = yaml.safe_load(f)


# ── Choose data source ────────────────────────────────────────────────────────
# Use DB if at least one project exists with tasks, otherwise fall back to Trello.
def _db_has_data() -> bool:
    try:
        src_root = Path(__file__).resolve().parent.parent / "src"
        if str(src_root) not in sys.path:
            sys.path.insert(0, str(src_root))
        from pmagent.db.session import get_session
        from pmagent.db.repository import get_project_tasks
        with get_session() as session:
            return len(get_project_tasks(session, 1)) > 0
    except Exception:
        return False


USE_DB = _db_has_data()

if USE_DB:
    data_source_tools = [DbProjectFetcherTool()]
    source_label = "local database"
else:
    data_source_tools = [BoardDataFetcherTool(), CardDataFetcherTool()]
    source_label = "Trello (fallback)"


# ── Create Agents ─────────────────────────────────────────────────────────────
data_collection_agent = Agent(
    config=agents_config["data_collection_agent"],
    tools=data_source_tools,
)

analysis_agent = Agent(
    config=agents_config["analysis_agent"],
)


# ── Create Tasks ──────────────────────────────────────────────────────────────
data_collection = Task(
    config=tasks_config["data_collection"],
    agent=data_collection_agent,
)

data_analysis = Task(
    config=tasks_config["data_analysis"],
    agent=analysis_agent,
)

report_generation = Task(
    config=tasks_config["report_generation"],
    agent=analysis_agent,
)


# ── Assemble Crew ─────────────────────────────────────────────────────────────
crew = Crew(
    agents=[data_collection_agent, analysis_agent],
    tasks=[data_collection, data_analysis, report_generation],
    verbose=True,
)


# ── Run ───────────────────────────────────────────────────────────────────────
def kickoff(project_id: int = 1):
    print("=" * 60)
    print(f"  CrewAI L2 – Sprint Progress Report (source: {source_label})")
    print("=" * 60)
    print()

    result = crew.kickoff()

    # ── Report ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Sprint Report")
    print("=" * 60)
    print(result.raw)

    # ── Usage metrics ─────────────────────────────────────────────────────────
    try:
        costs = 0.150 * (
            crew.usage_metrics.prompt_tokens + crew.usage_metrics.completion_tokens
        ) / 1_000_000
        print(f"\nTotal costs: ${costs:.4f}")
        print(pd.DataFrame([crew.usage_metrics.dict()]))
    except Exception:
        pass

    # ── Persist report to DB ──────────────────────────────────────────────────
    try:
        from pmagent.persistence import save_l2_report
        save_l2_report(
            project_id=project_id,
            raw_report=result.raw,
            prompt_tokens=crew.usage_metrics.prompt_tokens,
            completion_tokens=crew.usage_metrics.completion_tokens,
            estimated_cost_usd=costs if 'costs' in dir() else 0.0,
            summary=result.raw[:500],
        )
        print(f"\n[OK] Report saved to DB (project_id={project_id})")
    except Exception as exc:
        warnings.warn(f"DB save failed: {exc}")

    return result


if __name__ == "__main__":
    kickoff()

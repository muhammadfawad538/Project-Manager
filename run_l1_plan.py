# Line ending: LF
# Encoding: UTF-8
"""Quick demo: L1 crew creates a plan and persists it to the database."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure src/ is on the path so `pmagent` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

# Load .env before checking the key
load_dotenv(Path(__file__).resolve().parent / ".env")

def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or "your_" in api_key:
        print("ERROR: Set OPENAI_API_KEY in .env before running.")
        sys.exit(1)

    # 1. Create DB tables
    from pmagent.db.session import create_db
    create_db()
    print("✅ Database ready\n")

    # 2. Run L1 planning crew
    from pmagent.main import kickoff
    result = kickoff(persist=True)

    # 3. Show what was saved
    from pmagent.db.session import get_session
    from pmagent.db.repository import get_project_tasks, get_project_milestones

    pid = 1  # first project saved
    with get_session() as session:
        tasks = get_project_tasks(session, pid)
        milestones = get_project_milestones(session, pid)

    print(f"\n===== Saved to DB (project_id={pid}) =====")
    print(f"Tasks:      {len(tasks)}")
    print(f"Milestones: {len(milestones)}")
    print(f"Raw cost:   ${result['cost_usd']:.4f}")
    print(f"Tokens in:  {result['usage']['prompt_tokens']:,}")
    print(f"Tokens out: {result['usage']['completion_tokens']:,}")


if __name__ == "__main__":
    main()

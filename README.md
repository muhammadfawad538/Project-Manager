# pmagent — AI-Powered Project Management

CrewAI-based multi-agent system for project planning, risk management, and resource allocation. Built for the GCC market with bilingual (Arabic + English) document generation.

## What it does

Give it a project brief — it returns a complete PM package:

- **Work Breakdown Structure** — numbered tasks, estimates, dependencies, milestones
- **Risk Register** — identified risks with probability, impact, mitigation, contingency
- **Resource Allocation** — task-to-member mapping with load analysis and rebalancing
- **Executive Summary** — ready to hand to stakeholders

## Quick Start

```bash
# 1. Clone and install
git clone <repo-url>
cd project-management
pip install -r requirements.txt

# 2. Set your OpenAI key
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run via CLI
python -m pmagent.main

# 4. Or run the API server
python -m api.main
# Then POST to http://localhost:8000/plan

# 5. Or use the skill
# Just say "I need a project plan for..." and the senior-pm-advisor
# skill will trigger automatically.
```

## Project Structure

```
src/pmagent/
├── __init__.py
├── main.py              # Crew assembly, kickoff(), CLI entry point
├── config/
│   ├── __init__.py      # Loads agents.yaml + tasks.yaml, builds CrewAI objects
│   ├── agents.yaml      # 4 agent definitions (planner, risk, resource, manager)
│   ├── tasks.yaml       # 4 chained tasks with Pydantic output validation
│   └── models.py        # Pydantic models for structured output
├── tools/
│   ├── __init__.py
│   └── pm_tools.py      # Custom CrewAI tools (DB-backed: CRUD, blockers, logs)
└── db/
    ├── __init__.py
    ├── session.py       # SQLAlchemy engine + session factory
    ├── models.py        # ORM models: Project, Task, TeamMember, Milestone, etc.
    └── repository.py    # Database CRUD functions

api/
├── main.py              # FastAPI server: POST /plan, GET /health
└── requirements.txt     # API-specific deps

test_bilingual.py        # Test runner: English + Arabic side-by-side
test_outputs/            # Generated test results (gitignored)

.claude/skills/
└── senior-pm-advisor/   # The PM advisor skill (triggers on "I need a project plan")
    ├── SKILL.md
    └── references/      # PM document templates (plan, status report, risk, sprint)
```

## Architecture

4 agents in a sequential crew:

| Agent | Role | Output |
|-------|------|--------|
| `project_planner` | Breaks requirements into WBS | Tasks, milestones, critical path |
| `risk_analyst` | Identifies and assesses risks | Risk register with mitigation plans |
| `resource_allocator` | Assigns tasks to team members | Allocation matrix + load analysis |
| `manager` | Synthesizes all outputs | Final PM package (all sections) |

Each specialist produces **validated structured output** (Pydantic) that feeds the next agent.

## Tech Stack

- **CrewAI** — multi-agent orchestration
- **OpenAI GPT-4o** — LLM (configurable)
- **SQLAlchemy** — ORM + SQLite
- **Pydantic** — structured output validation
- **FastAPI** — REST API server (`POST /plan`, `GET /health`)

## Requirements

- Python 3.10+
- OpenAI API key
- See `requirements.txt`

## License

MIT

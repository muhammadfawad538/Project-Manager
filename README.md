# AI Project Planners

Production-ready multi-agent system that automates project planning, time/resource estimation, and team allocation using CrewAI and a Groq-accelerated LLM.

## Problem it solves

Manually breaking down projects into tasks, estimating timelines, and assigning team members is slow, inconsistent, and error-prone. This project replaces that with a 3-agent CrewAI pipeline: feed it raw project requirements and team info, and it produces a structured, Pydantic-validated project plan with task breakdowns, hour-level estimates, and evenly-distributed resource assignments in one run.

## Quick start

```bash
cp .env.example .env            # add your OPENAI_API_KEY
pip install -r requirements.txt
python -m pmagent.main          # run the crew
```

Or with the CrewAI CLI:

```bash
crewai run
```

## How it works

Three specialized agents run in sequence:

| Agent | Role |
|-------|------|
| **Project Planner** | Breaks project requirements into granular tasks with timelines and dependencies |
| **Estimation Analyst** | Estimates hours, resources, and effort per task; flags risks |
| **Resource Allocator** | Assigns tasks to team members by skill match and workload balance |

Output is validated through a `ProjectPlan` Pydantic model (tasks + milestones) and printed as formatted tables.

## Structure

```
src/pmagent/
  main.py               crew assembly + kickoff
  helper.py             utility helpers
  config/
    agents.yaml           agent definitions (role, goal, backstory)
    tasks.yaml            task definitions, expected output, agent binding
tests/
  test_main.py           smoke tests for crew wiring
  conftest.py            test fixtures
```

## Tech

- [CrewAI](https://docs.crewai.com) — multi-agent orchestration
- [Groq](https://groq.com) — fast LLM inference (`gpt-4o-mini`)
- Pydantic v2 — structured output validation
- YAML config — agent and task definitions loaded at runtime
- Pandas — usage metrics and result formatting

## Env vars

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Your OpenAI API key (required) |

## License

MIT

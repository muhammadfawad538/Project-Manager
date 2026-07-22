# pmagent

Production-ready CrewAI agents.

## Setup

```bash
cp .env.example .env          # fill in your API keys
crewai install                # install dependencies + tools
```

## Run

```bash
crewai run                    # sequential crew with inputs from CLI
python -m pmagent.main        # direct entry point
```

## Test

```bash
pytest
```

## Structure

```
src/pmagent/
  __init__.py           package marker
  main.py               entry point — crew assembly + kickoff
  config/
    __init__.py         package marker
    agents.yaml          agent definitions (loaded at runtime)
    tasks.yaml           task definitions (loaded at runtime)
tests/
  test_main.py          smoke tests for crew wiring
memory/                 CrewAI training data (*.pkl output)
logs/                   runtime logs
outputs/                generated deliverables (.md, .json, etc.)
```

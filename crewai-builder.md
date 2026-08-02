---
name: crewai-builder
description: Apply this skill when building, designing, or reviewing any CrewAI multi-agent project. Covers project scaffolding, agent/task design, structured output, custom tools, CrewAI Flow, testing, training, multi-LLM setup, and production deployment. Use whenever the task involves creating agents, crews, or flows with CrewAI.
---

# CrewAI Builder Skill

Use this skill as a reference whenever building a CrewAI project — from initial scaffold to production deployment.

---

## 1. Project Setup (L6 — Production Structure)

### Create a new project
```bash
crewai create crew <project_name> --provider openai --classic
# Interactive prompts: pick provider → pick model → skip API key (use .env instead)
cd <project_name>
crewai install
```

### Auto-generated structure
```
<project_name>/
├── .env
├── pyproject.toml
├── src/<project_name>/
│   ├── __init__.py
│   ├── main.py          ← entry point, edit this
│   └── config/
│       ├── agents.yaml  ← define agents here
│       └── tasks.yaml   ← define tasks here
```

### .env template
```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-4o-mini
SERPER_API_KEY=...       # optional, for web search tools
GROQ_API_KEY=...         # optional, for Groq LLM
```

---

## 2. Agent Design (L1, L5)

### YAML template — `config/agents.yaml`
```yaml
agent_name:
  role: >
    Short, specific title of the agent's role
  goal: >
    Clear, measurable goal this agent works toward
  backstory: >
    Rich persona narrative. The more context you give the LLM
    about who this agent is, the better and more consistent
    the output will be.
  allow_delegation: false
  verbose: true
```

### Best practices for agent design
- **Role**: Specific title, not generic ("Senior Research Analyst" not "Analyst")
- **Goal**: Actionable and measurable ("Find 3-5 trending topics" not "Find topics")
- **Backstory**: Include domain expertise, company context, and personality — this shapes tone and quality
- **allow_delegation**: Set `false` unless agents truly need to pass work to each other
- **One agent = one responsibility** — don't make one agent do research AND writing

---

## 3. Task Design (L1, L3)

### YAML template — `config/tasks.yaml`
```yaml
task_name:
  description: >
    Clear description of what the agent should do.
    Use {variable_name} for dynamic inputs passed at kickoff.
  expected_output: >
    Precise description of what the output should look like.
  agent: agent_name_from_yaml
  context:
    - previous_task_name    # optional: depends on another task's output
  output_pydantic:          # optional: enforce structured output
    - SomePydanticModel
```

### Task chaining with `context`
- Task B with `context: [task_a]` means B receives A's output as additional context
- Tasks in the YAML run in order; use `context` to build a dependency chain
- Without `context`, tasks are independent

---

## 4. Structured Output with Pydantic (L1, L3, L5)

### Define models in `main.py`
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class MyOutput(BaseModel):
    field_name: str = Field(..., description="Description of this field")
    items: List[str] = Field(..., description="List of items")
    optional_field: Optional[float] = Field(None, description="Optional numeric field")
```

### Attach to a task
```yaml
my_task:
  description: "..."
  expected_output: "..."
  agent: my_agent
  output_pydantic:
    - MyOutput
```

### Access the result
```python
result = crew.kickoff(inputs={...})
result.pydantic          # Returns Pydantic model instance
result.pydantic.dict()   # Converts to dictionary
```

---

## 5. Custom Tools (L2)

### Create a tool by extending `BaseTool`
```python
from crewai_tools import BaseTool
import requests

class MyCustomTool(BaseTool):
    name: str = "My Tool Name"
    description: str = "What this tool does and when to use it."

    # Tool-specific config (loaded from env vars)
    api_key: str = os.environ['MY_API_KEY']

    def _run(self, input_param: str) -> dict:
        """The actual logic — must return a string or dict."""
        url = f"https://api.example.com/endpoint?q={input_param}"
        response = requests.get(url, params={"key": self.api_key})
        if response.status_code == 200:
            return response.json()
        return {"error": "Request failed"}
```

### Attach tools to an agent
```yaml
my_agent:
  role: "..."
  goal: "..."
  backstory: "..."
  # Tools are attached in main.py, not YAML
```

```python
from my_tools import MyCustomTool
my_agent.tools = [MyCustomTool()]
```

### Built-in tools available
| Tool | Use |
|------|-----|
| `SerperDevTool` | Web search via Serper API |
| `ScrapeWebsiteTool` | Scrape content from a URL |
| `WebsiteSearchTool` | Search within a specific website |
| `FileReadTool` | Read local files (CSV, TXT, etc.) |

---

## 6. Crew Assembly & Kickoff (L1–L6)

### `main.py` pattern
```python
from crewai import Crew, Process, LLM
from content_creator.config import agents, tasks

# Optional: override LLM per agent
from crewai import LLM
groq_llm = LLM(model="groq/llama-3.3-70b-versatile")
openai_llm = LLM(model="gpt-4o-mini")

# Load agents from YAML
agent1 = agents.agent_name_agent

# Attach tools
from crewai_tools import SerperDevTool
agent1.tools = [SerperDevTool()]

# Assign different LLMs to specific agents
agent1.llm = groq_llm

# Load tasks from YAML
task1 = tasks.task_name

# Create crew
crew = Crew(
    agents=[agent1, agent2],
    tasks=[task1, task2],
    process=Process.sequential,  # or Process.hierarchical
    verbose=True,
)

# Run with inputs matching {placeholders} in task descriptions
if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "AI in 2025"})
    print(result.raw)           # Raw string output
    print(result.pydantic)      # Structured output (if output_pydantic set)
```

---

## 7. Multi-LLM Setup (L5)

### When to use multiple LLMs
- Cheap/fast LLM for simple agents (Groq Llama)
- Powerful LLM for complex agents (GPT-4o, Claude)

### Pattern
```python
from crewai import LLM

# Define LLM instances
groq_llm = LLM(model="groq/llama-3.3-70b-versatile")
openai_llm = LLM(model="gpt-4o-mini")

# Assign per agent (loaded from YAML)
agents.market_news_monitor_agent.llm = groq_llm
agents.data_analyst_agent.llm = groq_llm
# Others use default (from OPENAI_MODEL_NAME in .env)
```

---

## 8. CrewAI Flow (L3)

### Flow = multi-step pipeline with routing

```python
from crewai import Flow
from crewai.flow.flow import listen, start, and_, or_, router

class MyFlow(Flow):

    @start()
    def step_one(self):
        return {"data": "initial data"}

    @listen(step_one)
    def step_two(self, state):
        return crew_a.kickoff(inputs=state)

    @router(step_two)           # Branching logic
    def decide_path(self, result):
        if result["score"] > 70:
            return "high"
        return "low"

    @listen("high")             # Listens on specific route
    def high_path(self, result):
        return premium_crew.kickoff(inputs=result)

    @listen("low")
    def low_path(self, result):
        return standard_crew.kickoff(inputs=result)
```

### Key Flow decorators
| Decorator | Purpose |
|-----------|---------|
| `@start()` | Entry point — runs first |
| `@listen(step)` | Runs after `step` completes |
| `@router(step)` | Routes to named paths based on return value |
| `@listen('path_name')` | Handles a specific route from a router |
| `and_(a, b)` | Waits for BOTH a and b to complete |
| `or_(a, b)` | Runs when EITHER a or b completes |

### Run the flow
```python
flow = MyFlow()
result = flow.kickoff()
flow.plot()  # Generates HTML visualization
```

---

## 9. Testing & Training (L4)

### Test crew quality
```python
from crewai import LLM

eval_llm = LLM(model="gpt-4o-mini")
crew.test(n_iterations=3, eval_llm=eval_llm)
```
- Runs the crew multiple times and evaluates output quality using an LLM judge
- Check results for consistency and improvement areas

### Train crew (save learned patterns)
```python
crew.train(n_iterations=1, filename='training.pkl')
```
- Generates a training file that can improve future runs
- Useful when you have a consistent task and want to optimize performance

---

## 10. Cost Tracking (L1, L2, L5)

### After `kickoff()`, check usage:
```python
import pandas as pd

# Crew-level metrics
costs = 0.150 * (crew.usage_metrics.prompt_tokens + crew.usage_metrics.completion_tokens) / 1_000_000
print(f"Total costs: ${costs:.4f}")

df = pd.DataFrame([crew.usage_metrics.dict()])
```

### Flow-level metrics:
```python
# Access from individual crew results in flow
token_usage = flow.state["results"][0].token_usage
costs = 0.150 * token_usage.total_tokens / 1_000_000
```

---

## 11. Quick Reference Checklist

When building any CrewAI project, follow this order:

```
[ ] 1. crewai create crew <name> --provider openai --classic
[ ] 2. cd <name> && crewai install
[ ] 3. Edit .env with API keys
[ ] 4. Define agents in config/agents.yaml
[ ] 5. Define tasks in config/tasks.yaml
[ ] 6. Wire crew in main.py (attach tools, set LLMs)
[ ] 7. crewai run
```

---

## 12. Common Patterns by Use Case

| Use Case | Pattern |
|----------|---------|
| Research + Report | 2 agents (researcher, writer), sequential tasks with context |
| Data Pipeline | FileReadTool + analysis agents, structured output with Pydantic |
| External Integration | Custom BaseTool + data collection agent |
| Content at Scale | Multi-LLM (cheap for research, expensive for writing) |
| Sales Automation | Flow with router → branching paths (high/medium/low leads) |
| Production Ready | YAML configs + main.py entry point + .env + crewai CLI |

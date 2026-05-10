---
title: CogniRoute
emoji: 🧠
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# CogniRoute

CogniRoute is a hackathon MVP for a cognitive orchestration runtime for autonomous software engineering.

The goal is not to build AGI, an agent swarm, or production infrastructure. The goal is to make one orchestration loop clear, inspectable, and believable:

```text
User request
-> Architect agent
-> markdown execution state
-> scoped frontend worker
-> verifier agent
-> updated execution state
```

## What It Demonstrates

- Heavy reasoning roles for planning and verification
- Lightweight scoped workers for bounded execution
- Sequential orchestration with no queues or parallelism
- Markdown-based state management
- Pydantic schemas for runtime contracts
- Role-based routing across OpenAI-compatible model endpoints
- A FastAPI endpoint that returns the full execution trace

## Project Layout

```text
.
├── backend
│   ├── Dockerfile
│   ├── app
│   │   ├── main.py
│   │   └── settings.py
│   └── cogniroute
│       ├── orchestration_loop.py
│       ├── architect_agent.py
│       ├── frontend_worker.py
│       ├── verifier_agent.py
│       ├── state_manager.py
│       ├── services
│       │   └── llm.py
│       └── schemas
├── frontend
│   └── app
└── state
    ├── implementation_plan.md
    └── system_contracts.md
```

## Core Endpoint

```http
POST /generate
```

Example:

```bash
curl -X POST http://localhost:8001/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Build a compact dashboard that shows orchestration state"}'
```

Expected high-level response:

```json
{
  "run": {
    "verifier_report": {
      "status": "PASS",
      "issues": []
    },
    "routing_log": [
      {
        "node_id": "frontend_001",
        "chosen_worker": "frontend"
      }
    ]
  }
}
```

## Run Locally

From the project root:

```bash
cd "/Users/dev/Documents/Cognition Router"
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Health check:

```bash
curl http://localhost:8001/health
```

API docs:

```text
http://localhost:8001/docs
```

## Model Configuration

CogniRoute uses role-based model routing. Configure endpoints with environment variables:

```bash
export COGNIROUTE_ARCHITECT_BASE_URL="https://your-architect-endpoint/v1"
export COGNIROUTE_WORKER_BASE_URL="https://your-worker-endpoint/v1"
export COGNIROUTE_VERIFIER_BASE_URL="https://your-verifier-endpoint/v1"
```

Optional:

```bash
export COGNIROUTE_OPENAI_API_KEY="..."
export COGNIROUTE_ARCHITECT_MODEL="Qwen/Qwen2.5-7B-Instruct"
export COGNIROUTE_WORKER_MODEL="Qwen/Qwen2.5-7B-Instruct"
export COGNIROUTE_VERIFIER_MODEL="Qwen/Qwen2.5-7B-Instruct"
```

If a role endpoint fails or returns invalid structured output, the MVP falls back to deterministic behavior so the demo loop still completes.

## Deploy On Hugging Face Spaces

Use a Docker Space.

Space README front matter:

```yaml
---
title: CogniRoute
emoji: 🧠
colorFrom: blue
colorTo: cyan
sdk: docker
app_port: 7860
---
```

The Dockerfile is at:

```text
backend/Dockerfile
```

It expects the repository root as build context:

```bash
docker build -f backend/Dockerfile .
```

Set these as Hugging Face Space Variables:

```text
COGNIROUTE_ARCHITECT_BASE_URL
COGNIROUTE_WORKER_BASE_URL
COGNIROUTE_VERIFIER_BASE_URL
```

If your endpoints need authentication, set this as a Space Secret:

```text
COGNIROUTE_OPENAI_API_KEY
```

## Runtime State

CogniRoute externalizes execution state into markdown:

- `state/implementation_plan.md`
- `state/system_contracts.md`

Telemetry is written to:

- `state/telemetry.json`

`state/telemetry.json` is intentionally ignored by git.

## Design Constraints

CogniRoute intentionally avoids:

- parallel execution
- async job queues
- vector databases
- browser agents
- recursive replanning
- autonomous retry loops
- production infrastructure

The MVP should feel like a cognitive orchestration runtime, not a chatbot wrapper.

## Current Status

Implemented:

- `POST /generate`
- architect-generated task graph and markdown state
- one scoped frontend worker task
- single-pass verifier
- checklist state updates
- role endpoint routing with deterministic fallback
- Dockerfile for Hugging Face Spaces

Next likely steps:

- save generated artifacts under `state/artifacts/`
- build a frontend dashboard for traces and task graphs
- expose clearer runtime snapshots for demos

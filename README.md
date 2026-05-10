## CogniRoute (Hackathon MVP)

CogniRoute is an experimental **AI orchestration runtime** that demonstrates:

- **Structured task graphs**
- **Capability routing** to scoped workers
- **Cognitive scheduling** (heavy “Architect” + lightweight Workers + heavy “Verifier”)
- **Verification checkpoints**
- **Observability-first UX** (graph + timeline + telemetry)

This repo is intentionally **not production infrastructure**. It’s a believable prototype of a future “cognitive operating system”.

### Monorepo layout

- `backend/`: FastAPI + LangGraph orchestration runtime
- `frontend/`: Next.js + Tailwind + React Flow visualization UI

### Run locally (dev)

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev -- --port 3000
```

Then open `http://localhost:3000`.

### Environment (optional)

The MVP can run in **mock mode** with deterministic planning/execution.

If you want real model calls against an OpenAI-compatible endpoint:

- `COGNIROUTE_OPENAI_BASE_URL` (e.g. `http://localhost:8001/v1`)
- `COGNIROUTE_OPENAI_API_KEY` (if required by your gateway)
- `COGNIROUTE_ARCHITECT_MODEL` (e.g. `qwen3-32b`)
- `COGNIROUTE_WORKER_MODEL` (e.g. `qwen2.5-coder-7b`)
- `COGNIROUTE_VERIFIER_MODEL` (e.g. `deepseek-reasoner`)


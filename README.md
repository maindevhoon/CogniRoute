# CogniRoute 🧠

![CogniRoute](https://via.placeholder.com/1200x400/0d1117/38bdf8?text=CogniRoute)

CogniRoute is an advanced AI Orchestration Runtime and Web Interface for multi-agent code generation.

## Overview

CogniRoute uses a sophisticated multi-agent pipeline to generate reliable, multi-file codebases:

1. **Architect**: Analyzes the prompt and generates a high-level architecture reasoning and a comprehensive file plan.
2. **Workers**: Parallel autonomous agents that generate the actual code for each planned file based on the architecture.
3. **Verifier**: Audits the generated code to ensure it meets requirements, automatically triggering retries for any failures.

## Project Structure

- `backend/`: FastAPI Python backend orchestration runtime. Handles SSE streaming of the multi-agent pipeline.
- `frontend/`: Next.js React frontend. A beautifully designed, dark-themed command center for interacting with the orchestrator, tracking real-time status, viewing reasoning, and reviewing generated code.

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Features

- **Live Stream Tracking**: View real-time traces and status updates as the orchestration runs.
- **Architecture Insights**: Read the AI Architect's reasoning before code generation begins.
- **Code Viewer**: Live-updating code viewer for all generated files.
- **Modern UI**: Stunning, glassmorphic UI built with TailwindCSS.

## License
MIT

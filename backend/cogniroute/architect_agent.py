from __future__ import annotations

import uuid

from .llm import safe_json_loads
from .schemas import ModelTier, TaskGraph, TaskNode, WorkerType
from .services.llm import call_model
from .state_manager import StateManager


TASK_GRAPH_SCHEMA_HINT = """{
  "graph_id": "string",
  "user_goal": "string",
  "nodes": [
    {
      "id": "file_001",
      "title": "Create backend API server",
      "description": "Create the main FastAPI application with routes for ...",
      "worker_type": "backend",
      "model_tier": "worker",
      "depends_on": [],
      "inputs_schema": {},
      "outputs_schema": {"filename": "app/main.py", "content": "source code"}
    },
    {
      "id": "file_002",
      "title": "Create data models",
      "description": "Create pydantic models for ...",
      "worker_type": "backend",
      "model_tier": "worker",
      "depends_on": ["file_001"],
      "inputs_schema": {},
      "outputs_schema": {"filename": "app/models.py", "content": "source code"}
    },
    {
      "id": "file_003",
      "title": "Create dashboard page",
      "description": "Create the main React dashboard component ...",
      "worker_type": "frontend",
      "model_tier": "worker",
      "depends_on": ["file_001"],
      "inputs_schema": {},
      "outputs_schema": {"filename": "pages/Dashboard.tsx", "content": "source code"}
    },
    {
      "id": "verify_001",
      "title": "Verify all generated files",
      "description": "Validate all generated artifacts for correctness",
      "worker_type": "verifier",
      "model_tier": "verifier",
      "depends_on": ["file_001", "file_002", "file_003"],
      "inputs_schema": {},
      "outputs_schema": {"status": "PASS|FAIL", "issues": ["string"]}
    }
  ]
}"""


class ArchitectAgent:
    """
    Two-phase architect:
      1. Reasoning — thinks about architecture, data flow, API contracts
      2. Task graph — translates reasoning into a structured file plan

    The reasoning is stored in state and fed to every worker so they
    understand how their file fits into the larger system.
    """

    def __init__(self, *, state: StateManager) -> None:
        self._state = state

    async def run(self, *, user_request: str) -> tuple[TaskGraph, str, str, str]:
        """Returns (task_graph, plan_md, contracts_md, architecture_reasoning)."""
        # Phase 1: Architecture reasoning.
        reasoning = await self._generate_reasoning(user_request)

        # Phase 2: Task graph (informed by reasoning).
        task_graph = await self._build_task_graph(user_request, reasoning)

        plan_md = self._state.create_implementation_plan(
            user_request=user_request, task_graph=task_graph, architecture=reasoning
        )
        contracts_md = self._state.create_system_contracts(task_graph=task_graph)
        return task_graph, plan_md, contracts_md, reasoning

    async def _generate_reasoning(self, user_request: str) -> str:
        """Phase 1: The architect reasons about how the project fits together."""
        prompt = (
            f"The user wants to build: {user_request}\n\n"
            "As a senior software architect, reason through the following:\n\n"
            "1. **Architecture Overview**: What's the high-level architecture? (e.g. FastAPI backend + React frontend)\n"
            "2. **Data Model**: What are the core entities/models? What fields do they have?\n"
            "3. **API Design**: What endpoints does the backend expose? What does each return?\n"
            "4. **Frontend-Backend Contract**: How does the frontend call the backend? What types are shared?\n"
            "5. **File Structure**: What files are needed and how do they depend on each other?\n"
            "6. **Key Decisions**: Any important architectural choices (state management, auth, etc.)\n\n"
            "Be specific and concrete — include actual model names, endpoint paths, field names.\n"
            "This reasoning will be given to each code worker so they understand the full picture.\n\n"
            "Write your reasoning as clear, structured markdown. Do NOT return JSON."
        )
        try:
            result = await call_model("architect", prompt)
            return result.text.strip()
        except Exception:
            return self._fallback_reasoning(user_request)

    async def _build_task_graph(self, user_request: str, reasoning: str) -> TaskGraph:
        """Phase 2: Convert reasoning into a structured task graph."""
        prompt = (
            "Based on this architecture reasoning, create a task graph.\n\n"
            f"## Architecture Reasoning\n{reasoning}\n\n"
            f"## User Request\n{user_request}\n\n"
            "Rules:\n"
            "- Each node = ONE file to generate.\n"
            "- id: file_001, file_002, etc.\n"
            "- worker_type: 'backend' for .py, 'frontend' for .tsx/.ts/.css, 'file' for configs.\n"
            "- model_tier: 'worker' for all file tasks.\n"
            "- outputs_schema.filename: the target file path.\n"
            "- depends_on: which files must exist first (e.g. models before routes).\n"
            "- description: Be VERY specific — mention exact class names, function names, "
            "imports from other files. The description is all the worker sees.\n"
            "- ONE final verifier node (worker_type='verifier', model_tier='verifier').\n"
            "- 3-8 file tasks. Keep it practical.\n\n"
            "Return ONLY valid JSON."
        )
        try:
            result = await call_model(
                "architect", prompt, json_schema_hint=TASK_GRAPH_SCHEMA_HINT
            )
            graph = TaskGraph.model_validate(safe_json_loads(result.text))
            return self._normalize(graph, user_request)
        except Exception:
            return self._fallback_graph(user_request)

    def _normalize(self, graph: TaskGraph, user_request: str) -> TaskGraph:
        """Ensure the graph has at least one file task and one verifier."""
        file_tasks = [n for n in graph.nodes if n.worker_type != WorkerType.verifier]
        verifier_tasks = [n for n in graph.nodes if n.worker_type == WorkerType.verifier]

        if not file_tasks:
            return self._fallback_graph(user_request)

        for t in file_tasks:
            t.model_tier = ModelTier.worker

        if not verifier_tasks:
            verifier_tasks = [
                TaskNode(
                    id="verify_001",
                    title="Verify all generated files",
                    description="Validate all generated artifacts for correctness and consistency.",
                    worker_type=WorkerType.verifier,
                    model_tier=ModelTier.verifier,
                    depends_on=[t.id for t in file_tasks],
                )
            ]
        else:
            v = verifier_tasks[0]
            v.model_tier = ModelTier.verifier
            v.depends_on = [t.id for t in file_tasks]
            verifier_tasks = [v]

        graph.user_goal = user_request
        graph.graph_id = graph.graph_id or f"tg_{uuid.uuid4().hex[:8]}"
        graph.nodes = file_tasks + verifier_tasks
        return graph

    def _fallback_graph(self, user_request: str) -> TaskGraph:
        graph_id = f"tg_{uuid.uuid4().hex[:8]}"
        return TaskGraph(
            graph_id=graph_id,
            user_goal=user_request,
            nodes=[
                TaskNode(
                    id="file_001",
                    title="Create main application file",
                    description=f"Create the primary application file for: {user_request}",
                    worker_type=WorkerType.backend,
                    model_tier=ModelTier.worker,
                    inputs_schema={},
                    outputs_schema={"filename": "main.py", "content": "source code"},
                ),
                TaskNode(
                    id="file_002",
                    title="Create frontend page",
                    description=f"Create the main UI component for: {user_request}",
                    worker_type=WorkerType.frontend,
                    model_tier=ModelTier.worker,
                    depends_on=["file_001"],
                    inputs_schema={},
                    outputs_schema={"filename": "App.tsx", "content": "source code"},
                ),
                TaskNode(
                    id="verify_001",
                    title="Verify all generated files",
                    description="Validate all generated artifacts.",
                    worker_type=WorkerType.verifier,
                    model_tier=ModelTier.verifier,
                    depends_on=["file_001", "file_002"],
                ),
            ],
        )

    def _fallback_reasoning(self, user_request: str) -> str:
        return (
            f"# Architecture for: {user_request}\n\n"
            "## Overview\n"
            "FastAPI backend with a React/Next.js frontend.\n\n"
            "## Data Flow\n"
            "Frontend fetches data from backend API endpoints via fetch().\n"
            "Backend returns Pydantic models as JSON responses.\n\n"
            "## Files Needed\n"
            "- Backend: main.py (FastAPI app with routes)\n"
            "- Frontend: App.tsx (main UI component)\n"
        )

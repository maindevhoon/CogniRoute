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
    Multi-file architect.

    Turns a user request into a task graph where each non-verifier node
    represents one file to generate.  The architect uses the 32B model
    to plan the project structure, then the orchestration loop dispatches
    each file task to a 7B worker.
    """

    def __init__(self, *, state: StateManager) -> None:
        self._state = state

    async def run(self, *, user_request: str) -> tuple[TaskGraph, str, str]:
        task_graph = await self._build_task_graph(user_request)
        plan_md = self._state.create_implementation_plan(
            user_request=user_request, task_graph=task_graph
        )
        contracts_md = self._state.create_system_contracts(task_graph=task_graph)
        return task_graph, plan_md, contracts_md

    async def _build_task_graph(self, user_request: str) -> TaskGraph:
        prompt = (
            "You are planning a software project.  The user wants:\n\n"
            f"{user_request}\n\n"
            "Create a task graph where EACH node represents ONE file to generate.\n"
            "Rules:\n"
            "- Each file task must have a unique id like file_001, file_002, etc.\n"
            "- Set worker_type to 'backend' for Python/.py files, 'frontend' for .tsx/.ts/.jsx/.css files, "
            "'file' for configs/misc.\n"
            "- Set model_tier to 'worker' for all file tasks.\n"
            "- Set outputs_schema.filename to the target file path (e.g. 'app/main.py').\n"
            "- Use depends_on to express which files need to exist before this file can be written "
            "(e.g. models before routes).\n"
            "- Add exactly ONE final verifier node (worker_type='verifier', model_tier='verifier') "
            "that depends on ALL file tasks.\n"
            "- Keep the project small and practical (3-8 file tasks). Do not over-engineer.\n"
            "- Give clear, specific descriptions of what each file should contain.\n\n"
            "Return ONLY valid JSON matching the schema."
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

        # Ensure all file tasks use worker tier.
        for t in file_tasks:
            t.model_tier = ModelTier.worker

        # Ensure exactly one verifier at the end.
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
        """Deterministic fallback when the LLM call fails."""
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

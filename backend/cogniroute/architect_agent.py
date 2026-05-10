from __future__ import annotations

import uuid

from .llm import safe_json_loads
from .schemas import ModelTier, TaskGraph, TaskNode, WorkerType
from .services.llm import call_model
from .state_manager import StateManager


TASK_GRAPH_SCHEMA_HINT = """{
  "graph_id": "string",
  "user_goal": "string",
  "nodes": [{
    "id": "frontend_001",
    "title": "string",
    "description": "string",
    "worker_type": "frontend",
    "model_tier": "worker",
    "depends_on": [],
    "inputs_schema": {"key": "any"},
    "outputs_schema": {"key": "any"}
  }, {
    "id": "verify_001",
    "title": "string",
    "description": "string",
    "worker_type": "verifier",
    "model_tier": "verifier",
    "depends_on": ["frontend_001"],
    "inputs_schema": {"key": "any"},
    "outputs_schema": {"key": "any"}
  }]
}"""


class ArchitectAgent:
    """
    First-loop architect.

    It turns a user request into markdown state, contracts, and one structured
    task graph. The MVP keeps this deterministic so the orchestration behavior
    is stable even when the model endpoint is unavailable.
    """

    def __init__(self, *, state: StateManager) -> None:
        self._state = state

    async def run(self, *, user_request: str) -> tuple[TaskGraph, str, str]:
        task_graph = await self._build_task_graph_with_fallback(user_request)
        plan_md = self._state.create_implementation_plan(user_request=user_request, task_graph=task_graph)
        contracts_md = self._state.create_system_contracts(task_graph=task_graph)
        return task_graph, plan_md, contracts_md

    async def _build_task_graph_with_fallback(self, user_request: str) -> TaskGraph:
        prompt = (
            "Create the first CogniRoute MVP task graph for this user request.\n"
            "Rules: exactly one frontend worker task and one verifier task, sequential only, "
            "no queues, no parallelism, no replanning.\n\n"
            f"User request:\n{user_request}"
        )
        try:
            result = await call_model("architect", prompt, json_schema_hint=TASK_GRAPH_SCHEMA_HINT)
            graph = TaskGraph.model_validate(safe_json_loads(result.text))
            return self._normalize_graph(graph, user_request=user_request)
        except Exception:
            return self._build_task_graph(user_request)

    def _normalize_graph(self, graph: TaskGraph, *, user_request: str) -> TaskGraph:
        frontend = next((n for n in graph.nodes if n.worker_type == WorkerType.frontend), None)
        verifier = next((n for n in graph.nodes if n.worker_type == WorkerType.verifier), None)
        if frontend is None or verifier is None:
            return self._build_task_graph(user_request)
        frontend.id = "frontend_001"
        frontend.worker_type = WorkerType.frontend
        frontend.model_tier = ModelTier.worker
        frontend.depends_on = []
        verifier.id = "verify_001"
        verifier.worker_type = WorkerType.verifier
        verifier.model_tier = ModelTier.verifier
        verifier.depends_on = [frontend.id]
        return TaskGraph(graph_id=graph.graph_id or f"tg_{uuid.uuid4().hex[:8]}", user_goal=user_request, nodes=[frontend, verifier])

    def _build_task_graph(self, user_request: str) -> TaskGraph:
        graph_id = f"tg_{uuid.uuid4().hex[:8]}"
        frontend_task = TaskNode(
            id="frontend_001",
            title="Generate scoped frontend artifact",
            description=(
                "Create one frontend artifact that represents the requested UI surface. "
                "Return filename and content only; do not inspect the repository."
            ),
            worker_type=WorkerType.frontend,
            model_tier=ModelTier.worker,
            inputs_schema={
                "user_goal": "string",
                "plan_section_markdown": "Frontend checklist section only",
                "contracts": "Frontend artifact contract only",
            },
            outputs_schema={
                "task_id": "string",
                "status": "completed|failed",
                "artifact": {"filename": "string", "content": "string"},
            },
        )
        verifier_task = TaskNode(
            id="verify_001",
            title="Validate frontend artifact against contracts",
            description="Check the completed frontend artifact and checklist state once.",
            worker_type=WorkerType.verifier,
            model_tier=ModelTier.verifier,
            depends_on=[frontend_task.id],
            inputs_schema={"artifact": "WorkerResult", "contracts": "system_contracts.md"},
            outputs_schema={"status": "PASS|FAIL", "issues": ["string"]},
        )
        return TaskGraph(graph_id=graph_id, user_goal=user_request, nodes=[frontend_task, verifier_task])

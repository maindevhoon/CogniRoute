from __future__ import annotations

import uuid

from ..llm import LlmClient, LlmRole, safe_json_loads
from ..prompts.architect import ARCHITECT_SYSTEM_PROMPT, ARCHITECT_TASK_GRAPH_JSON_SCHEMA_HINT
from ..schemas import ModelTier, TaskGraph, TaskNode, WorkerType
from ..services.model_router import ModelRouter
from ..telemetry.tracing import token_estimate


class ArchitectAgent:
    """
    Architect Agent.

    Input: user request (string)
    Output: structured TaskGraph (JSON-serializable via Pydantic)
    """

    def __init__(self, *, llm: LlmClient, router: ModelRouter) -> None:
        self._llm = llm
        self._router = router

    async def plan(self, *, user_request: str) -> tuple[TaskGraph, dict]:
        """
        Returns (task_graph, llm_meta).

        We return meta separately so orchestration can record telemetry without
        coupling the schema to a specific provider.
        """

        if not self._llm.enabled():
            return self._mock_plan(user_request), {"mode": "mock"}

        call = self._router.build_call(
            role=LlmRole.architect,
            user_prompt=f"User request:\n{user_request}\n\nCreate an MVP task graph for sequential execution.",
            json_schema_hint=ARCHITECT_TASK_GRAPH_JSON_SCHEMA_HINT,
        )

        # Override system prompt here for readability: router provides defaults,
        # but the architect prompt is central to the demo.
        call = call.__class__(
            role=call.role,
            user_prompt=call.user_prompt,
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            model=call.model,
            temperature=call.temperature,
            json_schema_hint=call.json_schema_hint,
        )

        res = await self._llm.call_model(call=call)
        graph = TaskGraph.model_validate(safe_json_loads(res.text))

        meta = dict(res.meta)
        meta["token_estimate_in"] = token_estimate(call.user_prompt) + token_estimate(call.system_prompt)
        meta["token_estimate_out"] = token_estimate(res.text)
        return graph, meta

    def _mock_plan(self, user_request: str) -> TaskGraph:
        graph_id = f"tg_{uuid.uuid4().hex[:8]}"
        return TaskGraph(
            graph_id=graph_id,
            user_goal=user_request,
            nodes=[
                TaskNode(
                    id="t1",
                    title="Plan API contracts",
                    description="Define the minimal contracts for orchestration run + telemetry.",
                    worker_type=WorkerType.backend,
                    model_tier=ModelTier.architect,
                    inputs_schema={"user_request": "string"},
                    outputs_schema={"contracts": "object"},
                ),
                TaskNode(
                    id="t2",
                    title="Implement worker stubs",
                    description="Create worker stubs that accept scoped context and return artifacts.",
                    worker_type=WorkerType.backend,
                    model_tier=ModelTier.worker,
                    depends_on=["t1"],
                    inputs_schema={"task_def": "TaskNode", "scoped_context": "object"},
                    outputs_schema={"artifacts": "object"},
                ),
                TaskNode(
                    id="t3",
                    title="Verifier checkpoint",
                    description="Validate plan consistency and execution statuses (single pass).",
                    worker_type=WorkerType.verifier,
                    model_tier=ModelTier.verifier,
                    depends_on=["t2"],
                    inputs_schema={"plan": "TaskGraph", "execution": "dict"},
                    outputs_schema={"report": "object"},
                ),
            ],
        )


from __future__ import annotations

import time
import uuid

from .agents.base import ScopedContext
from .architect_agent import ArchitectAgent
from .frontend_worker import FrontendWorker
from .schemas import ModelTier, NodeExecution, OrchestrationRun, TaskStatus, TraceRole, WorkerType
from .state_manager import StateManager
from .telemetry.tracing import now_ms, span_end, span_start, trace_emit
from .verifier_agent import VerifierAgent


class CognitiveOrchestrationLoop:
    """
    First working CogniRoute loop:
    user -> architect -> markdown state -> one frontend worker -> verifier -> state.
    """

    def __init__(self, *, state: StateManager | None = None) -> None:
        self._state = state or StateManager()
        self._architect = ArchitectAgent(state=self._state)
        self._frontend_worker = FrontendWorker()
        self._verifier = VerifierAgent()

    async def run(self, *, prompt: str) -> OrchestrationRun:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        spans = []
        trace = []
        routing_log: list[dict] = []

        trace_emit(trace, role=TraceRole.user, title="User request received", detail=prompt)

        a_span = span_start(
            spans,
            name="architect.generate_state",
            role="architect",
            worker_type=None,
            model_tier=ModelTier.architect,
            model=None,
        )
        started = time.perf_counter()
        task_graph, plan_md, contracts_md = await self._architect.run(user_request=prompt)
        span_end(
            spans,
            a_span,
            latency_ms=int((time.perf_counter() - started) * 1000),
            meta={"graph_id": task_graph.graph_id, "markdown_state": True},
        )
        trace_emit(
            trace,
            role=TraceRole.architect,
            title="Markdown state generated",
            detail="Created implementation_plan.md, system_contracts.md, and a structured task graph.",
            meta={"graph_id": task_graph.graph_id},
        )

        execution = {node.id: NodeExecution(node_id=node.id) for node in task_graph.nodes}
        frontend_task = next(node for node in task_graph.nodes if node.worker_type == WorkerType.frontend)

        routing_log.append(
            {
                "node_id": frontend_task.id,
                "chosen_worker": WorkerType.frontend.value,
                "reason": "first_loop_frontend_task",
            }
        )
        trace_emit(
            trace,
            role=TraceRole.system,
            title="Scoped worker dispatch",
            detail="Dispatching exactly one frontend task with frontend plan section and contracts only.",
            node_id=frontend_task.id,
            worker_type=WorkerType.frontend,
            model_tier=frontend_task.model_tier,
        )

        frontend_execution = execution[frontend_task.id]
        frontend_execution.status = TaskStatus.running
        frontend_execution.started_at_ms = now_ms()

        w_span = span_start(
            spans,
            name="worker.frontend",
            role="worker",
            worker_type=WorkerType.frontend,
            model_tier=ModelTier.worker,
            model=None,
            meta={"node_id": frontend_task.id},
        )
        worker_started = time.perf_counter()
        worker_result = await self._frontend_worker.run(
            ctx=ScopedContext(
                run_id=run_id,
                user_goal=prompt,
                node=frontend_task,
                upstream_artifacts={},
                plan_section_markdown=_extract_section(plan_md, "Frontend"),
                allowed_plan_item_keys=set(),
            ),
            contracts_markdown=contracts_md,
        )
        self._state.mark_task(task_id=frontend_task.id, status=TaskStatus.succeeded)
        frontend_execution.status = TaskStatus.succeeded
        frontend_execution.ended_at_ms = now_ms()
        frontend_execution.artifacts = worker_result.model_dump()
        span_end(
            spans,
            w_span,
            latency_ms=int((time.perf_counter() - worker_started) * 1000),
            meta={"artifact_filename": worker_result.artifact.filename},
        )
        trace_emit(
            trace,
            role=TraceRole.worker,
            title="Frontend artifact generated",
            detail=f"Generated {worker_result.artifact.filename}.",
            node_id=frontend_task.id,
            worker_type=WorkerType.frontend,
            model_tier=ModelTier.worker,
            meta={"task_id": worker_result.task_id, "status": worker_result.status},
        )

        verifier_task = next(node for node in task_graph.nodes if node.worker_type == WorkerType.verifier)
        verifier_execution = execution[verifier_task.id]
        verifier_execution.status = TaskStatus.running
        verifier_execution.started_at_ms = now_ms()

        v_span = span_start(
            spans,
            name="verifier.validate",
            role="verifier",
            worker_type=WorkerType.verifier,
            model_tier=ModelTier.verifier,
            model=None,
            meta={"node_id": verifier_task.id},
        )
        verifier_report = await self._verifier.run(
            task_graph=task_graph,
            worker_result=worker_result,
            plan_markdown=self._state.read_plan_markdown(),
            contracts_markdown=self._state.read_contracts_markdown(),
        )
        if verifier_report.status == "PASS":
            self._state.mark_task(task_id=verifier_task.id, status=TaskStatus.succeeded)
            verifier_execution.status = TaskStatus.succeeded
        else:
            verifier_execution.status = TaskStatus.failed
            verifier_execution.error = "; ".join(verifier_report.issues)
        verifier_execution.ended_at_ms = now_ms()
        verifier_execution.artifacts = {"verifier_report": verifier_report.model_dump()}
        span_end(
            spans,
            v_span,
            status="ok" if verifier_report.status == "PASS" else "error",
            meta=verifier_report.model_dump(),
        )
        trace_emit(
            trace,
            role=TraceRole.verifier,
            title=f"Verifier {verifier_report.status}",
            detail="Validated completed checklist items and artifact contract.",
            node_id=verifier_task.id,
            worker_type=WorkerType.verifier,
            model_tier=ModelTier.verifier,
            meta=verifier_report.model_dump(),
        )

        self._state.update_telemetry(
            {
                "run_id": run_id,
                "graph_id": task_graph.graph_id,
                "frontend_task": frontend_task.id,
                "verifier_status": verifier_report.status,
            }
        )

        return OrchestrationRun(
            run_id=run_id,
            prompt=prompt,
            plan=task_graph,
            execution=execution,
            spans=spans,
            trace=trace,
            routing_log=routing_log,
            verifier_report=verifier_report.model_dump(),
            plan_markdown=self._state.read_plan_markdown(),
            contracts_markdown=self._state.read_contracts_markdown(),
        )


async def run_generate(prompt: str) -> OrchestrationRun:
    return await CognitiveOrchestrationLoop().run(prompt=prompt)


def _extract_section(markdown: str, title: str) -> str:
    lines = markdown.splitlines()
    out: list[str] = []
    active = False
    for line in lines:
        if line.startswith("## "):
            if active:
                break
            active = line[3:].strip() == title
        if active:
            out.append(line)
    return "\n".join(out).strip() + "\n"

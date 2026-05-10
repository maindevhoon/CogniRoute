from __future__ import annotations

import time
import uuid
from typing import Any

from ..agents.architect import ArchitectAgent
from ..agents.base import PlanUpdate, ScopedContext
from ..agents.verifier import VerifierAgent
from ..schemas import ModelTier, NodeExecution, OrchestrationRun, TaskGraph, TaskNode, TaskStatus, WorkerType
from ..state.plan import ChecklistStatus, apply_checklist_updates, parse_implementation_plan, scoped_keys_for_items
from ..state.store import StateStore
from ..telemetry.tracing import now_ms, span_end, span_start, trace_emit
from ..schemas.telemetry import TraceRole


class SequentialStatefulRuntime:
    """
    Sequential orchestration with shared markdown-based state.

    This is intentionally simple:
    - single writer (the orchestrator) updates `state/implementation_plan.md`
    - workers receive only: scoped node + scoped plan section text + allowed keys
    - verifier performs a single checkpoint (no loops, no retries)
    """

    def __init__(
        self,
        *,
        store: StateStore,
        architect: ArchitectAgent,
        workers: dict[WorkerType, Any],
        verifier: VerifierAgent,
    ) -> None:
        self._store = store
        self._architect = architect
        self._workers = workers
        self._verifier = verifier

    async def run(self, *, prompt: str) -> OrchestrationRun:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        spans = []
        trace = []
        routing_log: list[dict[str, Any]] = []

        plan_md = self._store.read_plan_markdown()
        contracts_md = self._store.read_contracts_markdown()

        trace_emit(trace, role=TraceRole.user, title="User request received", detail=prompt)
        trace_emit(trace, role=TraceRole.system, title="Loaded shared state", detail="Loaded plan + contracts markdown.")

        # Architect planning step
        span_id = span_start(spans, name="architect.plan", role="architect", worker_type=None, model_tier=ModelTier.architect, model=None)
        task_graph, architect_meta = await self._architect.plan(user_request=prompt)
        span_end(
            spans,
            span_id,
            meta={"architect_meta": architect_meta, "contracts_len": len(contracts_md)},
            latency_ms=architect_meta.get("latency_ms"),
            token_estimate_in=architect_meta.get("token_estimate_in"),
            token_estimate_out=architect_meta.get("token_estimate_out"),
        )
        trace_emit(
            trace,
            role=TraceRole.architect,
            title="Task graph planned",
            detail=f"Planned {len(task_graph.nodes)} nodes (sequential).",
            meta={"graph_id": task_graph.graph_id, **architect_meta},
        )

        execution: dict[str, NodeExecution] = {n.id: NodeExecution(node_id=n.id) for n in task_graph.nodes}

        # Run non-verifier nodes sequentially with dependency honoring.
        await self._execute_sequential(
            run_id=run_id,
            user_goal=prompt,
            task_graph=task_graph,
            execution=execution,
            plan_md=plan_md,
            spans=spans,
            trace=trace,
            routing_log=routing_log,
        )

        # Verifier checkpoint (single pass)
        v_span = span_start(
            spans,
            name="verifier.checkpoint",
            role="verifier",
            worker_type=WorkerType.verifier,
            model_tier=ModelTier.verifier,
            model=None,
        )
        verifier_report = await self._verifier.checkpoint(
            user_goal=prompt,
            plan=task_graph,
            execution=execution,
            plan_markdown=self._store.read_plan_markdown(),
        )
        span_end(spans, v_span, status="ok" if verifier_report.get("ok") else "error", meta={"verifier_report": verifier_report})
        trace_emit(
            trace,
            role=TraceRole.verifier,
            title="Verifier checkpoint",
            detail="Validated checklist completion markers and dependency integrity.",
            meta=verifier_report,
        )

        return OrchestrationRun(
            run_id=run_id,
            prompt=prompt,
            plan=task_graph,
            execution=execution,
            spans=spans,
            trace=trace,
            routing_log=routing_log,
            verifier_report=verifier_report,
        )

    async def _execute_sequential(
        self,
        *,
        run_id: str,
        user_goal: str,
        task_graph: TaskGraph,
        execution: dict[str, NodeExecution],
        plan_md: str,
        spans: list,
        trace: list,
        routing_log: list[dict[str, Any]],
    ) -> None:
        remaining = {n.id: n for n in task_graph.nodes if n.worker_type != WorkerType.verifier}
        completed: set[str] = set()

        while remaining:
            progressed = False
            for node_id, node in list(remaining.items()):
                if all(dep in completed and execution[dep].status == TaskStatus.succeeded for dep in node.depends_on):
                    await self._run_node(
                        run_id=run_id,
                        user_goal=user_goal,
                        node=node,
                        execution=execution[node_id],
                        plan_md=plan_md,
                        spans=spans,
                        trace=trace,
                        routing_log=routing_log,
                    )
                    completed.add(node_id)
                    remaining.pop(node_id, None)
                    progressed = True
            if not progressed:
                for node_id, node in remaining.items():
                    execution[node_id].status = TaskStatus.failed
                    execution[node_id].error = f"Unresolvable dependencies: {node.depends_on}"
                return

    async def _run_node(
        self,
        *,
        run_id: str,
        user_goal: str,
        node: TaskNode,
        execution: NodeExecution,
        plan_md: str,
        spans: list,
        trace: list,
        routing_log: list[dict[str, Any]],
    ) -> None:
        worker_type = node.worker_type
        routing_log.append({"node_id": node.id, "chosen_worker": worker_type.value, "reason": "plan.worker_type"})
        trace_emit(
            trace,
            role=TraceRole.system,
            title="Capability routing",
            detail=f"Routed node '{node.title}' to worker={worker_type.value}.",
            node_id=node.id,
            worker_type=worker_type,
            model_tier=node.model_tier,
        )

        worker = self._workers.get(worker_type)
        execution.status = TaskStatus.running
        execution.started_at_ms = now_ms()

        if worker is None:
            execution.status = TaskStatus.failed
            execution.error = f"No worker registered for worker_type={worker_type.value}"
            execution.ended_at_ms = now_ms()
            return

        # Scope the plan to a single section based on worker type.
        plan = parse_implementation_plan(self._store.read_plan_markdown())
        section_name = worker_type.value.capitalize() if worker_type != WorkerType.verifier else "Verification"
        section_items = plan.items_in(section_name)
        allowed_keys = scoped_keys_for_items(section_items)
        section_md = self._extract_section_markdown(self._store.read_plan_markdown(), section_name)

        ctx = ScopedContext(
            run_id=run_id,
            user_goal=user_goal,
            node=node,
            upstream_artifacts={},  # Phase 1: only minimal upstream passing
            plan_section_markdown=section_md,
            allowed_plan_item_keys=allowed_keys,
        )

        span_id = span_start(
            spans,
            name=f"worker.{worker_type.value}",
            role="worker",
            worker_type=worker_type,
            model_tier=node.model_tier,
            model=None,
            meta={"node_id": node.id, "node_title": node.title},
        )
        started = time.perf_counter()
        artifacts, plan_update = await worker.run(ctx=ctx)
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        self._apply_plan_update(plan_update, allowed_keys=allowed_keys)

        execution.artifacts = artifacts
        execution.ended_at_ms = now_ms()
        execution.status = TaskStatus.succeeded

        span_end(spans, span_id, meta={"plan_update": plan_update.__dict__ if isinstance(plan_update, PlanUpdate) else plan_update}, latency_ms=elapsed_ms)
        trace_emit(
            trace,
            role=TraceRole.worker,
            title=f"Worker completed: {worker_type.value}",
            detail=f"Produced artifacts: {', '.join(artifacts.keys()) or 'none'}.",
            node_id=node.id,
            worker_type=worker_type,
            model_tier=node.model_tier,
            meta={"plan_update": plan_update.__dict__ if isinstance(plan_update, PlanUpdate) else plan_update},
        )

    def _apply_plan_update(self, update: Any, *, allowed_keys: set[str]) -> None:
        if update is None:
            return

        if isinstance(update, dict):
            checklist_updates_raw = update.get("checklist_updates", {}) or {}
        else:
            checklist_updates_raw = getattr(update, "checklist_updates", {}) or {}

        checklist_updates: dict[str, ChecklistStatus] = {}
        for k, v in checklist_updates_raw.items():
            if k not in allowed_keys:
                continue
            if str(v).lower() == "done":
                checklist_updates[k] = ChecklistStatus.done
            elif str(v).lower() == "todo":
                checklist_updates[k] = ChecklistStatus.todo

        if not checklist_updates:
            return

        md = self._store.read_plan_markdown()
        updated = apply_checklist_updates(md, updates=checklist_updates, allowed_keys=allowed_keys)
        self._store.write_plan_markdown(updated)

    @staticmethod
    def _extract_section_markdown(markdown: str, section_title: str) -> str:
        lines = markdown.splitlines()
        out: list[str] = []
        in_section = False
        for line in lines:
            if line.strip().startswith("## "):
                title = line.strip()[3:].strip()
                if title == section_title:
                    in_section = True
                    out.append(line)
                    continue
                if in_section:
                    break
            if in_section:
                out.append(line)
        return "\n".join(out).strip() + "\n"


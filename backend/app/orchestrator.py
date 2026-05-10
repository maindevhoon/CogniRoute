from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .llm import llm_client, safe_json_loads
from .schemas import (
    ModelTier,
    NodeExecution,
    OrchestrationRun,
    TaskGraph,
    TaskNode,
    TaskStatus,
    TelemetrySpan,
    TraceEvent,
    TraceRole,
    WorkerType,
)
from .settings import settings


def now_ms() -> int:
    return int(time.time() * 1000)


class OrchestratorState(TypedDict, total=False):
    prompt: str
    run_id: str
    plan: TaskGraph
    execution: dict[str, NodeExecution]
    spans: list[TelemetrySpan]
    trace: list[TraceEvent]
    routing_log: list[dict[str, Any]]
    verifier_report: dict[str, Any]


def span_start(state: OrchestratorState, *, name: str, worker_type: WorkerType | None, model_tier: ModelTier | None) -> str:
    span_id = str(uuid.uuid4())
    state.setdefault("spans", []).append(
        TelemetrySpan(
            span_id=span_id,
            name=name,
            worker_type=worker_type,
            model_tier=model_tier,
            started_at_ms=now_ms(),
        )
    )
    return span_id


def span_end(state: OrchestratorState, span_id: str, *, status: str = "ok", meta: dict[str, Any] | None = None) -> None:
    for s in state.get("spans", []):
        if s.span_id == span_id:
            s.ended_at_ms = now_ms()
            s.status = status  # type: ignore[assignment]
            if meta:
                s.meta.update(meta)
            return


def trace_emit(
    state: OrchestratorState,
    *,
    role: TraceRole,
    title: str,
    detail: str,
    node_id: str | None = None,
    worker_type: WorkerType | None = None,
    model_tier: ModelTier | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    state.setdefault("trace", []).append(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            at_ms=now_ms(),
            role=role,
            title=title,
            detail=detail,
            node_id=node_id,
            worker_type=worker_type,
            model_tier=model_tier,
            meta=meta or {},
        )
    )


def _mock_plan(prompt: str) -> TaskGraph:
    graph_id = f"tg_{uuid.uuid4().hex[:8]}"
    return TaskGraph(
        graph_id=graph_id,
        user_goal=prompt,
        nodes=[
            TaskNode(
                id="t1",
                title="Define API contracts",
                description="Define minimal backend API contracts for orchestration run + telemetry.",
                worker_type=WorkerType.backend,
                model_tier=ModelTier.architect,
                inputs_schema={"prompt": "string"},
                outputs_schema={"endpoints": "list"},
            ),
            TaskNode(
                id="t2",
                title="Implement orchestrator runtime",
                description="Implement task graph execution with capability routing and checkpointing.",
                worker_type=WorkerType.backend,
                model_tier=ModelTier.worker,
                depends_on=["t1"],
                inputs_schema={"task_graph": "TaskGraph"},
                outputs_schema={"run": "OrchestrationRun"},
            ),
            TaskNode(
                id="t3",
                title="Build observability UI",
                description="Render task graph + routing decisions + spans in React Flow.",
                worker_type=WorkerType.frontend,
                model_tier=ModelTier.worker,
                depends_on=["t1"],
                inputs_schema={"run": "OrchestrationRun"},
                outputs_schema={"ui": "Next.js page"},
            ),
            TaskNode(
                id="t4",
                title="Verifier checkpoint",
                description="Validate plan consistency, missing deps, and interface compatibility.",
                worker_type=WorkerType.verifier,
                model_tier=ModelTier.verifier,
                depends_on=["t2", "t3"],
                inputs_schema={"plan": "TaskGraph", "execution": "dict"},
                outputs_schema={"report": "dict"},
            ),
        ],
    )


async def architect_plan(state: OrchestratorState) -> OrchestratorState:
    span_id = span_start(state, name="architect.plan", worker_type=None, model_tier=ModelTier.architect)
    prompt = state["prompt"]
    trace_emit(state, role=TraceRole.user, title="User request received", detail=prompt)

    if not llm_client.enabled():
        plan = _mock_plan(prompt)
        state["plan"] = plan
        state["execution"] = {n.id: NodeExecution(node_id=n.id) for n in plan.nodes}
        trace_emit(
            state,
            role=TraceRole.architect,
            title="Planned task graph (mock)",
            detail=f"Generated {len(plan.nodes)} nodes with explicit worker types and dependencies.",
            model_tier=ModelTier.architect,
            meta={"graph_id": plan.graph_id},
        )
        span_end(state, span_id, meta={"mode": "mock"})
        return state

    system = (
        "You are the CogniRoute Architect. Produce a compact structured task graph JSON. "
        "Optimize for scoped workers and clear dependencies. Keep it MVP-simple."
    )
    json_schema_hint = """{
  "graph_id": "string",
  "user_goal": "string",
  "nodes": [{
    "id": "string",
    "title": "string",
    "description": "string",
    "worker_type": "frontend|backend|research|file|verifier",
    "model_tier": "architect|worker|verifier",
    "depends_on": ["string"],
    "inputs_schema": {"key": "any"},
    "outputs_schema": {"key": "any"}
  }]
}"""

    res = await llm_client.chat_json(
        model=settings.architect_model,
        system=system,
        user=f"User goal:\n{prompt}\n\nReturn a task graph for the MVP flow.",
        json_schema_hint=json_schema_hint,
    )
    plan = TaskGraph.model_validate(safe_json_loads(res.text))
    state["plan"] = plan
    state["execution"] = {n.id: NodeExecution(node_id=n.id) for n in plan.nodes}
    trace_emit(
        state,
        role=TraceRole.architect,
        title="Planned task graph",
        detail=f"Generated {len(plan.nodes)} nodes with explicit worker types and dependencies.",
        model_tier=ModelTier.architect,
        meta={"graph_id": plan.graph_id, "model": settings.architect_model, "usage": res.meta.get("usage", {})},
    )
    span_end(state, span_id, meta={"mode": "llm", **res.meta})
    return state


def _route(node: TaskNode) -> WorkerType:
    # Capability routing MVP: explicit in plan; could evolve into learned routing.
    return node.worker_type


async def _run_worker(state: OrchestratorState, node: TaskNode) -> None:
    worker_type = _route(node)
    state.setdefault("routing_log", []).append(
        {"node_id": node.id, "chosen_worker": worker_type.value, "reason": "plan.worker_type"}
    )
    trace_emit(
        state,
        role=TraceRole.system,
        title="Capability routing",
        detail=f"Routed node '{node.title}' to worker={worker_type.value} (reason=plan.worker_type).",
        node_id=node.id,
        worker_type=worker_type,
        model_tier=node.model_tier,
    )

    exec_rec = state["execution"][node.id]
    exec_rec.status = TaskStatus.running
    exec_rec.started_at_ms = now_ms()

    span_id = span_start(state, name=f"worker.{worker_type.value}", worker_type=worker_type, model_tier=node.model_tier)
    trace_emit(
        state,
        role=TraceRole.worker,
        title=f"Worker started: {worker_type.value}",
        detail=node.description,
        node_id=node.id,
        worker_type=worker_type,
        model_tier=node.model_tier,
    )

    # Deterministic mock artifacts for demo; replace with real generation later.
    if worker_type == WorkerType.frontend:
        exec_rec.artifacts = {
            "ui_notes": "React Flow graph renders nodes/edges; side panel shows telemetry and routing log."
        }
    elif worker_type == WorkerType.backend:
        exec_rec.artifacts = {"backend_notes": "FastAPI exposes /run; LangGraph executes plan -> workers -> verifier."}
    elif worker_type == WorkerType.research:
        exec_rec.artifacts = {"research_notes": "No external browsing in MVP mock mode."}
    elif worker_type == WorkerType.file:
        exec_rec.artifacts = {"file_notes": "No repository scanning in MVP mock mode."}
    elif worker_type == WorkerType.verifier:
        exec_rec.artifacts = {"verifier_notes": "Verifier runs in dedicated verifier step, not here."}

    exec_rec.ended_at_ms = now_ms()
    exec_rec.status = TaskStatus.succeeded
    trace_emit(
        state,
        role=TraceRole.worker,
        title=f"Worker completed: {worker_type.value}",
        detail=f"Produced artifacts: {', '.join(exec_rec.artifacts.keys()) or 'none'}.",
        node_id=node.id,
        worker_type=worker_type,
        model_tier=node.model_tier,
        meta={"artifacts": exec_rec.artifacts},
    )
    span_end(state, span_id)


async def execute_tasks(state: OrchestratorState) -> OrchestratorState:
    plan = state["plan"]
    exec_map = state["execution"]

    # Sequential execution (MVP). Honors depends_on.
    remaining = {n.id: n for n in plan.nodes if n.worker_type != WorkerType.verifier}
    completed: set[str] = set()

    while remaining:
        progressed = False
        for node_id, node in list(remaining.items()):
            if all(dep in completed and exec_map[dep].status == TaskStatus.succeeded for dep in node.depends_on):
                await _run_worker(state, node)
                completed.add(node_id)
                remaining.pop(node_id, None)
                progressed = True
        if not progressed:
            # Dependency cycle or missing deps.
            for node_id, node in remaining.items():
                exec_map[node_id].status = TaskStatus.failed
                exec_map[node_id].error = f"Unresolvable dependencies: {node.depends_on}"
            break

    return state


async def verifier_checkpoint(state: OrchestratorState) -> OrchestratorState:
    span_id = span_start(state, name="verifier.checkpoint", worker_type=WorkerType.verifier, model_tier=ModelTier.verifier)
    plan = state["plan"]
    execution = state["execution"]

    missing_deps: list[dict[str, Any]] = []
    node_ids = {n.id for n in plan.nodes}
    for n in plan.nodes:
        for dep in n.depends_on:
            if dep not in node_ids:
                missing_deps.append({"node": n.id, "missing_dep": dep})

    failed = [nid for nid, ex in execution.items() if ex.status == TaskStatus.failed]
    report = {
        "ok": (len(missing_deps) == 0 and len(failed) == 0),
        "missing_deps": missing_deps,
        "failed_nodes": failed,
        "notes": "MVP verifier checks dependency integrity + execution failures.",
    }

    state["verifier_report"] = report
    trace_emit(
        state,
        role=TraceRole.verifier,
        title="Verifier checkpoint",
        detail="Validated dependency integrity and checked for failed nodes.",
        worker_type=WorkerType.verifier,
        model_tier=ModelTier.verifier,
        meta=report,
    )

    # Reflect verifier work on any explicit verifier nodes in the plan (so the UI shows checkpoint completion).
    for n in plan.nodes:
        if n.worker_type == WorkerType.verifier:
            ex = execution.get(n.id)
            if ex is None:
                ex = NodeExecution(node_id=n.id)
                execution[n.id] = ex
            ex.status = TaskStatus.succeeded if report["ok"] else TaskStatus.failed
            ex.started_at_ms = ex.started_at_ms or now_ms()
            ex.ended_at_ms = now_ms()
            ex.artifacts = {"verifier_report": report}
            ex.error = None if report["ok"] else "Verifier checkpoint found issues"

    span_end(state, span_id, status="ok" if report["ok"] else "error")
    return state


def build_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("architect_plan", architect_plan)
    g.add_node("execute_tasks", execute_tasks)
    g.add_node("verifier", verifier_checkpoint)

    g.set_entry_point("architect_plan")
    g.add_edge("architect_plan", "execute_tasks")
    g.add_edge("execute_tasks", "verifier")
    g.add_edge("verifier", END)
    return g.compile()


graph = build_graph()


async def run_orchestration(prompt: str) -> OrchestrationRun:
    state: OrchestratorState = {
        "prompt": prompt,
        "run_id": f"run_{uuid.uuid4().hex[:8]}",
        "spans": [],
        "trace": [],
        "routing_log": [],
        "verifier_report": {},
    }
    final = await graph.ainvoke(state)
    plan = final["plan"]
    execution = final["execution"]
    return OrchestrationRun(
        run_id=final["run_id"],
        prompt=prompt,
        plan=plan,
        execution=execution,
        spans=final.get("spans", []),
        trace=final.get("trace", []),
        routing_log=final.get("routing_log", []),
        verifier_report=final.get("verifier_report", {}),
    )


from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, AsyncIterator, Callable, Coroutine, Optional

from .agents.base import ScopedContext
from .architect_agent import ArchitectAgent
from .code_worker import CodeWorker
from .fixer_agent import FixerAgent
from .schemas import (
    ModelTier,
    NodeExecution,
    OrchestrationRun,
    TaskNode,
    TaskStatus,
    TraceRole,
    WorkerResult,
    WorkerType,
)
from .config import settings
from .services.simulator import run_generate_simulation, run_generate_stream_simulation
from .state_manager import StateManager
from .telemetry.tracing import now_ms, span_end, span_start, trace_emit
from .verifier_agent import VerifierAgent

MAX_RETRIES = 9

# Type for the streaming event callback.
EventCallback = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class CognitiveOrchestrationLoop:
    """
    Multi-file CogniRoute orchestration loop with optional SSE streaming.

    Flow:
      user prompt
        → architect (32B) plans N file tasks
        → for each file task (sequential, dependency-aware):
            → worker (7B) generates file code
            → verifier (32B) checks quality
            → if FAIL: re-prompt worker with issues (up to MAX_RETRIES)
        → final cross-file verification
        → return all file artifacts + full trace
    """

    def __init__(
        self,
        *,
        state: StateManager | None = None,
        on_event: EventCallback | None = None,
    ) -> None:
        self._state = state or StateManager()
        self._architect = ArchitectAgent(state=self._state)
        self._worker = CodeWorker()
        self._verifier = VerifierAgent()
        self._fixer = FixerAgent()
        self._on_event = on_event

    async def _emit(self, event: dict[str, Any]) -> None:
        """Send a streaming event if a callback is registered."""
        if self._on_event:
            await self._on_event(event)

    async def run(self, *, prompt: str) -> OrchestrationRun:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        spans: list = []
        trace: list = []
        routing_log: list[dict] = []

        trace_emit(trace, role=TraceRole.user, title="User request received", detail=prompt)

        await self._emit({"type": "status", "message": "Architect is analyzing the project..."})

        # ── Step 1: Architect reasons + plans ─────────────────────────
        a_span = span_start(
            spans,
            name="architect.plan",
            role="architect",
            worker_type=None,
            model_tier=ModelTier.architect,
            model=None,
        )
        started = time.perf_counter()
        task_graph, plan_md, contracts_md, architecture = await self._architect.run(user_request=prompt)
        span_end(
            spans,
            a_span,
            latency_ms=int((time.perf_counter() - started) * 1000),
            meta={"graph_id": task_graph.graph_id, "num_files": len([n for n in task_graph.nodes if n.worker_type != WorkerType.verifier])},
        )

        file_tasks = [n for n in task_graph.nodes if n.worker_type != WorkerType.verifier]

        # Stream the architecture reasoning to frontend.
        trace_emit(
            trace,
            role=TraceRole.architect,
            title="Architecture reasoning",
            detail=architecture,
            meta={"graph_id": task_graph.graph_id},
        )
        await self._emit({
            "type": "reasoning",
            "content": architecture,
        })

        trace_emit(
            trace,
            role=TraceRole.architect,
            title=f"Planned {len(file_tasks)} file tasks",
            detail=(
                "Files to generate:\n"
                + "\n".join(f"  - {n.id}: {n.outputs_schema.get('filename', n.title)}" for n in file_tasks)
            ),
            meta={"graph_id": task_graph.graph_id},
        )

        # Send the plan to the frontend.
        await self._emit({
            "type": "plan",
            "graph_id": task_graph.graph_id,
            "files": [
                {
                    "node_id": n.id,
                    "title": n.title,
                    "filename": n.outputs_schema.get("filename", n.title),
                    "worker_type": n.worker_type.value,
                    "status": "pending",
                }
                for n in file_tasks
            ],
        })

        # ── Step 2: Execute file tasks in dependency order ───────────
        execution = {node.id: NodeExecution(node_id=node.id) for node in task_graph.nodes}
        all_results: dict[str, WorkerResult] = {}
        generated_files: dict[str, str] = {}  # filename -> content

        remaining = {n.id: n for n in file_tasks}
        completed: set[str] = set()

        while remaining:
            progressed = False
            for node_id, node in list(remaining.items()):
                deps_met = all(
                    dep in completed for dep in node.depends_on
                    if dep in {n.id for n in file_tasks}
                )
                if not deps_met:
                    continue

                # Route the task.
                routing_log.append({
                    "node_id": node.id,
                    "chosen_worker": node.worker_type.value,
                    "reason": "plan.worker_type",
                })
                trace_emit(
                    trace,
                    role=TraceRole.system,
                    title=f"Dispatching: {node.title}",
                    detail=f"Routing {node.id} to {node.worker_type.value} worker.",
                    node_id=node.id,
                    worker_type=node.worker_type,
                    model_tier=node.model_tier,
                )

                target_filename = node.outputs_schema.get("filename", node.title)
                await self._emit({
                    "type": "file_start",
                    "node_id": node.id,
                    "filename": target_filename,
                    "title": node.title,
                })

                # Build dependency-filtered context: only files from tasks
                # this node depends_on, not all generated files.
                dep_files: dict[str, str] = {}
                for dep_id in node.depends_on:
                    if dep_id in all_results:
                        dep_result = all_results[dep_id]
                        dep_files[dep_result.artifact.filename] = dep_result.artifact.content

                # Run worker + verify with retry loop.
                worker_result = await self._run_with_retries(
                    node=node,
                    execution=execution,
                    generated_files=dep_files,
                    prompt=prompt,
                    plan_md=plan_md,
                    contracts_md=contracts_md,
                    architecture=architecture,
                    run_id=run_id,
                    spans=spans,
                    trace=trace,
                )

                all_results[node.id] = worker_result
                generated_files[worker_result.artifact.filename] = worker_result.artifact.content
                self._state.mark_task(task_id=node.id, status=TaskStatus.succeeded)
                completed.add(node_id)
                remaining.pop(node_id)
                progressed = True

            if not progressed:
                # Unresolvable dependencies.
                for node_id in remaining:
                    execution[node_id].status = TaskStatus.failed
                    execution[node_id].error = "Unresolvable dependencies"
                break

        # ── Step 3: Final cross-file verification ────────────────────
        verifier_node = next(
            (n for n in task_graph.nodes if n.worker_type == WorkerType.verifier),
            None,
        )
        verifier_report_dict: dict = {}

        if verifier_node and all_results:
            v_exec = execution[verifier_node.id]
            v_exec.status = TaskStatus.running
            v_exec.started_at_ms = now_ms()

            await self._emit({"type": "status", "message": "Running final verification..."})

            v_span = span_start(
                spans,
                name="verifier.final",
                role="verifier",
                worker_type=WorkerType.verifier,
                model_tier=ModelTier.verifier,
                model=None,
                meta={"node_id": verifier_node.id},
            )
            final_report = await self._verifier.verify_final(
                task_graph=task_graph,
                all_results=all_results,
                user_goal=prompt,
            )
            verifier_report_dict = final_report.model_dump()
            v_exec.status = TaskStatus.succeeded if final_report.ok else TaskStatus.failed
            v_exec.ended_at_ms = now_ms()
            v_exec.artifacts = {"verifier_report": verifier_report_dict}
            if not final_report.ok:
                v_exec.error = "; ".join(final_report.issues)

            span_end(
                spans,
                v_span,
                status="ok" if final_report.ok else "error",
                meta=verifier_report_dict,
            )
            trace_emit(
                trace,
                role=TraceRole.verifier,
                title=f"Final verification: {final_report.status}",
                detail=(
                    "All files passed cross-file consistency check."
                    if final_report.ok
                    else "Issues: " + "; ".join(final_report.issues)
                ),
                node_id=verifier_node.id,
                worker_type=WorkerType.verifier,
                model_tier=ModelTier.verifier,
                meta=verifier_report_dict,
            )

            self._state.mark_task(
                task_id=verifier_node.id,
                status=TaskStatus.succeeded if final_report.ok else TaskStatus.failed,
            )

            # --- EXPERIMENTAL FIXER ---
            if not final_report.ok:
                await self._emit({"type": "status", "message": "Applying global fixes using reasoning model..."})
                fixed_files = await self._fixer.fix(
                    task_graph=task_graph,
                    all_results=all_results,
                    issues=final_report.issues,
                    user_goal=prompt
                )
                if fixed_files:
                    # Update all_results and generated_files
                    for f_name, f_content in fixed_files.items():
                        # Find corresponding node
                        for node_id, w_res in all_results.items():
                            if w_res.artifact.filename == f_name:
                                w_res.artifact.content = f_content
                                generated_files[f_name] = f_content
                                # Emit file generated event to update UI
                                await self._emit({
                                    "type": "file_generated",
                                    "node_id": node_id,
                                    "filename": f_name,
                                    "content": f_content,
                                })
                                break

        # ── Telemetry ────────────────────────────────────────────────
        self._state.update_telemetry({
            "run_id": run_id,
            "graph_id": task_graph.graph_id,
            "files_generated": len(all_results),
            "verifier_status": verifier_report_dict.get("status", "N/A"),
        })

        result = OrchestrationRun(
            run_id=run_id,
            prompt=prompt,
            plan=task_graph,
            execution=execution,
            spans=spans,
            trace=trace,
            routing_log=routing_log,
            verifier_report=verifier_report_dict,
            plan_markdown=self._state.read_plan_markdown(),
            contracts_markdown=self._state.read_contracts_markdown(),
        )

        await self._emit({"type": "complete", "run": json.loads(result.model_dump_json())})
        return result

    async def _run_with_retries(
        self,
        *,
        node: TaskNode,
        execution: dict[str, NodeExecution],
        generated_files: dict[str, str],
        prompt: str,
        plan_md: str,
        contracts_md: str,
        architecture: str,
        run_id: str,
        spans: list,
        trace: list,
    ) -> WorkerResult:
        """Run a worker, verify, retry on failure up to MAX_RETRIES."""
        exec_rec = execution[node.id]
        exec_rec.status = TaskStatus.running
        exec_rec.started_at_ms = now_ms()

        retry_issues: list[str] | None = None

        for attempt in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES retries
            # ── Worker call ──
            w_span = span_start(
                spans,
                name=f"worker.{node.worker_type.value}",
                role="worker",
                worker_type=node.worker_type,
                model_tier=ModelTier.worker,
                model=None,
                meta={"node_id": node.id, "attempt": attempt},
            )
            worker_started = time.perf_counter()

            await self._emit({
                "type": "worker_start",
                "node_id": node.id,
                "attempt": attempt,
                "message": f"Worker generating code{' (retry)' if attempt > 1 else ''}...",
            })

            plan_section = _extract_section(plan_md, _section_for(node.worker_type))
            worker_result = await self._worker.run(
                ctx=ScopedContext(
                    run_id=run_id,
                    user_goal=prompt,
                    node=node,
                    upstream_artifacts={},
                    plan_section_markdown=plan_section,
                    allowed_plan_item_keys=set(),
                ),
                contracts_markdown=contracts_md,
                upstream_code=generated_files,
                retry_issues=retry_issues,
                architecture=architecture,
            )

            span_end(
                spans,
                w_span,
                latency_ms=int((time.perf_counter() - worker_started) * 1000),
                meta={"filename": worker_result.artifact.filename, "attempt": attempt},
            )

            action = "generated" if attempt == 1 else f"regenerated (attempt {attempt})"
            trace_emit(
                trace,
                role=TraceRole.worker,
                title=f"Worker {action}: {worker_result.artifact.filename}",
                detail=f"File: {worker_result.artifact.filename} ({len(worker_result.artifact.content)} chars)",
                node_id=node.id,
                worker_type=node.worker_type,
                model_tier=ModelTier.worker,
                meta={"attempt": attempt, "filename": worker_result.artifact.filename},
            )

            # Send the generated code to the frontend.
            await self._emit({
                "type": "file_generated",
                "node_id": node.id,
                "filename": worker_result.artifact.filename,
                "content": worker_result.artifact.content,
                "attempt": attempt,
            })

            # ── Verify ──
            await self._emit({
                "type": "verify_start",
                "node_id": node.id,
                "filename": worker_result.artifact.filename,
                "message": "Verifier checking code quality...",
            })

            v_span = span_start(
                spans,
                name="verifier.per_file",
                role="verifier",
                worker_type=WorkerType.verifier,
                model_tier=ModelTier.verifier,
                model=None,
                meta={"node_id": node.id, "attempt": attempt},
            )
            verify_started = time.perf_counter()
            report = await self._verifier.verify_file(
                task_node=node,
                worker_result=worker_result,
                upstream_code=generated_files,
                user_goal=prompt,
            )
            span_end(
                spans,
                v_span,
                status="ok" if report.ok else "error",
                latency_ms=int((time.perf_counter() - verify_started) * 1000),
                meta=report.model_dump(),
            )

            if report.ok:
                trace_emit(
                    trace,
                    role=TraceRole.verifier,
                    title=f"Verified PASS: {worker_result.artifact.filename}",
                    detail="File passed verification.",
                    node_id=node.id,
                    worker_type=WorkerType.verifier,
                    model_tier=ModelTier.verifier,
                )
                exec_rec.status = TaskStatus.succeeded
                exec_rec.ended_at_ms = now_ms()
                exec_rec.artifacts = worker_result.model_dump()

                await self._emit({
                    "type": "file_verified",
                    "node_id": node.id,
                    "filename": worker_result.artifact.filename,
                    "status": "PASS",
                })
                return worker_result

            # Verification failed — retry or accept.
            trace_emit(
                trace,
                role=TraceRole.verifier,
                title=f"Verified FAIL (attempt {attempt}): {worker_result.artifact.filename}",
                detail="Issues: " + "; ".join(report.issues),
                node_id=node.id,
                worker_type=WorkerType.verifier,
                model_tier=ModelTier.verifier,
                meta={"issues": report.issues, "attempt": attempt},
            )

            await self._emit({
                "type": "file_verified",
                "node_id": node.id,
                "filename": worker_result.artifact.filename,
                "status": "FAIL",
                "issues": report.issues,
            })

            if attempt <= MAX_RETRIES:
                retry_issues = report.issues
                trace_emit(
                    trace,
                    role=TraceRole.system,
                    title=f"Retrying {node.id} (attempt {attempt + 1})",
                    detail=f"Feeding {len(report.issues)} issues back to worker.",
                    node_id=node.id,
                )
                await self._emit({
                    "type": "file_retry",
                    "node_id": node.id,
                    "attempt": attempt + 1,
                    "issues": report.issues,
                })
            else:
                # Accept the last attempt even if imperfect.
                exec_rec.status = TaskStatus.succeeded
                exec_rec.ended_at_ms = now_ms()
                exec_rec.artifacts = worker_result.model_dump()
                exec_rec.error = f"Accepted after {MAX_RETRIES} retries; issues: {'; '.join(report.issues)}"
                return worker_result

        # Should not reach here, but just in case.
        exec_rec.status = TaskStatus.failed
        exec_rec.ended_at_ms = now_ms()
        return worker_result  # type: ignore[possibly-undefined]


async def run_generate(prompt: str) -> OrchestrationRun:
    if settings.mock_mode or not settings.openai_base_url:
        return await run_generate_simulation(prompt)
    return await CognitiveOrchestrationLoop().run(prompt=prompt)


async def run_generate_stream(prompt: str) -> AsyncIterator[str]:
    """SSE-compatible generator that yields events as the orchestration progresses."""
    if settings.mock_mode or not settings.openai_base_url:
        async for event in run_generate_stream_simulation(prompt):
            yield event
        return

    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

    async def enqueue_event(event: dict[str, Any]) -> None:
        await queue.put(event)

    loop = CognitiveOrchestrationLoop(on_event=enqueue_event)

    async def run_in_background():
        try:
            await loop.run(prompt=prompt)
        except Exception as e:
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)  # Signal end.

    task = asyncio.create_task(run_in_background())

    while True:
        event = await queue.get()
        if event is None:
            break
        yield f"data: {json.dumps(event)}\n\n"

    await task  # Ensure the task is fully done.


def _section_for(worker_type: WorkerType) -> str:
    return {
        WorkerType.backend: "Backend",
        WorkerType.frontend: "Frontend",
        WorkerType.file: "Configuration",
        WorkerType.research: "Research",
    }.get(worker_type, "Other")


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

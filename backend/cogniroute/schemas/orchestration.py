from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .task_graph import TaskGraph, TaskStatus
from .telemetry import TelemetrySpan, TraceEvent


class NodeExecution(BaseModel):
    node_id: str
    status: TaskStatus = TaskStatus.pending
    started_at_ms: Optional[int] = None
    ended_at_ms: Optional[int] = None
    error: Optional[str] = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    filename: str
    content: str


class WorkerResult(BaseModel):
    task_id: str
    status: Literal["completed", "failed"]
    artifact: Artifact
    notes: str = ""


class VerifierReport(BaseModel):
    status: Literal["PASS", "FAIL"]
    issues: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


class OrchestrationRun(BaseModel):
    run_id: str
    prompt: str
    plan: TaskGraph
    execution: dict[str, NodeExecution]

    spans: list[TelemetrySpan] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    routing_log: list[dict[str, Any]] = Field(default_factory=list)
    verifier_report: dict[str, Any] = Field(default_factory=dict)
    plan_markdown: str = ""
    contracts_markdown: str = ""


class RunRequest(BaseModel):
    prompt: str


class RunResponse(BaseModel):
    run: OrchestrationRun


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    run: OrchestrationRun

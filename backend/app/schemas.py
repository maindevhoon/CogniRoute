from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ModelTier(str, Enum):
    architect = "architect"
    worker = "worker"
    verifier = "verifier"


class WorkerType(str, Enum):
    frontend = "frontend"
    backend = "backend"
    research = "research"
    file = "file"
    verifier = "verifier"


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class TaskNode(BaseModel):
    id: str
    title: str
    description: str
    worker_type: WorkerType
    model_tier: ModelTier
    depends_on: list[str] = Field(default_factory=list)

    # Explicit interfaces/contracts for scoped execution.
    inputs_schema: dict[str, Any] = Field(default_factory=dict)
    outputs_schema: dict[str, Any] = Field(default_factory=dict)


class TaskGraph(BaseModel):
    graph_id: str
    user_goal: str
    nodes: list[TaskNode]


class TelemetrySpan(BaseModel):
    span_id: str
    name: str
    worker_type: Optional[WorkerType] = None
    model_tier: Optional[ModelTier] = None
    started_at_ms: int
    ended_at_ms: Optional[int] = None
    status: Literal["ok", "error"] = "ok"
    meta: dict[str, Any] = Field(default_factory=dict)


class NodeExecution(BaseModel):
    node_id: str
    status: TaskStatus = TaskStatus.pending
    started_at_ms: Optional[int] = None
    ended_at_ms: Optional[int] = None
    error: Optional[str] = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


class TraceRole(str, Enum):
    system = "system"
    user = "user"
    architect = "architect"
    worker = "worker"
    verifier = "verifier"


class TraceEvent(BaseModel):
    event_id: str
    at_ms: int
    role: TraceRole
    title: str
    detail: str
    node_id: Optional[str] = None
    worker_type: Optional[WorkerType] = None
    model_tier: Optional[ModelTier] = None
    meta: dict[str, Any] = Field(default_factory=dict)


class OrchestrationRun(BaseModel):
    run_id: str
    prompt: str
    plan: TaskGraph
    execution: dict[str, NodeExecution]
    spans: list[TelemetrySpan] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    routing_log: list[dict[str, Any]] = Field(default_factory=list)
    verifier_report: dict[str, Any] = Field(default_factory=dict)


class RunRequest(BaseModel):
    prompt: str


class RunResponse(BaseModel):
    run: OrchestrationRun


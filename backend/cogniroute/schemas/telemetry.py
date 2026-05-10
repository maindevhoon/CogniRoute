from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .task_graph import ModelTier, WorkerType


class TraceRole(str, Enum):
    system = "system"
    user = "user"
    architect = "architect"
    worker = "worker"
    verifier = "verifier"


class TelemetrySpan(BaseModel):
    span_id: str
    name: str
    role: Optional[str] = None
    worker_type: Optional[WorkerType] = None
    model_tier: Optional[ModelTier] = None
    model: Optional[str] = None

    started_at_ms: int
    ended_at_ms: Optional[int] = None
    status: Literal["ok", "error"] = "ok"

    latency_ms: Optional[int] = None
    token_estimate_in: Optional[int] = None
    token_estimate_out: Optional[int] = None

    meta: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    event_id: str
    at_ms: int
    role: TraceRole
    title: str
    detail: str
    node_id: Optional[str] = None
    worker_type: Optional[WorkerType] = None
    model_tier: Optional[ModelTier] = None
    model: Optional[str] = None
    meta: dict[str, Any] = Field(default_factory=dict)


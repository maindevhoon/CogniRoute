from __future__ import annotations

from enum import Enum
from typing import Any

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

    inputs_schema: dict[str, Any] = Field(default_factory=dict)
    outputs_schema: dict[str, Any] = Field(default_factory=dict)


class TaskGraph(BaseModel):
    graph_id: str
    user_goal: str
    nodes: list[TaskNode]


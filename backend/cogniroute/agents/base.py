from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..schemas import TaskGraph, TaskNode


@dataclass(frozen=True)
class ScopedContext:
    """
    The *only* context workers should receive in the MVP.

    Keep this intentionally small and explicit so the runtime feels like
    "cognitive scheduling" rather than an unbounded chatbot.
    """

    run_id: str
    user_goal: str
    node: TaskNode
    upstream_artifacts: dict[str, Any]
    plan_section_markdown: str
    allowed_plan_item_keys: set[str]


@dataclass(frozen=True)
class PlanUpdate:
    """
    A worker's *proposed* update to the shared implementation plan.

    The orchestrator applies these updates (sequentially) as the single writer.
    """

    checklist_updates: dict[str, str]  # PlanItem.key() -> "todo"|"done"
    notes: str = ""


class Architect(Protocol):
    async def plan(self, *, user_request: str) -> TaskGraph: ...


class Worker(Protocol):
    async def run(self, *, ctx: ScopedContext) -> tuple[dict[str, Any], PlanUpdate]: ...


class Verifier(Protocol):
    async def checkpoint(self, *, user_goal: str, plan: TaskGraph, execution: dict[str, Any], plan_markdown: str) -> dict[str, Any]: ...


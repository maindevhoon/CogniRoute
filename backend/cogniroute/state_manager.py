from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .schemas import TaskGraph, TaskStatus
from .state.plan import ChecklistStatus, apply_checklist_updates, parse_implementation_plan
from .state.store import StatePaths


class StateManager:
    """
    Markdown-backed execution state for the MVP loop.

    This deliberately uses simple line-oriented markdown parsing. The plan file
    is the externalized cognition surface; the orchestrator remains the only
    writer.
    """

    def __init__(self, *, paths: StatePaths | None = None) -> None:
        self.paths = paths or StatePaths.default()
        self.paths.root_dir.mkdir(parents=True, exist_ok=True)

    def create_implementation_plan(self, *, user_request: str, task_graph: TaskGraph) -> str:
        frontend_tasks = [n for n in task_graph.nodes if n.worker_type.value == "frontend"]
        verifier_tasks = [n for n in task_graph.nodes if n.worker_type.value == "verifier"]

        lines = [
            "# Implementation Plan",
            "",
            f"User request: {user_request}",
            "",
            "## Frontend",
            "",
        ]
        for node in frontend_tasks:
            lines.append(f"* [ ] {node.id}: {node.title}")

        lines.extend(["", "## Verification", ""])
        for node in verifier_tasks:
            lines.append(f"* [ ] {node.id}: {node.title}")

        markdown = "\n".join(lines).rstrip() + "\n"
        self.paths.implementation_plan.write_text(markdown, encoding="utf-8")
        return markdown

    def create_system_contracts(self, *, task_graph: TaskGraph) -> str:
        frontend = next((n for n in task_graph.nodes if n.worker_type.value == "frontend"), None)
        output_schema = json.dumps(frontend.outputs_schema if frontend else {}, indent=2, sort_keys=True)
        markdown = (
            "# System Contracts\n\n"
            "## Runtime Constraints\n\n"
            "- Sequential orchestration only\n"
            "- One frontend worker task per `/generate` call\n"
            "- Workers receive scoped task context only\n"
            "- Plan state is stored in `state/implementation_plan.md`\n"
            "- Verification is a single checkpoint, not a replanning loop\n\n"
            "## Frontend Artifact Contract\n\n"
            "The frontend worker must return exactly one artifact with a filename and content.\n\n"
            "```json\n"
            f"{output_schema}\n"
            "```\n"
        )
        self.paths.system_contracts.write_text(markdown, encoding="utf-8")
        return markdown

    def read_execution_state(self) -> dict[str, Any]:
        plan_md = self.read_plan_markdown()
        contracts_md = self.read_contracts_markdown()
        parsed = parse_implementation_plan(plan_md)
        return {
            "implementation_plan": plan_md,
            "system_contracts": contracts_md,
            "checklist": [
                {"key": item.key(), "section": item.section, "text": item.text, "status": item.status.value}
                for item in parsed.all_items()
            ],
        }

    def read_plan_markdown(self) -> str:
        if not self.paths.implementation_plan.exists():
            return ""
        return self.paths.implementation_plan.read_text(encoding="utf-8")

    def read_contracts_markdown(self) -> str:
        if not self.paths.system_contracts.exists():
            return ""
        return self.paths.system_contracts.read_text(encoding="utf-8")

    def mark_task(self, *, task_id: str, status: TaskStatus) -> str:
        desired = ChecklistStatus.done if status == TaskStatus.succeeded else ChecklistStatus.todo
        plan = parse_implementation_plan(self.read_plan_markdown())
        updates: dict[str, ChecklistStatus] = {}
        for item in plan.all_items():
            if item.text.startswith(f"{task_id}:"):
                updates[item.key()] = desired
        markdown = apply_checklist_updates(self.read_plan_markdown(), updates=updates)
        self.paths.implementation_plan.write_text(markdown, encoding="utf-8")
        return markdown

    def update_telemetry(self, event: dict[str, Any]) -> None:
        p = self.paths.telemetry_json
        data = {"events": []}
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8") or '{"events":[]}')
        event = {"at_ms": int(time.time() * 1000), **event}
        data.setdefault("events", []).append(event)
        p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_state_manager() -> StateManager:
    return StateManager()

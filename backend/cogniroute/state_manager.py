from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .schemas import TaskGraph, TaskStatus, WorkerType
from .state.plan import ChecklistStatus, apply_checklist_updates, parse_implementation_plan
from .state.store import StatePaths


# Map worker_type to plan section heading.
_SECTION_MAP: dict[str, str] = {
    "backend": "Backend",
    "frontend": "Frontend",
    "file": "Configuration",
    "research": "Research",
}


class StateManager:
    """
    Markdown-backed execution state for the multi-file orchestration loop.

    This deliberately uses simple line-oriented markdown parsing. The plan file
    is the externalized cognition surface; the orchestrator remains the only
    writer.
    """

    def __init__(self, *, paths: StatePaths | None = None) -> None:
        self.paths = paths or StatePaths.default()
        self.paths.root_dir.mkdir(parents=True, exist_ok=True)

    def create_implementation_plan(self, *, user_request: str, task_graph: TaskGraph) -> str:
        """Generate a multi-section implementation plan from the task graph."""
        # Group file tasks by section.
        sections: dict[str, list] = {}
        for node in task_graph.nodes:
            if node.worker_type == WorkerType.verifier:
                continue
            section = _SECTION_MAP.get(node.worker_type.value, "Other")
            sections.setdefault(section, []).append(node)

        lines = [
            "# Implementation Plan",
            "",
            f"User request: {user_request}",
            "",
        ]

        for section_name, nodes in sections.items():
            lines.append(f"## {section_name}")
            lines.append("")
            for node in nodes:
                target_file = node.outputs_schema.get("filename", node.title)
                lines.append(f"* [ ] {node.id}: {node.title} → {target_file}")
            lines.append("")

        # Verification section.
        verifier_tasks = [n for n in task_graph.nodes if n.worker_type == WorkerType.verifier]
        if verifier_tasks:
            lines.append("## Verification")
            lines.append("")
            for node in verifier_tasks:
                lines.append(f"* [ ] {node.id}: {node.title}")
            lines.append("")

        markdown = "\n".join(lines).rstrip() + "\n"
        self.paths.implementation_plan.write_text(markdown, encoding="utf-8")
        return markdown

    def create_system_contracts(self, *, task_graph: TaskGraph) -> str:
        """Generate system contracts describing the expected outputs."""
        file_tasks = [n for n in task_graph.nodes if n.worker_type != WorkerType.verifier]

        file_list = "\n".join(
            f"- `{n.outputs_schema.get('filename', n.title)}` — {n.description[:80]}"
            for n in file_tasks
        )

        markdown = (
            "# System Contracts\n\n"
            "## Runtime Constraints\n\n"
            "- Sequential orchestration only\n"
            "- Each worker task generates exactly one file\n"
            "- Workers receive scoped task context + upstream file contents\n"
            "- Verifier checks each file; failed files are retried up to 2 times\n"
            "- Final verification checks cross-file consistency\n\n"
            "## File Artifact Contract\n\n"
            "Each worker must return JSON with:\n"
            "- `task_id`: matching the assigned task node id\n"
            "- `status`: 'completed'\n"
            "- `artifact.filename`: the target file path\n"
            "- `artifact.content`: the COMPLETE file source code (no truncation)\n\n"
            "## Planned Files\n\n"
            f"{file_list}\n"
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

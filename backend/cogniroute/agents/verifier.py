from __future__ import annotations

from typing import Any

from ..schemas import TaskGraph


class VerifierAgent:
    """
    Verifier (single checkpoint only).

    This intentionally does not replan, retry, or loop.
    """

    async def checkpoint(
        self, *, user_goal: str, plan: TaskGraph, execution: dict[str, Any], plan_markdown: str
    ) -> dict[str, Any]:
        node_ids = {n.id for n in plan.nodes}
        missing_deps = []
        for n in plan.nodes:
            for dep in n.depends_on:
                if dep not in node_ids:
                    missing_deps.append({"node": n.id, "missing_dep": dep})

        failed = []
        for node_id, rec in execution.items():
            status = getattr(rec, "status", None)
            if status == "failed":
                failed.append(node_id)

        return {
            "ok": (len(missing_deps) == 0 and len(failed) == 0),
            "missing_deps": missing_deps,
            "failed_nodes": failed,
            "completed_checklist_items": _completed_checklist_items(plan_markdown),
            "notes": "Sequential checkpoint validation only (no loops, no retries).",
        }


def _completed_checklist_items(plan_markdown: str) -> list[str]:
    completed: list[str] = []
    for line in plan_markdown.splitlines():
        line = line.strip()
        if line.startswith(("* [x]", "- [x]", "* [X]", "- [X]")):
            completed.append(line)
    return completed


from __future__ import annotations

from ..base import ScopedContext


class ResearchWorker:
    async def run(self, *, ctx: ScopedContext):
        artifacts = {
            "summary": "Stubbed research worker",
            "node_id": ctx.node.id,
            "notes": "No autonomous browsing/tools in this skeleton.",
        }
        plan_update = {
            "checklist_updates": {},
            "notes": "Research tools are disabled; no updates.",
        }
        return artifacts, plan_update


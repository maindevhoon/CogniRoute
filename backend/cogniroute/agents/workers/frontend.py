from __future__ import annotations

from ..base import ScopedContext


class FrontendWorker:
    async def run(self, *, ctx: ScopedContext):
        artifacts = {
            "summary": "Stubbed frontend worker",
            "node_id": ctx.node.id,
            "notes": "Frontend work is explicitly out of scope for now.",
        }
        plan_update = {
            "checklist_updates": {},
            "notes": "Frontend is out of scope; no updates.",
        }
        return artifacts, plan_update


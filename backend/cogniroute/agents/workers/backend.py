from __future__ import annotations

from ..base import ScopedContext


class BackendWorker:
    async def run(self, *, ctx: ScopedContext):
        artifacts = {
            "summary": "Stubbed backend worker",
            "node_id": ctx.node.id,
            "notes": "No real code generation in Phase 1.",
        }
        plan_update = {
            "checklist_updates": {},
            "notes": "No checklist updates emitted by this stub.",
        }
        return artifacts, plan_update


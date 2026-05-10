from __future__ import annotations

from ..base import ScopedContext


class FileWorker:
    async def run(self, *, ctx: ScopedContext):
        artifacts = {
            "summary": "Stubbed file worker",
            "node_id": ctx.node.id,
            "notes": "Filesystem persistence/writes are disabled in this phase.",
        }
        plan_update = {
            "checklist_updates": {},
            "notes": "Filesystem writes are disabled; no plan updates.",
        }
        return artifacts, plan_update


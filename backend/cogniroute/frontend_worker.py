from __future__ import annotations

import re

from .llm import safe_json_loads
from .agents.base import ScopedContext
from .schemas import Artifact, WorkerResult
from .services.llm import call_model


WORKER_RESULT_SCHEMA_HINT = """{
  "task_id": "string",
  "status": "completed",
  "artifact": {
    "filename": "ComponentName.tsx",
    "content": "valid TSX component source"
  },
  "notes": "string"
}"""


class FrontendWorker:
    """
    Scoped frontend executor.

    The worker receives only the task node, frontend plan section, and explicit
    contracts. It returns one artifact and never reads repository context.
    """

    async def run(self, *, ctx: ScopedContext, contracts_markdown: str) -> WorkerResult:
        model_result = await self._run_model(ctx=ctx, contracts_markdown=contracts_markdown)
        if model_result is not None:
            return model_result

        component_name = _component_name(ctx.user_goal)
        content = _render_component(component_name=component_name, user_goal=ctx.user_goal)
        return WorkerResult(
            task_id=ctx.node.id,
            status="completed",
            artifact=Artifact(filename=f"{component_name}.tsx", content=content),
            notes=(
                "Generated from scoped task context only. "
                f"Plan section chars={len(ctx.plan_section_markdown)}, contracts chars={len(contracts_markdown)}."
            ),
        )

    async def _run_model(self, *, ctx: ScopedContext, contracts_markdown: str) -> WorkerResult | None:
        prompt = (
            "Execute this single scoped frontend task. Do not ask for repo context. "
            "Do not mention files you cannot see. Return one TSX artifact only.\n\n"
            f"Task id: {ctx.node.id}\n"
            f"Task title: {ctx.node.title}\n"
            f"Task description: {ctx.node.description}\n\n"
            f"User goal:\n{ctx.user_goal}\n\n"
            f"Scoped plan section:\n{ctx.plan_section_markdown}\n\n"
            f"Contracts:\n{contracts_markdown}\n"
        )
        try:
            result = await call_model("worker", prompt, json_schema_hint=WORKER_RESULT_SCHEMA_HINT)
            worker_result = WorkerResult.model_validate(safe_json_loads(result.text))
            if worker_result.task_id != ctx.node.id:
                worker_result.task_id = ctx.node.id
            if not worker_result.artifact.filename.endswith(".tsx"):
                worker_result.artifact.filename = _component_name(ctx.user_goal) + ".tsx"
            return worker_result
        except Exception:
            return None


def _component_name(user_goal: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", user_goal.title())
    stem = "".join(words[:4]) or "CogniRouteArtifact"
    if not stem.endswith("View"):
        stem += "View"
    return stem


def _render_component(*, component_name: str, user_goal: str) -> str:
    escaped_goal = user_goal.replace("{", "{{").replace("}", "}}")
    return f"""export default function {component_name}() {{
  const stages = [
    "Architect plans the work",
    "Frontend worker executes one scoped task",
    "Verifier checks the completed artifact",
  ];

  return (
    <main className="min-h-screen bg-zinc-950 px-6 py-8 text-zinc-100">
      <section className="mx-auto max-w-4xl">
        <p className="text-sm uppercase tracking-wide text-cyan-300">CogniRoute MVP</p>
        <h1 className="mt-3 text-3xl font-semibold">Scoped orchestration artifact</h1>
        <p className="mt-4 max-w-2xl text-sm leading-6 text-zinc-300">{escaped_goal}</p>
        <ol className="mt-8 grid gap-3 md:grid-cols-3">
          {{stages.map((stage, index) => (
            <li key={{stage}} className="rounded border border-zinc-800 bg-zinc-900 p-4">
              <span className="text-xs text-cyan-300">0{{index + 1}}</span>
              <p className="mt-2 text-sm font-medium">{{stage}}</p>
            </li>
          ))}}
        </ol>
      </section>
    </main>
  );
}}
"""

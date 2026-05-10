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
    "filename": "path/to/file.ext",
    "content": "full file source code"
  },
  "notes": "string"
}"""


class CodeWorker:
    """
    Generic scoped code-generation worker.

    Given a task node describing a single file to produce, this worker
    prompts the 7B model with the task description, upstream file context,
    and any retry feedback from the verifier.  It returns one WorkerResult
    with the generated file.
    """

    async def run(
        self,
        *,
        ctx: ScopedContext,
        contracts_markdown: str,
        upstream_code: dict[str, str],
        retry_issues: list[str] | None = None,
    ) -> WorkerResult:
        model_result = await self._run_model(
            ctx=ctx,
            contracts_markdown=contracts_markdown,
            upstream_code=upstream_code,
            retry_issues=retry_issues,
        )
        if model_result is not None:
            return model_result

        # Fallback: deterministic stub so the pipeline never hard-crashes.
        filename = _infer_filename(ctx.node.title, ctx.node.worker_type.value)
        return WorkerResult(
            task_id=ctx.node.id,
            status="completed",
            artifact=Artifact(
                filename=filename,
                content=f"// TODO: {ctx.node.title}\n// {ctx.node.description}\n",
            ),
            notes="LLM call failed; returned deterministic stub.",
        )

    async def _run_model(
        self,
        *,
        ctx: ScopedContext,
        contracts_markdown: str,
        upstream_code: dict[str, str],
        retry_issues: list[str] | None = None,
    ) -> WorkerResult | None:
        # Build upstream file context block.
        upstream_block = ""
        if upstream_code:
            parts = []
            for fname, code in upstream_code.items():
                parts.append(f"### FILE: {fname}\n```\n{code}\n```")
            upstream_block = (
                "\n\n## EXISTING PROJECT FILES (import from these, match their interfaces):\n"
                + "\n\n".join(parts)
            )

        retry_block = ""
        if retry_issues:
            retry_block = (
                "\n\n## RETRY — YOUR PREVIOUS CODE WAS REJECTED. FIX THESE ISSUES:\n"
                + "\n".join(f"  ❌ {issue}" for issue in retry_issues)
                + "\n\nGenerate the COMPLETE CORRECTED file from scratch. Do not explain — just return the fixed JSON."
            )

        prompt = (
            f"Generate the file: {ctx.node.outputs_schema.get('filename', ctx.node.title)}\n\n"
            f"## TASK\n"
            f"ID: {ctx.node.id}\n"
            f"Title: {ctx.node.title}\n"
            f"Description: {ctx.node.description}\n\n"
            f"## USER GOAL\n{ctx.user_goal}\n"
            f"{upstream_block}"
            f"{retry_block}\n\n"
            "## INSTRUCTIONS\n"
            "- Write the COMPLETE file. Every function must have a real implementation.\n"
            "- Include all necessary imports.\n"
            "- If upstream files define classes/functions, import and use them.\n"
            "- Return ONLY valid JSON matching the schema hint."
        )
        try:
            result = await call_model(
                "worker", prompt, json_schema_hint=WORKER_RESULT_SCHEMA_HINT
            )
            worker_result = WorkerResult.model_validate(safe_json_loads(result.text))
            # Ensure task_id matches.
            if worker_result.task_id != ctx.node.id:
                worker_result.task_id = ctx.node.id
            return worker_result
        except Exception:
            return None


def _infer_filename(title: str, worker_type: str) -> str:
    """Best-effort filename from the task title."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", title.strip()).strip("_").lower()
    ext_map = {
        "frontend": ".tsx",
        "backend": ".py",
        "file": ".txt",
        "research": ".md",
    }
    ext = ext_map.get(worker_type, ".txt")
    return f"{slug}{ext}"

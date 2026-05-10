from __future__ import annotations

import re
from pathlib import Path

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

# Skill files directory (backend/cogniroute/skills/).
_SKILLS_DIR = Path(__file__).resolve().parent / "skills"

# Map worker_type -> skill filename.
_SKILL_MAP: dict[str, str] = {
    "frontend": "frontend.md",
    "backend": "backend.md",
}


def _load_skill(worker_type: str) -> str:
    """Load the skill markdown for a given worker type, or empty string."""
    fname = _SKILL_MAP.get(worker_type)
    if not fname:
        return ""
    path = _SKILLS_DIR / fname
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


class CodeWorker:
    """
    Generic scoped code-generation worker with skill injection.

    The worker loads a skill file based on worker_type (frontend.md, backend.md)
    and prepends it to the prompt so the 7B model gets domain-specific rules.
    """

    async def run(
        self,
        *,
        ctx: ScopedContext,
        contracts_markdown: str,
        upstream_code: dict[str, str],
        retry_issues: list[str] | None = None,
        architecture: str = "",
    ) -> WorkerResult:
        model_result = await self._run_model(
            ctx=ctx,
            contracts_markdown=contracts_markdown,
            upstream_code=upstream_code,
            retry_issues=retry_issues,
            architecture=architecture,
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
        architecture: str = "",
    ) -> WorkerResult | None:
        # Load domain-specific skill.
        skill = _load_skill(ctx.node.worker_type.value)
        skill_block = f"## SKILL (follow these rules strictly)\n{skill}\n\n" if skill else ""

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

        arch_block = ""
        if architecture:
            arch_block = f"## ARCHITECTURE CONTEXT (how your file fits in the system)\n{architecture}\n\n"

        prompt = (
            f"{skill_block}"
            f"{arch_block}"
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
            "- Follow the architecture context above for naming, API paths, and data models.\n"
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

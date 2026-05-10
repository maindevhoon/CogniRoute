from __future__ import annotations

from .llm import safe_json_loads
from .schemas import TaskGraph, TaskNode, VerifierReport, WorkerResult
from .services.llm import call_model


VERIFIER_SCHEMA_HINT = """{
  "status": "PASS|FAIL",
  "issues": ["concise description of each problem found"]
}"""


class VerifierAgent:
    """
    Per-file verifier for the multi-file orchestration loop.

    Called after each worker produces a file.  Returns PASS or FAIL with
    actionable issues that get fed back to the worker on retry.
    """

    async def verify_file(
        self,
        *,
        task_node: TaskNode,
        worker_result: WorkerResult,
        upstream_code: dict[str, str],
        user_goal: str,
    ) -> VerifierReport:
        """Verify a single generated file against its task spec."""
        model_report = await self._run_model(
            task_node=task_node,
            worker_result=worker_result,
            upstream_code=upstream_code,
            user_goal=user_goal,
        )
        if model_report is not None:
            return model_report

        # Deterministic fallback checks.
        return self._deterministic_check(worker_result)

    async def verify_final(
        self,
        *,
        task_graph: TaskGraph,
        all_results: dict[str, WorkerResult],
        user_goal: str,
    ) -> VerifierReport:
        """Final verification of all generated files together."""
        files_summary = "\n".join(
            f"- {r.artifact.filename} ({len(r.artifact.content)} chars)"
            for r in all_results.values()
        )
        prompt = (
            "You are doing a FINAL verification of a complete project.\n"
            "Check that all files are consistent with each other and with the user goal.\n"
            "Look for: missing imports between files, API mismatches, incomplete implementations.\n\n"
            f"User goal: {user_goal}\n\n"
            f"Generated files:\n{files_summary}\n\n"
            "File contents:\n"
        )
        for r in all_results.values():
            prompt += f"\n--- {r.artifact.filename} ---\n{r.artifact.content}\n"

        prompt += "\n\nReturn PASS if the project is coherent, FAIL with issues if not."

        try:
            result = await call_model(
                "verifier", prompt, json_schema_hint=VERIFIER_SCHEMA_HINT
            )
            return VerifierReport.model_validate(safe_json_loads(result.text))
        except Exception:
            # If final verification LLM fails, do basic checks.
            issues = []
            for r in all_results.values():
                issues.extend(self._deterministic_check(r).issues)
            return VerifierReport(
                status="PASS" if not issues else "FAIL", issues=issues
            )

    async def _run_model(
        self,
        *,
        task_node: TaskNode,
        worker_result: WorkerResult,
        upstream_code: dict[str, str],
        user_goal: str,
    ) -> VerifierReport | None:
        upstream_block = ""
        if upstream_code:
            parts = [f"--- {f} ---\n{c}\n" for f, c in upstream_code.items()]
            upstream_block = (
                "\n\nOther project files for context:\n" + "\n".join(parts)
            )

        prompt = (
            f"Review this file: {worker_result.artifact.filename}\n\n"
            f"Task: {task_node.title}\n"
            f"Description: {task_node.description}\n\n"
            f"```\n{worker_result.artifact.content}\n```\n"
            f"{upstream_block}\n\n"
            "FAIL only if there are REAL bugs:\n"
            "- Missing imports that would cause ImportError/NameError at runtime\n"
            "- Empty function bodies (just 'pass' or raise NotImplementedError)\n"
            "- Truncated or obviously incomplete code\n"
            "- Syntax errors\n\n"
            "PASS if the code is functional even if imperfect.\n"
            "Config files (.env, .json, .yaml) with placeholder values should always PASS.\n"
            "Return JSON: {\"status\": \"PASS\" or \"FAIL\", \"issues\": [\"...\"]}"
        )
        try:
            result = await call_model(
                "verifier", prompt, json_schema_hint=VERIFIER_SCHEMA_HINT
            )
            return VerifierReport.model_validate(safe_json_loads(result.text))
        except Exception:
            return None

    def _deterministic_check(self, worker_result: WorkerResult) -> VerifierReport:
        """Basic structural checks that don't need the LLM."""
        issues: list[str] = []

        if worker_result.status != "completed":
            issues.append(
                f"Worker task {worker_result.task_id} status is '{worker_result.status}', expected 'completed'."
            )
        if not worker_result.artifact.filename:
            issues.append("Artifact filename is empty.")
        if not worker_result.artifact.content.strip():
            issues.append("Artifact content is empty.")
        if len(worker_result.artifact.content.strip()) < 20:
            issues.append("Artifact content is suspiciously short (< 20 chars).")

        return VerifierReport(
            status="PASS" if not issues else "FAIL", issues=issues
        )

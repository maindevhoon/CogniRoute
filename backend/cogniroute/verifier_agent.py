from __future__ import annotations

from .llm import safe_json_loads
from .schemas import TaskGraph, VerifierReport, WorkerResult
from .services.llm import call_model
from .state.plan import parse_implementation_plan


VERIFIER_SCHEMA_HINT = """{
  "status": "PASS|FAIL",
  "issues": ["string"]
}"""


class VerifierAgent:
    """
    Single-pass verifier for the first CogniRoute loop.
    """

    async def run(
        self,
        *,
        task_graph: TaskGraph,
        worker_result: WorkerResult,
        plan_markdown: str,
        contracts_markdown: str,
    ) -> VerifierReport:
        model_report = await self._run_model(
            task_graph=task_graph,
            worker_result=worker_result,
            plan_markdown=plan_markdown,
            contracts_markdown=contracts_markdown,
        )
        if model_report is not None and model_report.status == "FAIL":
            return model_report

        issues: list[str] = []

        if worker_result.status != "completed":
            issues.append(f"Worker task {worker_result.task_id} did not complete.")
        if not worker_result.artifact.filename:
            issues.append("Artifact filename is empty.")
        if not worker_result.artifact.content.strip():
            issues.append("Artifact content is empty.")
        if "Frontend Artifact Contract" not in contracts_markdown:
            issues.append("System contracts are missing the frontend artifact contract.")

        node_ids = {node.id for node in task_graph.nodes}
        for node in task_graph.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    issues.append(f"Task {node.id} depends on missing task {dep}.")

        plan = parse_implementation_plan(plan_markdown)
        completed = {item.text.split(":", 1)[0] for item in plan.all_items() if item.status.value == "done"}
        if worker_result.task_id not in completed:
            issues.append(f"Checklist item for {worker_result.task_id} is not marked complete.")

        return VerifierReport(status="PASS" if not issues else "FAIL", issues=issues)

    async def _run_model(
        self,
        *,
        task_graph: TaskGraph,
        worker_result: WorkerResult,
        plan_markdown: str,
        contracts_markdown: str,
    ) -> VerifierReport | None:
        prompt = (
            "Validate this single CogniRoute execution checkpoint. "
            "Do not replan. Do not request retries. Return PASS or FAIL only.\n\n"
            f"Task graph JSON:\n{task_graph.model_dump_json()}\n\n"
            f"Worker result JSON:\n{worker_result.model_dump_json()}\n\n"
            f"Implementation plan markdown:\n{plan_markdown}\n\n"
            f"System contracts markdown:\n{contracts_markdown}\n"
        )
        try:
            result = await call_model("verifier", prompt, json_schema_hint=VERIFIER_SCHEMA_HINT)
            return VerifierReport.model_validate(safe_json_loads(result.text))
        except Exception:
            return None

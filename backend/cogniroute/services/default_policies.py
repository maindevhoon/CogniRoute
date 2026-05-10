from __future__ import annotations

from ..llm import LlmRole
from ..prompts.architect import ARCHITECT_SYSTEM_PROMPT
from ..prompts.verifier import VERIFIER_SYSTEM_PROMPT
from .model_router import RolePolicy


def default_role_policies(*, architect_model: str, worker_model: str, verifier_model: str) -> dict[LlmRole, RolePolicy]:
    """
    Defaults tuned for readability and predictable outputs.

    These are deliberately conservative: low temperature, explicit role prompts,
    and small capability hints for UI/telemetry.
    """

    return {
        LlmRole.architect: RolePolicy(
            model=architect_model,
            system_prompt=ARCHITECT_SYSTEM_PROMPT,
            temperature=0.2,
            capabilities={
                "task": "plan",
                "output": "structured_task_graph_json",
                "constraints": ["sequential_orchestration_only", "no_autonomous_retries"],
            },
        ),
        LlmRole.worker: RolePolicy(
            model=worker_model,
            system_prompt=(
                "You are a CogniRoute Worker. Execute ONLY the assigned task.\n"
                "Use ONLY the provided scoped context. Do not invent dependencies.\n"
                "Return a concise JSON object of artifacts."
            ),
            temperature=0.1,
            capabilities={
                "task": "execute_scoped_node",
                "output": "json_artifacts",
                "constraints": ["no_frontend_work_yet", "no_filesystem_writes_yet"],
            },
        ),
        LlmRole.verifier: RolePolicy(
            model=verifier_model,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            temperature=0.0,
            capabilities={
                "task": "checkpoint_validation",
                "output": "verifier_report_json",
                "constraints": ["no_recursive_loops", "no_autonomous_retries"],
            },
        ),
    }


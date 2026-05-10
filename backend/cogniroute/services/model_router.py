from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..llm import LlmCall, LlmRole


@dataclass(frozen=True)
class RolePolicy:
    """
    Single place to define how roles map to model + prompt + temperature.

    Keep this intentionally small: it's the "believable cognitive scheduling"
    dial for a hackathon demo, not a production policy engine.
    """

    model: str
    system_prompt: str
    temperature: float
    capabilities: dict[str, Any]


class ModelRouter:
    """
    Role-based routing: role -> (model, system, temperature, capabilities).

    Phase 1: deterministic policy; Phase 2: orchestration will use this.
    """

    def __init__(
        self,
        *,
        architect: RolePolicy,
        worker: RolePolicy,
        verifier: RolePolicy,
    ) -> None:
        self._policies = {
            LlmRole.architect: architect,
            LlmRole.worker: worker,
            LlmRole.verifier: verifier,
        }

    def build_call(
        self,
        *,
        role: LlmRole,
        user_prompt: str,
        json_schema_hint: Optional[str] = None,
    ) -> LlmCall:
        p = self._policies[role]
        return LlmCall(
            role=role,
            user_prompt=user_prompt,
            system_prompt=p.system_prompt,
            model=p.model,
            temperature=p.temperature,
            json_schema_hint=json_schema_hint,
        )

    def capabilities_for(self, role: LlmRole) -> dict[str, Any]:
        return dict(self._policies[role].capabilities)


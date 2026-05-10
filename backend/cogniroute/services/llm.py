from __future__ import annotations

from typing import Optional

from app.settings import settings
from ..llm import LlmCall, LlmResult, LlmRole, OpenAICompatibleClient


SYSTEM_PROMPTS: dict[LlmRole, str] = {
    LlmRole.architect: (
        "You are the CogniRoute Architect. Convert requests into compact, "
        "sequential implementation plans with scoped worker tasks. Return only "
        "the requested artifact."
    ),
    LlmRole.worker: (
        "You are a CogniRoute Worker. Execute only the provided scoped task. "
        "Do not use repository-wide context. Return only the requested artifact."
    ),
    LlmRole.verifier: (
        "You are the CogniRoute Verifier. Validate one completed step against "
        "the contracts. Return PASS or FAIL with concrete issues."
    ),
}

ROLE_MODELS: dict[LlmRole, str] = {
    LlmRole.architect: settings.architect_model,
    LlmRole.worker: settings.worker_model,
    LlmRole.verifier: settings.verifier_model,
}

ROLE_TEMPERATURES: dict[LlmRole, float] = {
    LlmRole.architect: 0.1,
    LlmRole.worker: 0.1,
    LlmRole.verifier: 0.0,
}


ROLE_ENDPOINTS: dict[LlmRole, Optional[str]] = {
    LlmRole.architect: settings.architect_base_url,
    LlmRole.worker: settings.worker_base_url,
    LlmRole.verifier: settings.verifier_base_url,
}


def _coerce_role(role: str | LlmRole) -> LlmRole:
    if isinstance(role, LlmRole):
        return role
    return LlmRole(role)


def make_client(*, base_url: Optional[str] = None, api_key: Optional[str] = None) -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url=base_url or settings.openai_base_url,
        api_key=api_key if api_key is not None else settings.openai_api_key,
        timeout_s=settings.llm_timeout_s,
    )


async def call_model(
    role: str | LlmRole,
    user_prompt: str,
    *,
    json_schema_hint: Optional[str] = None,
    base_url: Optional[str] = None,
) -> LlmResult:
    """
    Canonical role-routed inference entry point.

    The role decides the system prompt, model, and temperature. The base URL
    remains configurable so the same code can target vLLM or any compatible
    OpenAI-style endpoint.
    """

    llm_role = _coerce_role(role)
    call = LlmCall(
        role=llm_role,
        user_prompt=user_prompt,
        system_prompt=SYSTEM_PROMPTS[llm_role],
        model=ROLE_MODELS[llm_role],
        temperature=ROLE_TEMPERATURES[llm_role],
        json_schema_hint=json_schema_hint,
    )
    role_base_url = base_url or ROLE_ENDPOINTS[llm_role] or settings.openai_base_url
    return await make_client(base_url=role_base_url).call_model(call=call)

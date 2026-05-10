from __future__ import annotations

from typing import Optional

from app.settings import settings
from ..llm import LlmCall, LlmResult, LlmRole, OpenAICompatibleClient


SYSTEM_PROMPTS: dict[LlmRole, str] = {
    LlmRole.architect: (
        "You are the CogniRoute Architect — a senior software architect.\n"
        "Convert user requests into structured task graphs where each task = one file.\n"
        "Be specific about what each file should contain and how files relate to each other.\n"
        "Include concrete details: exact import paths, function names, class names.\n"
        "Return only valid JSON matching the provided schema."
    ),
    LlmRole.worker: (
        "You are a senior software engineer generating ONE complete source file.\n"
        "CRITICAL RULES:\n"
        "1. Write COMPLETE, PRODUCTION-READY code — no placeholders, no TODOs, no '...'.\n"
        "2. Include ALL imports at the top of the file.\n"
        "3. If other project files are provided as context, import from them correctly.\n"
        "4. Implement ALL functions with real logic — never raise NotImplementedError.\n"
        "5. For .env files: use realistic default values (e.g. sqlite:///./app.db).\n"
        "6. Return ONLY valid JSON with the complete file content in the 'content' field.\n"
        "7. Do NOT add markdown formatting or backticks inside the JSON content field.\n"
        "8. Make sure the JSON is valid — escape special characters properly."
    ),
    LlmRole.verifier: (
        "You are a pragmatic code reviewer. Your job is to catch REAL bugs only.\n"
        "PASS the file if it is functional and reasonably complete.\n"
        "FAIL only for:\n"
        "- Missing imports that would cause runtime errors\n"
        "- Syntax errors\n"
        "- Functions with no implementation (empty body or just 'pass')\n"
        "- Truncated/incomplete code\n"
        "DO NOT fail for:\n"
        "- Style preferences or naming conventions\n"
        "- Placeholder values in .env or config files (these are expected)\n"
        "- Missing type hints\n"
        "- Using sync vs async patterns\n"
        "- Minor architectural disagreements\n"
        "Return only valid JSON: {\"status\": \"PASS\" or \"FAIL\", \"issues\": [...]}"
    ),
}

ROLE_MODELS: dict[LlmRole, str] = {
    LlmRole.architect: settings.architect_model,
    LlmRole.worker: settings.worker_model,
    LlmRole.verifier: settings.verifier_model,
}

ROLE_TEMPERATURES: dict[LlmRole, float] = {
    LlmRole.architect: 0.1,
    LlmRole.worker: 0.2,
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

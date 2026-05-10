from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import httpx


class LlmRole(str, Enum):
    """
    Logical roles in CogniRoute.

    The role is the *primary* dial: it selects a model, a system prompt,
    temperature, and a capability posture (e.g., "planner" vs "executor").
    """

    architect = "architect"
    worker = "worker"
    verifier = "verifier"


@dataclass(frozen=True)
class LlmCall:
    role: LlmRole
    user_prompt: str
    system_prompt: str
    model: str
    temperature: float
    json_schema_hint: Optional[str] = None
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class LlmResult:
    text: str
    meta: dict[str, Any]


class LlmClient:
    """
    Minimal role-routed LLM abstraction.

    Phase 1: Only supports chat-completions style, OpenAI-compatible gateways.
    Phase 2: orchestration will depend on this module.
    """

    def enabled(self) -> bool:  # pragma: no cover
        return False

    async def call_model(self, *, call: LlmCall) -> LlmResult:  # pragma: no cover
        raise NotImplementedError


class OpenAICompatibleClient(LlmClient):
    """
    OpenAI-compatible client wrapper (vLLM-ready).

    Notes:
    - vLLM's OpenAI server typically exposes `/v1/chat/completions`.
    - To keep Phase 1 additive and dependency-light, we only implement the subset
      we need: messages -> one text output.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str],
        api_key: Optional[str] = None,
        chat_completions_path: str = "/chat/completions",
        timeout_s: float = 60.0,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else None
        self._api_key = api_key
        self._path = chat_completions_path
        self._timeout_s = timeout_s

    def enabled(self) -> bool:
        return bool(self._base_url)

    async def call_model(self, *, call: LlmCall) -> LlmResult:
        if not self.enabled():
            raise RuntimeError("LLM client not configured (base_url unset)")

        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        user_content = call.user_prompt
        if call.json_schema_hint:
            user_content += "\n\nReturn ONLY valid JSON.\nJSON schema hint:\n" + call.json_schema_hint

        payload = {
            "model": call.model,
            "temperature": call.temperature,
            "max_tokens": call.max_tokens or 4096,
            "messages": [
                {"role": "system", "content": call.system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        started = time.perf_counter()
        url = f"{self._base_url}{self._path}"
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        text = data["choices"][0]["message"]["content"]
        meta = {
            "role": call.role.value,
            "model": call.model,
            "temperature": call.temperature,
            "latency_ms": elapsed_ms,
            "usage": data.get("usage", {}),
            "raw_choice_finish_reason": data["choices"][0].get("finish_reason"),
            "base_url": self._base_url,
            "path": self._path,
        }
        return LlmResult(text=text, meta=meta)


def safe_json_loads(text: str) -> Any:
    """
    Tolerate fenced JSON blocks and extra prose from LLM output.
    """
    import re

    cleaned = text.strip()

    # Strip markdown code fences.
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence.
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()

    # If the text starts with prose before JSON, find the first { or [.
    if cleaned and cleaned[0] not in ('{', '['):
        brace = cleaned.find('{')
        bracket = cleaned.find('[')
        candidates = [i for i in (brace, bracket) if i >= 0]
        if candidates:
            start = min(candidates)
            cleaned = cleaned[start:]

    # If there's trailing text after the JSON, find the matching close.
    if cleaned.startswith('{'):
        depth = 0
        for i, c in enumerate(cleaned):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    cleaned = cleaned[:i + 1]
                    break
    elif cleaned.startswith('['):
        depth = 0
        for i, c in enumerate(cleaned):
            if c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    cleaned = cleaned[:i + 1]
                    break

    return json.loads(cleaned)


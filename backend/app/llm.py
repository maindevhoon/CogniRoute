from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx

from .settings import settings


@dataclass(frozen=True)
class LlmResult:
    text: str
    meta: dict[str, Any]


class OpenAICompatibleClient:
    """
    Minimal OpenAI-compatible chat client.

    MVP note: This is intentionally tiny and optional. If no base URL is set,
    CogniRoute runs deterministic mock planning/execution for demo stability.
    """

    def __init__(self) -> None:
        self.base_url = settings.openai_base_url
        self.api_key = settings.openai_api_key

    def enabled(self) -> bool:
        return bool(self.base_url)

    async def chat_json(self, *, model: str, system: str, user: str, json_schema_hint: str) -> LlmResult:
        if not self.enabled():
            raise RuntimeError("LLM client not configured (COGNIROUTE_OPENAI_BASE_URL unset)")

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": user
                    + "\n\nReturn ONLY valid JSON.\nJSON schema hint:\n"
                    + json_schema_hint,
                },
            ],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(f"{self.base_url.rstrip('/')}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()

        text = data["choices"][0]["message"]["content"]
        meta = {
            "model": model,
            "usage": data.get("usage", {}),
            "raw_choice_finish_reason": data["choices"][0].get("finish_reason"),
        }
        return LlmResult(text=text, meta=meta)


def safe_json_loads(text: str) -> Any:
    # Tolerate fenced code blocks in some gateways.
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()
    return json.loads(cleaned)


llm_client = OpenAICompatibleClient()


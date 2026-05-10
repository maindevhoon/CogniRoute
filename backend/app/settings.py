from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COGNIROUTE_", extra="ignore")

    # vLLM/OpenAI-compatible endpoints. Configure in deployment env vars.
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    architect_base_url: Optional[str] = None
    verifier_base_url: Optional[str] = None
    worker_base_url: Optional[str] = None
    llm_timeout_s: float = 10.0

    architect_model: str = "Qwen/Qwen2.5-32B-Instruct"
    worker_model: str = "Qwen/Qwen2.5-7B-Instruct"
    verifier_model: str = "Qwen/Qwen2.5-32B-Instruct"


settings = Settings()

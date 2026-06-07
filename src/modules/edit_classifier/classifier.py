from __future__ import annotations

import os
from typing import Any

from toolkit.edit_classifier import LLMEditClassifier


DEFAULT_PROMPT_PATH = "config/prompts/edit_classifier.txt"


def build_edit_classifier(
    llm_client: Any,
    llm_providers_config: dict[str, Any],
    tier: Any = "commodity",
    attribution: str | None = None,
) -> LLMEditClassifier | None:
    """Build an LLMEditClassifier from Diplomat's pipeline.yaml provider config.

    Reads the `{"primary": {provider, api_key_env, models}}` shape that
    Diplomat's `pipeline.yaml` uses and translates it into the toolkit
    primitive's constructor kwargs. Returns ``None`` when no primary
    provider is configured (mirrors the historical optional-build pattern
    used by other Diplomat module factories).
    """
    primary = llm_providers_config.get("primary", {})
    if not primary:
        return None

    return LLMEditClassifier(
        llm_client=llm_client,
        llm_config=_subsystem_llm_config(primary, tier),
        tier=tier,
        prompt_path=DEFAULT_PROMPT_PATH,
        attribution=attribution,
    )


def _subsystem_llm_config(primary: dict[str, Any], tier: Any) -> dict[str, Any]:
    api_key_env = primary.get("api_key_env", "")
    models = primary.get("models", {})
    model_name = ""
    if isinstance(models, dict):
        model_name = models.get(tier, "")

    return {
        "provider": primary.get("provider", "openai"),
        "models": {tier: model_name},
        "api_key": os.getenv(api_key_env, "") if api_key_env else "",
    }


__all__ = [
    "DEFAULT_PROMPT_PATH",
    "build_edit_classifier",
]

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolkit.structured_llm import structured_call

from modules.extraction import load_prompt
from modules.edit_classifier.types import EditClassification


EDIT_CLASSIFICATION_CATEGORIES = (
    "tone_softer",
    "tone_harder",
    "commitment_removed",
    "ambiguity_added",
    "constraint_enforcement",
    "persona_correction",
)

EDIT_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["category", "confidence", "rationale"],
    "properties": {
        "category": {"type": "string", "enum": list(EDIT_CLASSIFICATION_CATEGORIES)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string", "minLength": 1},
    },
}

DEFAULT_PROMPT_PATH = Path("config/prompts/edit_classifier.txt")


class LLMEditClassifier:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        tier: Any,
        prompt_path: str | Path = DEFAULT_PROMPT_PATH,
        attribution: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.system_prompt = load_prompt(prompt_path)
        self.classifier_model = _resolve_classifier_model(llm_config, tier)
        self.attribution = attribution

    async def classify(
        self,
        original: str,
        edited: str,
        edit_notes: str | None,
    ) -> EditClassification:
        if not original.strip():
            raise ValueError("original must not be blank")
        if not edited.strip():
            raise ValueError("edited must not be blank")

        user_prompt = _build_user_prompt(original, edited, edit_notes)

        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=EDIT_CLASSIFICATION_SCHEMA,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            max_retries=1,
            purpose="edit_classification",
            attribution=self.attribution,
        )

        if not result.success:
            raise RuntimeError(result.error or "Edit classification failed")

        data = result.data or {}
        category = data.get("category", "")
        confidence = data.get("confidence", 0.0)
        rationale = data.get("rationale", "")

        if category not in EDIT_CLASSIFICATION_CATEGORIES:
            raise ValueError(f"Invalid edit classification category: {category}")
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            raise ValueError("Edit classification confidence must be between 0 and 1")
        if not isinstance(rationale, str) or not rationale.strip():
            raise ValueError("Edit classification rationale must not be blank")

        return EditClassification(
            category=category,
            confidence=float(confidence),
            rationale=rationale.strip(),
            classifier_model=self.classifier_model,
            classified_at=datetime.now(timezone.utc),
        )


def build_edit_classifier(
    llm_client: Any,
    llm_providers_config: dict[str, Any],
    tier: Any = "commodity",
    attribution: str | None = None,
) -> LLMEditClassifier | None:
    primary = llm_providers_config.get("primary", {})
    if not primary:
        return None

    return LLMEditClassifier(
        llm_client=llm_client,
        llm_config=_subsystem_llm_config(primary, tier),
        tier=tier,
        attribution=attribution,
    )


def _build_user_prompt(original: str, edited: str, edit_notes: str | None) -> str:
    notes = edit_notes.strip() if isinstance(edit_notes, str) and edit_notes.strip() else "[none]"
    return "\n\n".join(
        [
            "Classify the edit into exactly one category.",
            "Original draft:",
            original.strip(),
            "Edited draft:",
            edited.strip(),
            "Edit notes:",
            notes,
            "Return the category, confidence, and a short rationale.",
        ]
    )


def _resolve_classifier_model(llm_config: Any, tier: Any) -> str:
    models = llm_config.get("models", {}) if isinstance(llm_config, dict) else {}
    if isinstance(models, dict):
        model = models.get(tier)
        if isinstance(model, str) and model.strip():
            return model.strip()
        if isinstance(tier, str) and tier.strip():
            return tier.strip()
    return "unknown"


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
    "EDIT_CLASSIFICATION_SCHEMA",
    "EDIT_CLASSIFICATION_CATEGORIES",
    "LLMEditClassifier",
    "build_edit_classifier",
]

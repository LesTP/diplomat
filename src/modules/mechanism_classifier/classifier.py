from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from toolkit.structured_llm import load_schema, structured_call

from modules.extraction import load_prompt

DEFAULT_PROMPT_PATH = "config/prompts/mechanism_classifier.txt"
DEFAULT_SCHEMA_PATH = "config/schemas/mechanism_classifier.json"


def derive_label(answers: Mapping[str, Any]) -> str:
    """Derive the final mechanism label from the judge's five boolean answers."""
    q1 = bool(answers.get("q1", False))
    q2 = bool(answers.get("q2", False))
    q3 = bool(answers.get("q3", False))
    q4 = bool(answers.get("q4", False))
    q5 = bool(answers.get("q5", False))

    if q5:
        return "closed"
    if q4:
        return "incoherence"
    if q3 and q1:
        return "strategic_refusal"
    if q2 and q1:
        return "near_miss"
    return "breakdown"


def schema_path() -> Path:
    """Return the packaged schema location for the mechanism judge."""
    return Path(DEFAULT_SCHEMA_PATH)


def cohens_kappa(labels_a: Any, labels_b: Any) -> float:
    """Return Cohen's kappa for two equally sized label sequences."""
    seq_a = list(labels_a)
    seq_b = list(labels_b)
    if len(seq_a) != len(seq_b):
        raise ValueError("cohens_kappa requires label sequences of equal length")
    if not seq_a:
        raise ValueError("cohens_kappa requires at least one label pair")
    if seq_a == seq_b:
        return 1.0

    total = len(seq_a)
    counts_a = Counter(seq_a)
    counts_b = Counter(seq_b)
    observed = sum(left == right for left, right in zip(seq_a, seq_b)) / total
    expected = sum(
        (counts_a[label] / total) * (counts_b[label] / total)
        for label in counts_a.keys() | counts_b.keys()
    )
    if expected == 1.0:
        return 1.0 if observed == 1.0 else 0.0

    kappa = (observed - expected) / (1.0 - expected)
    if kappa < -1.0:
        return -1.0
    if kappa > 1.0:
        return 1.0
    return float(kappa)


class MechanismClassifier:
    """LLM-backed classifier for negotiation mechanisms."""

    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        tier: Any,
        prompt_path: str | Path,
        attribution: str | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.system_prompt = load_prompt(prompt_path)
        self.schema = load_schema(DEFAULT_SCHEMA_PATH)
        self.attribution = attribution

    async def classify(self, result: dict[str, Any]) -> str:
        user_prompt = self._build_user_prompt(result)
        structured = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=self.schema,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            max_retries=1,
            purpose="mechanism",
            attribution=self.attribution,
        )
        if not structured.success:
            raise RuntimeError(structured.error or "Mechanism classification failed")
        return derive_label(structured.data or {})

    def _build_user_prompt(self, result: dict[str, Any]) -> str:
        transcript = result.get("transcript", [])
        rounds_completed = result.get("rounds_completed")
        round_responses = result.get("round_responses", {})
        final_round = round_responses.get(str(rounds_completed), {})

        return "\n\n".join(
            [
                "Transcript:",
                _dump_json(transcript),
                f"Final round responses for round {rounds_completed}:",
                _dump_json(final_round),
            ]
        )


def build_mechanism_classifier(
    llm_client: Any,
    llm_providers_config: dict[str, Any],
    tier: Any = "commodity",
    attribution: str | None = None,
) -> MechanismClassifier | None:
    """Build a mechanism classifier from Diplomat's pipeline provider config."""
    primary = llm_providers_config.get("primary", {})
    if not primary:
        return None

    return MechanismClassifier(
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


def _dump_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)

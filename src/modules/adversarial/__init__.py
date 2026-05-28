from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toolkit.structured_llm import structured_complete, validate_json_schema

from modules.extraction import load_prompt, load_schema, parse_json_object


@dataclass(frozen=True)
class AdversarialResult:
    success: bool
    analysis: dict[str, Any] | None
    error: str | None


class LLMAdversarialReader:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        tier: Any,
        prompt_path: str | Path,
        schema_path: str | Path,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.system_prompt = load_prompt(prompt_path)
        self.schema = load_schema(schema_path)

    async def read(self, draft: str) -> AdversarialResult:
        try:
            if not draft.strip():
                raise ValueError("Draft must not be blank")
            response_text = await structured_complete(
                self.llm_client, self.llm_config, self.tier,
                self._build_messages(draft),
            )
            analysis = validate_adversarial_analysis(
                parse_json_object(response_text),
                self.schema,
            )
        except Exception as exc:
            return AdversarialResult(success=False, analysis=None, error=str(exc))

        return AdversarialResult(success=True, analysis=analysis, error=None)

    def _build_messages(self, draft: str) -> list[dict[str, str]]:
        user_prompt = "\n\n".join(
            [
                "Adversarial analysis JSON schema:",
                json.dumps(self.schema, sort_keys=True),
                "Draft response:",
                draft,
            ]
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]


def validate_adversarial_analysis(
    analysis_data: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    validate_json_schema(
        analysis_data, schema, label="Adversarial analysis failed schema validation"
    )
    return analysis_data


__all__ = [
    "AdversarialResult",
    "LLMAdversarialReader",
    "validate_adversarial_analysis",
]

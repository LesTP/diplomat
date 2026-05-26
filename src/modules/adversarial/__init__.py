from __future__ import annotations

import json
from dataclasses import dataclass
from inspect import isawaitable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

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
            response_text = await self._complete(self._build_messages(draft))
            analysis = validate_adversarial_analysis(
                parse_json_object(response_text),
                self.schema,
            )
        except Exception as exc:
            return AdversarialResult(success=False, analysis=None, error=str(exc))

        return AdversarialResult(success=True, analysis=analysis, error=None)

    async def _complete(self, messages: list[dict[str, str]]) -> str:
        response = self.llm_client.complete(
            messages=messages,
            config=self.llm_config,
            tier=self.tier,
        )
        if isawaitable(response):
            response = await response
        if not isinstance(response, str):
            raise ValueError("LLM response must be plain text")
        return response

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
    try:
        Draft202012Validator(schema).validate(analysis_data)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise ValueError(
            f"Adversarial analysis failed schema validation{location}: {exc.message}"
        ) from exc
    return analysis_data


__all__ = [
    "AdversarialResult",
    "LLMAdversarialReader",
    "validate_adversarial_analysis",
]

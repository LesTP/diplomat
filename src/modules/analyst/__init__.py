from __future__ import annotations

import json
from datetime import datetime, timezone
from inspect import isawaitable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from modules.extraction import load_prompt, load_schema, parse_json_object
from modules.types import AnalysisResult


class LLMAnalyst:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        tier: Any,
        prompt_path: str | Path,
        schema_path: str | Path,
        provider_id: str,
    ) -> None:
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.system_prompt = load_prompt(prompt_path)
        self.schema = load_schema(schema_path)
        self.provider_id = provider_id

    async def analyze(self, state: dict[str, Any]) -> AnalysisResult:
        timestamp = datetime.now(timezone.utc)
        try:
            response_text = await self._complete(self._build_messages(state))
            report = validate_intelligence_report(
                parse_json_object(response_text),
                self.schema,
            )
        except Exception as exc:
            return AnalysisResult(
                success=False,
                provider_id=self.provider_id,
                report=None,
                error=str(exc),
                timestamp=timestamp,
            )

        return AnalysisResult(
            success=True,
            provider_id=self.provider_id,
            report=report,
            error=None,
            timestamp=timestamp,
        )

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

    def _build_messages(self, state: dict[str, Any]) -> list[dict[str, str]]:
        user_prompt = "\n\n".join(
            [
                "Intelligence JSON schema:",
                json.dumps(self.schema, sort_keys=True),
                "Current state snapshot:",
                json.dumps(state, sort_keys=True),
            ]
        )
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]


def validate_intelligence_report(
    report_data: dict[str, Any], schema: dict[str, Any]
) -> dict[str, Any]:
    try:
        Draft202012Validator(schema).validate(report_data)
    except ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path)
        location = f" at {path}" if path else ""
        raise ValueError(
            f"Intelligence report failed schema validation{location}: {exc.message}"
        ) from exc
    return report_data


__all__ = ["LLMAnalyst", "validate_intelligence_report"]

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolkit.structured_llm import structured_complete, validate_json_schema

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
            response_text = await structured_complete(
                self.llm_client, self.llm_config, self.tier,
                self._build_messages(state),
            )
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
    validate_json_schema(
        report_data, schema, label="Intelligence report failed schema validation"
    )
    return report_data


__all__ = ["LLMAnalyst", "validate_intelligence_report"]

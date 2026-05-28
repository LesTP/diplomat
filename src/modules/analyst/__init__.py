from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from toolkit.structured_llm import structured_call

from modules.extraction import load_prompt, load_schema
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

        user_prompt = "\n\n".join(
            [
                "Current state snapshot:",
                json.dumps(state, sort_keys=True),
            ]
        )

        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=self.schema,
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            max_retries=1,
        )

        if not result.success:
            return AnalysisResult(
                success=False,
                provider_id=self.provider_id,
                report=None,
                error=result.error,
                timestamp=timestamp,
            )

        return AnalysisResult(
            success=True,
            provider_id=self.provider_id,
            report=result.data,
            error=None,
            timestamp=timestamp,
        )


__all__ = ["LLMAnalyst"]

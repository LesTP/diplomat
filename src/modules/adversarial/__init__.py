from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from toolkit.structured_llm import structured_call

from modules.extraction import load_prompt, load_schema


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
        if not draft.strip():
            return AdversarialResult(
                success=False, analysis=None, error="Draft must not be blank"
            )

        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=self.schema,
            system_prompt=self.system_prompt,
            user_prompt=f"Draft response:\n\n{draft}",
            max_retries=1,
            purpose="adversarial",
        )

        if not result.success:
            return AdversarialResult(
                success=False, analysis=None, error=result.error
            )

        return AdversarialResult(
            success=True, analysis=result.data, error=None
        )


__all__ = [
    "AdversarialResult",
    "LLMAdversarialReader",
]

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from toolkit.structured_llm import structured_call

from modules.context_assembler import DecisionContext


_GENERATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["response", "reasoning"],
    "properties": {
        "response": {"type": "string", "minLength": 1},
        "reasoning": {"type": "string", "minLength": 1},
    },
}


@dataclass(frozen=True)
class GenerationResult:
    success: bool
    response_text: str | None
    reasoning: str | None
    raw_response: dict[str, Any] | None
    error: str | None


class LLMGenerator:
    def __init__(
        self,
        llm_client: Any,
        llm_config: Any,
        tier: Any,
        max_tokens: int = 1024,
        review_gate_enabled: bool = True,
    ) -> None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        self.llm_client = llm_client
        self.llm_config = llm_config
        self.tier = tier
        self.max_tokens = max_tokens
        self.review_gate_enabled = review_gate_enabled

    async def generate(
        self,
        context: DecisionContext,
        *,
        purpose: str = "generation",
        attribution: str | None = None,
    ) -> GenerationResult:
        return await self.generate_with_metadata(
            context,
            purpose=purpose,
            attribution=attribution,
        )

    async def generate_with_metadata(
        self,
        context: DecisionContext,
        *,
        purpose: str = "generation",
        attribution: str | None = None,
    ) -> GenerationResult:
        if self.review_gate_enabled:
            return await self._generate_json(
                context,
                purpose=purpose,
                attribution=attribution,
            )
        return await self._generate_plain(
            context,
            purpose=purpose,
            attribution=attribution,
        )

    async def _generate_json(
        self,
        context: DecisionContext,
        *,
        purpose: str,
        attribution: str | None,
    ) -> GenerationResult:
        result = await structured_call(
            self.llm_client,
            self.llm_config,
            self.tier,
            schema=_GENERATION_SCHEMA,
            system_prompt=context.system_prompt,
            user_prompt=context.user_prompt,
            max_retries=1,
            purpose=purpose,
            attribution=attribution,
        )

        if not result.success:
            return GenerationResult(
                success=False,
                response_text=None,
                reasoning=None,
                raw_response=None,
                error=result.error,
            )

        data = result.data or {}
        response_text = data.get("response", "")
        reasoning = data.get("reasoning", "")

        if not response_text.strip():
            return GenerationResult(
                success=False,
                response_text=None,
                reasoning=None,
                raw_response=data,
                error="LLM response JSON must include a nonblank response",
            )

        return GenerationResult(
            success=True,
            response_text=response_text.strip(),
            reasoning=reasoning.strip(),
            raw_response=data,
            error=None,
        )

    async def _generate_plain(
        self,
        context: DecisionContext,
        *,
        purpose: str,
        attribution: str | None,
    ) -> GenerationResult:
        from inspect import isawaitable

        try:
            response = self.llm_client.complete(
                messages=[
                    {"role": "system", "content": context.system_prompt},
                    {"role": "user", "content": context.user_prompt},
                ],
                config=self.llm_config,
                tier=self.tier,
                max_tokens=self.max_tokens,
                purpose=purpose,
                attribution=attribution,
            )
            if isawaitable(response):
                response = await response
            if not isinstance(response, str):
                raise ValueError("LLM response must be plain text")
            if not response.strip():
                raise ValueError("LLM response must not be blank")
        except Exception as exc:
            return GenerationResult(
                success=False,
                response_text=None,
                reasoning=None,
                raw_response=None,
                error=str(exc),
            )

        return GenerationResult(
            success=True,
            response_text=response.strip(),
            reasoning=None,
            raw_response=None,
            error=None,
        )


__all__ = ["GenerationResult", "LLMGenerator"]

from __future__ import annotations

import json
from dataclasses import dataclass
from inspect import isawaitable
from typing import Any

from modules.context_assembler import DecisionContext


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

    async def generate(self, context: DecisionContext) -> GenerationResult:
        try:
            response = await self._complete(self._build_messages(context))
            response_text, raw_response = self._normalize_response(response)
            if not response_text.strip():
                raise ValueError("LLM response must not be blank")
            if self.review_gate_enabled:
                response_text, reasoning, raw_response = self._parse_review_response(
                    response_text, raw_response
                )
            else:
                response_text = response_text.strip()
                reasoning = None
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
            response_text=response_text,
            reasoning=reasoning,
            raw_response=raw_response,
            error=None,
        )

    async def _complete(self, messages: list[dict[str, str]]) -> Any:
        response = self.llm_client.complete(
            messages=messages,
            config=self.llm_config,
            tier=self.tier,
            max_tokens=self.max_tokens,
        )
        if isawaitable(response):
            response = await response
        return response

    def _build_messages(self, context: DecisionContext) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": context.system_prompt},
            {"role": "user", "content": context.user_prompt},
        ]

    def _normalize_response(self, response: Any) -> tuple[str, dict[str, Any] | None]:
        if isinstance(response, str):
            return response, None
        if isinstance(response, dict):
            for key in ("text", "content", "response"):
                value = response.get(key)
                if isinstance(value, str):
                    return value, response
            raise ValueError("LLM response dict must contain text content")
        raise ValueError("LLM response must be plain text")

    def _parse_review_response(
        self, response_text: str, raw_response: dict[str, Any] | None
    ) -> tuple[str, str, dict[str, Any]]:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM response was not valid JSON: {exc.msg}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("LLM response JSON must be an object")

        response = parsed.get("response")
        reasoning = parsed.get("reasoning")
        if not isinstance(response, str) or not response.strip():
            raise ValueError("LLM response JSON must include a nonblank response")
        if not isinstance(reasoning, str):
            raise ValueError("LLM response JSON must include reasoning")

        debug_response = dict(raw_response or {})
        debug_response["parsed_json"] = parsed
        return response.strip(), reasoning.strip(), debug_response


__all__ = ["GenerationResult", "LLMGenerator"]

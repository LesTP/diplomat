from __future__ import annotations

import pytest

from modules.context_assembler import DecisionContext
from modules.generation import GenerationResult, LLMGenerator


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _context() -> DecisionContext:
    return DecisionContext(
        system_prompt="Faction persona",
        user_prompt="Generate the next message.",
        metadata={"round_number": 3},
    )


@pytest.mark.asyncio
async def test_successful_plain_text_generation():
    client = FakeLLMClient("  Austria, we can support Belgium this round.  ")
    generator = LLMGenerator(
        llm_client=client,
        llm_config={"provider": "anthropic"},
        tier="QUALITY",
        max_tokens=512,
        review_gate_enabled=False,
    )

    result = await generator.generate(_context())

    assert result == GenerationResult(
        success=True,
        response_text="Austria, we can support Belgium this round.",
        reasoning=None,
        raw_response=None,
        error=None,
    )


@pytest.mark.asyncio
async def test_llm_exception_success_false():
    generator = LLMGenerator(
        FakeLLMClient(RuntimeError("provider unavailable")),
        llm_config={},
        tier="QUALITY",
    )

    result = await generator.generate(_context())

    assert result.success is False
    assert result.response_text is None
    assert result.reasoning is None
    assert result.raw_response is None
    assert result.error == "provider unavailable"


@pytest.mark.asyncio
async def test_prompt_forwarding_to_llm_client():
    client = FakeLLMClient("Message")
    generator = LLMGenerator(client, llm_config={}, tier="QUALITY")

    await generator.generate(_context())

    assert client.calls[0]["messages"] == [
        {"role": "system", "content": "Faction persona"},
        {"role": "user", "content": "Generate the next message."},
    ]


@pytest.mark.asyncio
async def test_tier_config_and_max_tokens_forwarded():
    client = FakeLLMClient("Message")
    generator = LLMGenerator(
        client,
        llm_config={"provider": "openai"},
        tier="ECONOMY",
        max_tokens=2048,
    )

    await generator.generate(_context())

    assert client.calls[0]["config"] == {"provider": "openai"}
    assert client.calls[0]["tier"] == "ECONOMY"
    assert client.calls[0]["max_tokens"] == 2048


@pytest.mark.asyncio
async def test_raw_response_propagated_when_client_returns_dict():
    raw_response = {
        "text": "France, let us coordinate quietly.",
        "provider_id": "anthropic",
    }
    generator = LLMGenerator(FakeLLMClient(raw_response), llm_config={}, tier="QUALITY")

    result = await generator.generate(_context())

    assert result.success is True
    assert result.response_text == "France, let us coordinate quietly."
    assert result.raw_response == raw_response


@pytest.mark.asyncio
async def test_blank_plain_text_response_success_false():
    generator = LLMGenerator(FakeLLMClient("   "), llm_config={}, tier="QUALITY")

    result = await generator.generate(_context())

    assert result.success is False
    assert result.error == "LLM response must not be blank"

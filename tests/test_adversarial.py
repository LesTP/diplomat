from __future__ import annotations

import json

import pytest

from modules.adversarial import AdversarialResult, LLMAdversarialReader


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def prompt_path(tmp_path):
    path = tmp_path / "adversarial.txt"
    path.write_text("Read as an opposing faction.", encoding="utf-8")
    return path


@pytest.fixture
def schema_path(tmp_path):
    path = tmp_path / "adversarial.json"
    path.write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "reveals",
                    "commitments",
                    "exploitable",
                    "counter_moves",
                ],
                "properties": {
                    "reveals": {"type": "array", "items": {"type": "string"}},
                    "commitments": {"type": "array", "items": {"type": "string"}},
                    "exploitable": {"type": "array", "items": {"type": "string"}},
                    "counter_moves": {"type": "array", "items": {"type": "string"}},
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _analysis() -> dict:
    return {
        "reveals": ["We want Belgium cooperation."],
        "commitments": ["Support this round."],
        "exploitable": ["Opponent could demand specifics."],
        "counter_moves": ["Ask for a public commitment."],
    }


@pytest.mark.asyncio
async def test_successful_read_returns_result_contract(prompt_path, schema_path):
    reader = LLMAdversarialReader(
        llm_client=FakeLLMClient(json.dumps(_analysis())),
        llm_config={"provider": "openai"},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("We can support Belgium this round.")

    assert result == AdversarialResult(success=True, analysis=_analysis(), error=None)


@pytest.mark.asyncio
async def test_blank_draft_success_false_without_client_call(prompt_path, schema_path):
    client = FakeLLMClient("{}")
    reader = LLMAdversarialReader(
        client,
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("   ")

    assert result.success is False
    assert result.analysis is None
    assert result.error == "Draft must not be blank"
    assert client.calls == []


@pytest.mark.asyncio
async def test_llm_exception_success_false(prompt_path, schema_path):
    reader = LLMAdversarialReader(
        FakeLLMClient(RuntimeError("provider unavailable")),
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("A draft.")

    assert result.success is False
    assert result.analysis is None
    assert result.error == "provider unavailable"


@pytest.mark.asyncio
async def test_prompt_and_draft_forwarded_to_llm_client(prompt_path, schema_path):
    client = FakeLLMClient(json.dumps(_analysis()))
    reader = LLMAdversarialReader(
        client,
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    await reader.read("Germany, we should coordinate quietly.")

    messages = client.calls[0]["messages"]
    assert messages[0] == {
        "role": "system",
        "content": "Read as an opposing faction.",
    }
    assert messages[1]["role"] == "user"
    assert "Adversarial analysis JSON schema:" in messages[1]["content"]
    assert "Germany, we should coordinate quietly." in messages[1]["content"]


@pytest.mark.asyncio
async def test_config_and_tier_forwarded(prompt_path, schema_path):
    client = FakeLLMClient(json.dumps(_analysis()))
    reader = LLMAdversarialReader(
        client,
        llm_config={"provider": "openai"},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    await reader.read("A draft.")

    assert client.calls[0]["config"] == {"provider": "openai"}
    assert client.calls[0]["tier"] == "QUALITY"


@pytest.mark.asyncio
async def test_malformed_json_success_false(prompt_path, schema_path):
    reader = LLMAdversarialReader(
        FakeLLMClient("{invalid"),
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("A draft.")

    assert result.success is False
    assert result.analysis is None
    assert "not valid JSON" in result.error


@pytest.mark.asyncio
async def test_missing_required_key_success_false(prompt_path, schema_path):
    data = _analysis()
    del data["counter_moves"]
    reader = LLMAdversarialReader(
        FakeLLMClient(json.dumps(data)),
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("A draft.")

    assert result.success is False
    assert result.analysis is None
    assert "failed schema validation" in result.error


@pytest.mark.asyncio
async def test_wrong_value_type_success_false(prompt_path, schema_path):
    data = _analysis()
    data["reveals"] = "not an array"
    reader = LLMAdversarialReader(
        FakeLLMClient(json.dumps(data)),
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("A draft.")

    assert result.success is False
    assert result.analysis is None
    assert "failed schema validation at reveals" in result.error


@pytest.mark.asyncio
async def test_non_text_llm_response_success_false(prompt_path, schema_path):
    reader = LLMAdversarialReader(
        FakeLLMClient({"text": json.dumps(_analysis())}),
        llm_config={},
        tier="QUALITY",
        prompt_path=prompt_path,
        schema_path=schema_path,
    )

    result = await reader.read("A draft.")

    assert result.success is False
    assert result.analysis is None
    assert result.error == "LLM response must be plain text"

from __future__ import annotations

import json

import pytest

from modules.extraction import (
    ExtractionResult,
    OpenAIStructuredExtractor,
    RuleBasedExtractor,
    load_prompt,
    load_schema,
    parse_json_object,
    validate_state_patch,
)
from modules.types import StatePatch


SCHEMA_PATH = "config/schemas/state_patch.json"
PROMPT_PATH = "config/prompts/state_updater.txt"


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_extraction_result_exposes_success_patch_and_error_fields():
    patch = StatePatch({"promises": []})

    result = ExtractionResult(success=True, patch=patch)

    assert result.success is True
    assert result.patch == patch
    assert result.error is None


def test_public_exports_include_primary_and_fallback_extractors():
    import modules.extraction as extraction

    assert extraction.OpenAIStructuredExtractor is OpenAIStructuredExtractor
    assert extraction.RuleBasedExtractor is RuleBasedExtractor
    assert extraction.ExtractionResult is ExtractionResult


def test_configured_state_updater_prompt_loads_json_only_guidance():
    prompt = load_prompt(PROMPT_PATH)

    assert "Return ONLY valid JSON" in prompt
    assert "return {}" in prompt


def test_parse_json_object_returns_decoded_object():
    assert parse_json_object('{"promises": []}') == {"promises": []}


def test_parse_json_object_rejects_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_object("{invalid")


def test_parse_json_object_rejects_non_object_json():
    with pytest.raises(ValueError, match="must be an object"):
        parse_json_object("[]")


def test_validate_state_patch_returns_state_patch_for_valid_data():
    schema = load_schema(SCHEMA_PATH)

    patch = validate_state_patch(
        {
            "promises": [
                {
                    "promise_id": "p1",
                    "from_faction": "england",
                    "to_faction": "france",
                    "content": "Support France into Belgium.",
                }
            ]
        },
        schema,
    )

    assert patch == StatePatch(
        {
            "promises": [
                {
                    "promise_id": "p1",
                    "from_faction": "england",
                    "to_faction": "france",
                    "content": "Support France into Belgium.",
                }
            ]
        }
    )


def test_validate_state_patch_rejects_schema_violations():
    schema = load_schema(SCHEMA_PATH)

    with pytest.raises(ValueError, match="failed schema validation"):
        validate_state_patch(
            {"promises": [{"promise_id": "missing-required-fields"}]},
            schema,
        )


def test_validate_state_patch_accepts_empty_patch():
    assert validate_state_patch({}, load_schema(SCHEMA_PATH)) == StatePatch({})


@pytest.mark.asyncio
async def test_rule_based_extractor_extracts_simple_promise():
    extractor = RuleBasedExtractor(SCHEMA_PATH)

    result = await extractor.extract(
        "England promises France support into Belgium.",
        current_state={},
        trigger_type="message",
    )

    assert result.success is True
    assert result.error is None
    assert result.patch == StatePatch(
        {
            "promises": [
                {
                    "promise_id": "promise-england-promises-france-support-into-belgium",
                    "from_faction": "England",
                    "to_faction": "France",
                    "content": "support into Belgium",
                    "status": "pending",
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_rule_based_extractor_extracts_simple_coalition():
    extractor = RuleBasedExtractor(SCHEMA_PATH)

    result = await extractor.extract(
        "England and France form a coalition against Germany.",
        current_state={},
        trigger_type="message",
    )

    assert result.patch == StatePatch(
        {
            "coalitions": [
                {
                    "coalition_id": (
                        "coalition-england-and-france-form-a-coalition-against-germ"
                    ),
                    "faction_a": "England",
                    "faction_b": "France",
                    "confidence": 0.7,
                    "basis": "against Germany",
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_rule_based_extractor_extracts_simple_inconsistency():
    extractor = RuleBasedExtractor(SCHEMA_PATH)

    result = await extractor.extract(
        "Germany broke the non-aggression promise to Russia.",
        current_state={},
        trigger_type="intel_correction",
    )

    assert result.patch == StatePatch(
        {
            "inconsistencies": [
                {
                    "inconsistency_id": (
                        "inconsistency-germany-broke-the-non-aggression-promise-to-russ"
                    ),
                    "faction_id": "Germany",
                    "description": "the non-aggression promise to Russia",
                    "leverage_value": 0.5,
                    "spent": False,
                }
            ]
        }
    )


@pytest.mark.asyncio
async def test_rule_based_extractor_returns_empty_patch_when_no_pattern_matches():
    extractor = RuleBasedExtractor(SCHEMA_PATH)

    result = await extractor.extract(
        "The board is quiet this round.",
        current_state={},
        trigger_type="message",
    )

    assert result == ExtractionResult(success=True, patch=StatePatch({}))


@pytest.mark.asyncio
async def test_openai_structured_extractor_uses_prompt_context_and_commodity_tier(
    tmp_path,
):
    prompt_path = tmp_path / "state_updater.txt"
    prompt_path.write_text("Extract only valid state patch JSON.", encoding="utf-8")
    client = FakeLLMClient(
        json.dumps(
            {
                "promises": [
                    {
                        "promise_id": "p1",
                        "from_faction": "England",
                        "to_faction": "France",
                        "content": "Support into Belgium.",
                    }
                ]
            }
        )
    )
    extractor = OpenAIStructuredExtractor(
        llm_client=client,
        llm_config={"provider": "openai"},
        schema_path=SCHEMA_PATH,
        prompt_path=prompt_path,
        tier="COMMODITY",
    )

    result = await extractor.extract(
        "England promises France support into Belgium.",
        current_state={"promises": []},
        trigger_type="message",
    )

    assert result.success is True
    assert result.patch == StatePatch(
        {
            "promises": [
                {
                    "promise_id": "p1",
                    "from_faction": "England",
                    "to_faction": "France",
                    "content": "Support into Belgium.",
                }
            ]
        }
    )
    assert client.calls[0]["config"] == {"provider": "openai"}
    assert client.calls[0]["tier"] == "COMMODITY"
    # structured_call assembles schema + examples into the system prompt.
    system_prompt = client.calls[0]["messages"][0]["content"]
    assert "Extract only valid state patch JSON." in system_prompt
    assert "JSON Schema" in system_prompt
    assert "Example" in system_prompt
    user_prompt = client.calls[0]["messages"][1]["content"]
    assert '"promises": []' in user_prompt
    assert "Treat this as an observed game message." in user_prompt
    assert "England promises France" in user_prompt


@pytest.mark.asyncio
async def test_openai_structured_extractor_marks_intel_as_high_confidence(tmp_path):
    prompt_path = tmp_path / "state_updater.txt"
    prompt_path.write_text("Extract JSON.", encoding="utf-8")
    client = FakeLLMClient("{}")
    extractor = OpenAIStructuredExtractor(
        client,
        llm_config={},
        schema_path=SCHEMA_PATH,
        prompt_path=prompt_path,
        tier="COMMODITY",
    )

    await extractor.extract(
        "France did not agree to support England.",
        current_state={},
        trigger_type="intel_correction",
    )

    user_prompt = client.calls[0]["messages"][1]["content"]
    assert "[OPERATOR INTEL]" in user_prompt
    assert "high-confidence correction" in user_prompt


@pytest.mark.asyncio
async def test_openai_structured_extractor_reports_invalid_json(tmp_path):
    prompt_path = tmp_path / "state_updater.txt"
    prompt_path.write_text("Extract JSON.", encoding="utf-8")
    extractor = OpenAIStructuredExtractor(
        FakeLLMClient("{invalid"),
        llm_config={},
        schema_path=SCHEMA_PATH,
        prompt_path=prompt_path,
        tier="COMMODITY",
    )

    result = await extractor.extract("bad response", {}, "message")

    assert result.success is False
    assert result.patch is None
    assert "not valid JSON" in result.error


@pytest.mark.asyncio
async def test_openai_structured_extractor_reports_invalid_schema(tmp_path):
    prompt_path = tmp_path / "state_updater.txt"
    prompt_path.write_text("Extract JSON.", encoding="utf-8")
    # FakeLLMClient returns the same invalid-schema response on both
    # the initial attempt and the retry, so structured_call exhausts retries.
    extractor = OpenAIStructuredExtractor(
        FakeLLMClient('{"promises": [{"promise_id": "missing"}]}'),
        llm_config={},
        schema_path=SCHEMA_PATH,
        prompt_path=prompt_path,
        tier="COMMODITY",
    )

    result = await extractor.extract("bad schema", {}, "message")

    assert result.success is False
    assert result.patch is None
    assert "required property" in result.error


@pytest.mark.asyncio
async def test_openai_structured_extractor_reports_llm_exception(tmp_path):
    prompt_path = tmp_path / "state_updater.txt"
    prompt_path.write_text("Extract JSON.", encoding="utf-8")
    extractor = OpenAIStructuredExtractor(
        FakeLLMClient(RuntimeError("provider unavailable")),
        llm_config={},
        schema_path=SCHEMA_PATH,
        prompt_path=prompt_path,
        tier="COMMODITY",
    )

    result = await extractor.extract("anything", {}, "message")

    assert result == ExtractionResult(
        success=False,
        patch=None,
        error="provider unavailable",
    )

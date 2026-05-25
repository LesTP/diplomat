from __future__ import annotations

import pytest

from modules.extraction import (
    ExtractionResult,
    RuleBasedExtractor,
    load_schema,
    parse_json_object,
    validate_state_patch,
)
from modules.types import StatePatch


SCHEMA_PATH = "config/schemas/state_patch.json"


def test_extraction_result_exposes_success_patch_and_error_fields():
    patch = StatePatch({"promises": []})

    result = ExtractionResult(success=True, patch=patch)

    assert result.success is True
    assert result.patch == patch
    assert result.error is None


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

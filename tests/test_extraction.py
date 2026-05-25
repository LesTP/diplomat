from __future__ import annotations

import pytest

from modules.extraction import (
    ExtractionResult,
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

from __future__ import annotations

import json

import pytest

from tests.prompt_regression.types import (
    json_path_exists,
    json_path_get,
    load_scenario,
    load_scenarios,
)


def test_json_path_get_navigates_dotted_keys_and_array_indexes():
    data = {
        "patch": {
            "data": {
                "promises": [
                    {"status": "pending", "from_faction": "England"},
                ]
            }
        }
    }

    assert json_path_get(data, "patch.data.promises[0].status") == "pending"


def test_json_path_exists_returns_true_for_existing_falsey_values():
    data = {"patch": {"data": {"promises": [], "spent": False, "count": 0}}}

    assert json_path_exists(data, "patch.data.promises") is True
    assert json_path_exists(data, "patch.data.spent") is True
    assert json_path_exists(data, "patch.data.count") is True


def test_json_path_exists_returns_false_for_missing_key_or_bad_index():
    data = {"patch": {"data": {"promises": []}}}

    assert json_path_exists(data, "patch.data.coalitions") is False
    assert json_path_exists(data, "patch.data.promises[0]") is False


def test_json_path_get_rejects_invalid_path_syntax():
    with pytest.raises(ValueError, match="Invalid empty path segment"):
        json_path_get({}, "patch..data")

    with pytest.raises(ValueError, match="Invalid array index syntax"):
        json_path_get({"patch": []}, "patch[abc]")


def test_json_path_get_raises_for_type_mismatch():
    with pytest.raises(TypeError, match="Expected array"):
        json_path_get({"patch": {"data": {}}}, "patch.data[0]")


def test_load_scenario_validates_expected_shape(tmp_path):
    scenario_path = tmp_path / "scenario.json"
    scenario = {
        "scenario_id": "extraction.promise_explicit",
        "description": "Explicit promise creates a pending promise.",
        "module": "extraction",
        "input": {"text": "England promises France support."},
        "expected_properties": [
            {
                "type": "json_path_equals",
                "description": "Promise status is pending.",
                "path": "patch.data.promises[0].status",
                "value": "pending",
            }
        ],
    }
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")

    assert load_scenario(scenario_path) == scenario


def test_load_scenario_rejects_missing_required_fields(tmp_path):
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "scenario_id": "bad",
                "description": "Missing module.",
                "input": {},
                "expected_properties": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must define nonblank 'module'"):
        load_scenario(scenario_path)


def test_load_scenarios_loads_json_files_recursively_in_sorted_order(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    first = {
        "scenario_id": "a",
        "description": "First.",
        "module": "extraction",
        "input": {},
        "expected_properties": [],
    }
    second = {
        "scenario_id": "b",
        "description": "Second.",
        "module": "generation",
        "input": {},
        "expected_properties": [],
    }
    (nested / "b.json").write_text(json.dumps(second), encoding="utf-8")
    (tmp_path / "a.json").write_text(json.dumps(first), encoding="utf-8")

    assert [scenario["scenario_id"] for scenario in load_scenarios(tmp_path)] == [
        "a",
        "b",
    ]

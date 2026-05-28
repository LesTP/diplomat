from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from modules.types import StatePatch
from tests.prompt_regression.runner import ScenarioRunner
from tests.prompt_regression.types import RunReport


@dataclass(frozen=True)
class FakeExtractionResult:
    success: bool = True
    patch: StatePatch = StatePatch(
        {"promises": [{"status": "pending", "from_faction": "England"}]}
    )
    error: str | None = None


class FakeExtractor:
    def __init__(self):
        self.calls = []

    async def extract(self, input_text, current_state, trigger_type):
        self.calls.append((input_text, current_state, trigger_type))
        return FakeExtractionResult()


class FakeLLMClient:
    async def complete(self, **kwargs):
        return "PASS|Looks good."


async def fake_module_caller(
    module_name: str, input_data: Any, metadata: dict[str, Any]
) -> Any:
    if module_name == "extraction":
        extractor = FakeExtractor()
        return await extractor.extract(
            input_data.get("text", ""),
            input_data.get("current_state", {}),
            input_data.get("trigger_type", "message"),
        )
    raise ValueError(f"Unsupported module: {module_name}")


@pytest.mark.asyncio
async def test_run_scenario_evaluates_structural_properties():
    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )
    scenario = {
        "scenario_id": "extraction.promise_explicit",
        "description": "Explicit promise creates pending promise.",
        "module": "extraction",
        "input": {
            "text": "England promises France support.",
            "current_state": {"round": 1},
            "trigger_type": "message",
        },
        "expected_properties": [
            {
                "type": "json_path_exists",
                "description": "Promise exists.",
                "path": "patch.data.promises[0]",
            },
            {
                "type": "json_path_equals",
                "description": "Promise is pending.",
                "path": "patch.data.promises[0].status",
                "value": "pending",
            },
        ],
    }

    result = await runner.run_scenario(scenario)

    assert result.scenario_id == "extraction.promise_explicit"
    assert result.passed is True
    assert [property_result.passed for property_result in result.properties] == [
        True,
        True,
    ]


@pytest.mark.asyncio
async def test_run_scenario_evaluates_llm_judge_property():
    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )

    result = await runner.run_scenario(
        {
            "scenario_id": "extraction.judged",
            "description": "Judge can evaluate selected output.",
            "module": "extraction",
            "input": {"text": "England promises France support."},
            "expected_properties": [
                {
                    "type": "llm_judge",
                    "description": "Judge sees promise output.",
                    "path": "patch.data.promises[0]",
                    "criteria": "Output contains a promise.",
                    "pass_instruction": "Pass when promise is present.",
                    "fail_instruction": "Fail when promise is absent.",
                }
            ],
        }
    )

    assert result.passed is True
    assert result.properties[0].judge_explanation == "Looks good."


@pytest.mark.asyncio
async def test_run_scenario_raises_for_unsupported_module():
    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )

    with pytest.raises(ValueError, match="Unsupported module"):
        await runner.run_scenario(
            {
                "scenario_id": "generation.missing",
                "description": "No handler for this module.",
                "module": "generation",
                "input": {},
                "expected_properties": [],
            }
        )


@pytest.mark.asyncio
async def test_run_scenario_raises_for_invalid_judge_path():
    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )

    with pytest.raises(ValueError, match="Cannot extract judge response text"):
        await runner.run_scenario(
            {
                "scenario_id": "extraction.bad_path",
                "description": "Bad path raises clear error.",
                "module": "extraction",
                "input": {"text": "England promises support."},
                "expected_properties": [
                    {
                        "type": "llm_judge",
                        "description": "Judge sees response.",
                        "path": "nonexistent.field",
                        "criteria": "Something.",
                        "pass_instruction": "Pass.",
                        "fail_instruction": "Fail.",
                    }
                ],
            }
        )


@pytest.mark.asyncio
async def test_run_all_loads_scenarios_filters_and_returns_report(tmp_path):
    scenario = {
        "scenario_id": "extraction.promise_explicit",
        "description": "Explicit promise creates pending promise.",
        "module": "extraction",
        "input": {"text": "England promises France support."},
        "expected_properties": [
            {
                "type": "json_path_equals",
                "description": "Promise is pending.",
                "path": "patch.data.promises[0].status",
                "value": "pending",
            }
        ],
    }
    skipped = dict(scenario, scenario_id="generation.skip", module="generation")
    (tmp_path / "a.json").write_text(json.dumps(scenario), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps(skipped), encoding="utf-8")

    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )

    report = await runner.run_all(tmp_path, module_filter="extraction")

    assert report.total == 1
    assert report.passed == 1
    assert len(report.results) == 1
    assert report.results[0].scenario_id == "extraction.promise_explicit"
    assert report.results[0].passed is True


@pytest.mark.asyncio
async def test_run_scenario_failing_structural_check():
    """A json_path_equals mismatch should produce ScenarioResult.passed=False."""
    runner = ScenarioRunner(
        llm_client=FakeLLMClient(),
        llm_config={},
        module_caller=fake_module_caller,
    )
    scenario = {
        "scenario_id": "extraction.wrong_status",
        "description": "Status mismatch should fail.",
        "module": "extraction",
        "input": {"text": "England promises France support."},
        "expected_properties": [
            {
                "type": "json_path_equals",
                "description": "Promise status should be kept (but it is pending).",
                "path": "patch.data.promises[0].status",
                "value": "kept",
            }
        ],
    }
    result = await runner.run_scenario(scenario)
    assert result.passed is False
    assert len(result.properties) == 1
    assert result.properties[0].passed is False
    assert result.properties[0].expected == "kept"
    assert result.properties[0].actual == "pending"

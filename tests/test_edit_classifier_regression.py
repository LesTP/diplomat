from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from adapters import ToolkitLLMAdapter
from modules.edit_classifier import build_edit_classifier
from tests.prompt_regression.types import load_scenarios


SCENARIO_DIR = Path("tests/prompt_regression/scenarios/edit_classification")
PIPELINE_CONFIG = Path("config/pipeline.yaml")
MIN_ACCURACY = 0.85
MIN_CONFIDENCE = 0.7


def _load_pipeline_config() -> dict[str, Any]:
    config = yaml.safe_load(PIPELINE_CONFIG.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Pipeline config must be a mapping: {PIPELINE_CONFIG}")
    return config


def _build_live_classifier():
    config = _load_pipeline_config()
    providers = dict(config.get("llm_providers") or {})
    primary = dict(providers.get("primary") or {})
    if not primary:
        raise RuntimeError("Pipeline config missing llm_providers.primary")

    api_key_env = str(primary.get("api_key_env") or "")
    if not api_key_env or not os.getenv(api_key_env):
        pytest.skip(
            f"{api_key_env or 'LLM API key'} is required for the live edit-classification regression suite"
        )

    toolkit_llm = __import__("toolkit.llm_client", fromlist=["llm_client"])
    llm_client = ToolkitLLMAdapter(toolkit_llm)
    classifier = build_edit_classifier(
        llm_client=llm_client,
        llm_providers_config={"primary": primary},
        tier="commodity",
        attribution="edit_classifier_regression",
    )
    if classifier is None:
        raise RuntimeError("Unable to build edit classifier from pipeline config")
    return classifier


def test_edit_classifier_fixture_suite_has_all_categories():
    scenarios = load_scenarios(SCENARIO_DIR)
    assert len(scenarios) == 24
    assert {scenario["expected_category"] for scenario in scenarios} == {
        "tone_softer",
        "tone_harder",
        "commitment_removed",
        "ambiguity_added",
        "constraint_enforcement",
        "persona_correction",
    }
    assert all(scenario["module"] == "edit_classifier" for scenario in scenarios)
    assert all(
        scenario["minimum_confidence"] == MIN_CONFIDENCE for scenario in scenarios
    )


@pytest.mark.asyncio
async def test_edit_classifier_regression_suite_meets_thresholds():
    classifier = _build_live_classifier()
    scenarios = load_scenarios(SCENARIO_DIR)
    assert scenarios, f"No regression scenarios found in {SCENARIO_DIR}"

    passed = 0
    failures: list[str] = []
    category_totals: dict[str, int] = {}
    category_passes: dict[str, int] = {}

    for scenario in scenarios:
        input_data = scenario["input"]
        try:
            classification = await classifier.classify(
                input_data["original"],
                input_data["edited"],
                input_data.get("edit_notes"),
            )
        except RuntimeError as exc:
            err = str(exc)
            if "package is required" in err or "Install it with" in err:
                pytest.skip(err)
            raise

        expected_category = scenario["expected_category"]
        minimum_confidence = float(scenario.get("minimum_confidence", MIN_CONFIDENCE))
        category_totals[expected_category] = category_totals.get(expected_category, 0) + 1

        category_ok = classification.category == expected_category
        confidence_ok = classification.confidence >= minimum_confidence

        if category_ok and confidence_ok:
            passed += 1
            category_passes[expected_category] = (
                category_passes.get(expected_category, 0) + 1
            )
            continue

        failures.append(
            (
                f"{scenario['scenario_id']}: expected {expected_category} "
                f"at >= {minimum_confidence:.2f}, got {classification.category} "
                f"at {classification.confidence:.2f}"
            )
        )

    accuracy = passed / len(scenarios)

    assert accuracy >= MIN_ACCURACY, (
        f"Edit classification regression suite passed {passed}/{len(scenarios)} "
        f"scenarios ({accuracy:.1%}), below the {MIN_ACCURACY:.0%} floor.\n"
        f"Category passes: {category_passes}\n"
        f"Category totals: {category_totals}\n"
        + ("\n".join(failures) if failures else "")
    )

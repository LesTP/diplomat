from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from modules.analyst import LLMAnalyst
from modules.analyst.divergence import compare
from modules.types import AnalysisResult, Divergence


SCHEMA_PATH = "config/schemas/intelligence.json"
PROMPT_PATH = "config/prompts/analyst.txt"


class FakeLLMClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _report(
    threat_level: int = 2,
    key_leverage_points: list[str] | None = None,
    coalition_stability: str = "stable",
) -> dict:
    return {
        "threat_level": threat_level,
        "key_leverage_points": key_leverage_points or ["Belgium support"],
        "coalition_stability": coalition_stability,
    }


def _result(success: bool = True, report: dict | None = None) -> AnalysisResult:
    return AnalysisResult(
        success=success,
        provider_id="primary",
        report=report if report is not None else _report(),
        error=None if success else "failed",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_successful_analysis_with_valid_json():
    client = FakeLLMClient(json.dumps(_report()))
    analyst = LLMAnalyst(
        llm_client=client,
        llm_config={"provider": "anthropic"},
        tier="QUALITY",
        prompt_path=PROMPT_PATH,
        schema_path=SCHEMA_PATH,
        provider_id="anthropic",
    )

    result = await analyst.analyze({"promises": []})

    assert result.success is True
    assert result.provider_id == "anthropic"
    assert result.report == _report()
    assert result.error is None
    assert result.timestamp.tzinfo is not None
    assert client.calls[0]["config"] == {"provider": "anthropic"}
    assert client.calls[0]["tier"] == "QUALITY"
    assert client.calls[0]["messages"][0]["role"] == "system"
    assert "Intelligence JSON schema:" in client.calls[0]["messages"][1]["content"]
    assert '"promises": []' in client.calls[0]["messages"][1]["content"]


@pytest.mark.asyncio
async def test_llm_returns_invalid_json_success_false():
    analyst = LLMAnalyst(
        FakeLLMClient("{invalid"),
        llm_config={},
        tier="QUALITY",
        prompt_path=PROMPT_PATH,
        schema_path=SCHEMA_PATH,
        provider_id="openai",
    )

    result = await analyst.analyze({})

    assert result.success is False
    assert result.provider_id == "openai"
    assert result.report is None
    assert "not valid JSON" in result.error


@pytest.mark.asyncio
async def test_llm_exception_success_false():
    analyst = LLMAnalyst(
        FakeLLMClient(RuntimeError("provider unavailable")),
        llm_config={},
        tier="QUALITY",
        prompt_path=PROMPT_PATH,
        schema_path=SCHEMA_PATH,
        provider_id="anthropic",
    )

    result = await analyst.analyze({})

    assert result.success is False
    assert result.report is None
    assert result.error == "provider unavailable"


@pytest.mark.asyncio
async def test_schema_validation_failure_success_false():
    analyst = LLMAnalyst(
        FakeLLMClient(json.dumps({"threat_level": 9})),
        llm_config={},
        tier="QUALITY",
        prompt_path=PROMPT_PATH,
        schema_path=SCHEMA_PATH,
        provider_id="anthropic",
    )

    result = await analyst.analyze({})

    assert result.success is False
    assert result.report is None
    assert "failed schema validation" in result.error


@pytest.mark.asyncio
async def test_provider_id_propagated_on_failure():
    analyst = LLMAnalyst(
        FakeLLMClient(RuntimeError("boom")),
        llm_config={},
        tier="QUALITY",
        prompt_path=PROMPT_PATH,
        schema_path=SCHEMA_PATH,
        provider_id="secondary-provider",
    )

    result = await analyst.analyze({})

    assert result.provider_id == "secondary-provider"


def test_compare_both_failed_empty():
    assert compare(_result(success=False), _result(success=False)) == []


def test_compare_one_failed_empty():
    assert compare(_result(success=True), _result(success=False)) == []


def test_compare_both_identical_empty():
    assert compare(_result(report=_report()), _result(report=_report())) == []


def test_threat_level_steps_divergence_detected():
    divergences = compare(
        _result(report=_report(threat_level=1)),
        _result(report=_report(threat_level=4)),
    )

    assert divergences == [
        Divergence(
            field="threat_level",
            primary_value="1",
            secondary_value="4",
            note="Threat level differs by 3 steps, above threshold 1.",
        )
    ]


def test_threat_level_steps_within_threshold_no_divergence():
    divergences = compare(
        _result(report=_report(threat_level=2)),
        _result(report=_report(threat_level=3)),
    )

    assert divergences == []


def test_missing_leverage_item_divergence():
    divergences = compare(
        _result(report=_report(key_leverage_points=["Belgium support", "Blackmail"])),
        _result(report=_report(key_leverage_points=["Belgium support"])),
    )

    assert len(divergences) == 1
    assert divergences[0].field == "key_leverage_points"
    assert divergences[0].primary_value == "Belgium support, Blackmail"
    assert divergences[0].secondary_value == "Belgium support"


def test_coalition_stability_mismatch_divergence():
    divergences = compare(
        _result(report=_report(coalition_stability="stable")),
        _result(report=_report(coalition_stability="volatile")),
    )

    assert divergences == [
        Divergence(
            field="coalition_stability",
            primary_value="stable",
            secondary_value="volatile",
            note="Analysts disagree on coalition stability.",
        )
    ]

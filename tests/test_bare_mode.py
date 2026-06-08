"""Unit tests for bare-mode ablation stand-ins."""

from __future__ import annotations

import pytest

from modules.adversarial import AdversarialResult
from modules.extraction import ExtractionResult
from modules.reconciliation import ReconciliationResult
from modules.types import AnalysisResult, StatePatch
from tests.self_play.bare_mode import (
    _BareAdversarial,
    _BareAnalyst,
    _BareCoaching,
    _BareExtractor,
    _BareReconciler,
    bare_module_overrides,
)
from toolkit.coaching import CoachingEvent


@pytest.mark.asyncio
async def test_bare_extractor_success_with_empty_patch():
    result = await _BareExtractor().extract("any text", {}, "message")
    assert isinstance(result, ExtractionResult)
    assert result.success is True
    assert isinstance(result.patch, StatePatch)
    assert result.patch.data == {}
    assert result.error is None


@pytest.mark.asyncio
async def test_bare_extractor_ignores_input_content():
    extractor = _BareExtractor()
    r1 = await extractor.extract("Alpha promises Beta territory.", {"promises": []}, "message")
    r2 = await extractor.extract("", {}, "intel_correction")
    for result in (r1, r2):
        assert result.success is True
        assert result.patch.data == {}


@pytest.mark.asyncio
async def test_bare_analyst_returns_failure():
    result = await _BareAnalyst(provider_id="bare_primary").analyze({}, recent_events=[])
    assert isinstance(result, AnalysisResult)
    assert result.success is False
    assert result.error == "bare_mode"
    assert result.report is None
    assert result.provider_id == "bare_primary"
    assert result.timestamp.tzinfo is not None


@pytest.mark.asyncio
async def test_bare_analyst_default_provider_id():
    result = await _BareAnalyst().analyze({})
    assert result.provider_id == "bare"


@pytest.mark.asyncio
async def test_bare_analyst_accepts_none_events():
    result = await _BareAnalyst().analyze({"promises": []}, recent_events=None)
    assert result.success is False


@pytest.mark.asyncio
async def test_bare_reconciler_returns_success_no_mutations():
    result = await _BareReconciler().reconcile({}, [], 1)
    assert isinstance(result, ReconciliationResult)
    assert result.success is True
    assert result.merged_promises == []
    assert result.updated_statuses == []
    assert result.new_inconsistencies == []
    assert result.missed_proposals == []
    assert result.error is None


@pytest.mark.asyncio
async def test_bare_adversarial_returns_success_no_analysis():
    result = await _BareAdversarial().read("some draft text")
    assert isinstance(result, AdversarialResult)
    assert result.success is True
    assert result.analysis is None
    assert result.error is None


@pytest.mark.asyncio
async def test_bare_adversarial_handles_blank_draft():
    result = await _BareAdversarial().read("")
    assert result.success is True
    assert result.analysis is None


def test_bare_coaching_returns_free_coaching_event():
    result = _BareCoaching().parse("PRIORITY: dominate the negotiation")
    assert isinstance(result, CoachingEvent)
    assert result.content == ""
    assert result.route != "state_updater"


def test_bare_coaching_ignores_all_input_variants():
    coaching = _BareCoaching()
    for raw in ("INTEL: Alpha controls river", "/preview", "", "free text"):
        result = coaching.parse(raw)
        assert isinstance(result, CoachingEvent)
        assert result.content == ""


def test_bare_module_overrides_contains_expected_module_keys():
    overrides = bare_module_overrides(None)
    required_keys = {"extractor", "primary_analyst", "secondary_analyst", "divergence", "adversarial", "coaching_parser"}
    assert required_keys <= overrides.keys()


def test_bare_module_overrides_does_not_include_reconciler():
    overrides = bare_module_overrides(None)
    assert "reconciler" not in overrides


def test_bare_module_overrides_stand_in_types():
    overrides = bare_module_overrides(None)
    assert isinstance(overrides["extractor"], _BareExtractor)
    assert isinstance(overrides["primary_analyst"], _BareAnalyst)
    assert isinstance(overrides["secondary_analyst"], _BareAnalyst)
    assert isinstance(overrides["adversarial"], _BareAdversarial)
    assert isinstance(overrides["coaching_parser"], _BareCoaching)
    assert callable(overrides["divergence"])


def test_bare_module_overrides_analyst_provider_ids():
    overrides = bare_module_overrides(None)
    assert overrides["primary_analyst"].provider_id == "bare_primary"
    assert overrides["secondary_analyst"].provider_id == "bare_secondary"

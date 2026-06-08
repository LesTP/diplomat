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


# ── Step 34.3: --bare-prompt flag integration tests ──────────────────


@pytest.mark.asyncio
async def test_game_environment_bare_mode_flag_in_results(tmp_path):
    """bare_mode=True is stored in the results JSON."""
    from pathlib import Path
    from tests.helpers.factories import FakeCostAccountant, FakeLLMClient
    from tests.self_play.game_environment import GameEnvironment

    personas_dir = Path(__file__).resolve().parent / "self_play" / "personas"
    project_root = Path(__file__).resolve().parent.parent
    factions = {
        "alpha": personas_dir / "alpha.txt",
        "beta": personas_dir / "beta.txt",
    }
    # Bare mode only needs generation responses — no analyst, no adversarial.
    llm_client = FakeLLMClient(
        [{"response": "Test message.", "reasoning": "Testing."}] * 20
    )
    env = GameEnvironment(
        faction_personas=factions,
        llm_client=llm_client,
        cost_accountant=FakeCostAccountant(),
        base_path=project_root,
        tmp_dir=tmp_path,
        bare_mode=True,
    )
    await env.setup()
    results = await env.run_game(total_rounds=1)
    await env.teardown()

    assert results.get("bare_mode") is True


@pytest.mark.asyncio
async def test_game_environment_full_mode_bare_mode_false(tmp_path):
    """bare_mode defaults to False and is stored as such in results."""
    from pathlib import Path
    from tests.helpers.factories import FakeCostAccountant, FakeLLMClient
    from tests.helpers.stub_analyst import StubAnalyst
    from tests.self_play.game_environment import GameEnvironment

    personas_dir = Path(__file__).resolve().parent / "self_play" / "personas"
    project_root = Path(__file__).resolve().parent.parent
    fixture = project_root / "tests" / "integration" / "fixtures" / "intelligence_stub.json"
    factions = {
        "alpha": personas_dir / "alpha.txt",
        "beta": personas_dir / "beta.txt",
    }
    llm_client = FakeLLMClient(
        [
            {"response": "Test message.", "reasoning": "Testing."},
            {"reveals": [], "commits_to": [], "exploitable": [], "counter_moves": [], "summary": "No exploit."},
        ] * 20
    )
    env = GameEnvironment(
        faction_personas=factions,
        llm_client=llm_client,
        cost_accountant=FakeCostAccountant(),
        base_path=project_root,
        tmp_dir=tmp_path,
        extra_module_overrides={
            "primary_analyst": StubAnalyst(fixture, provider_id="primary"),
            "secondary_analyst": StubAnalyst(fixture, provider_id="secondary"),
        },
    )
    await env.setup()
    results = await env.run_game(total_rounds=1)
    await env.teardown()

    assert results.get("bare_mode") is False


@pytest.mark.asyncio
async def test_bare_mode_context_shorter_than_full_mode():
    """Bare-mode context omits intel/divergences/coaching, producing a shorter prompt."""
    from datetime import datetime, timezone
    from modules.context_assembler import DefaultContextAssembler
    from modules.types import StoredEvent, InboundEvent

    assembler = DefaultContextAssembler()
    persona = "You are Alpha faction in a water rights dispute."
    round_ctx = "Round 1. Opening positions."
    intelligence = {"threat_level": "high", "leverage": "upstream control", "risks": []}
    divergences = []
    now = datetime.now(timezone.utc)
    event = StoredEvent(
        event_id="e1",
        round_number=1,
        event=InboundEvent(sender_faction="alpha", channel="public", content="Hello.", timestamp=now),
    )
    recent_events = [event]
    coaching = []

    full_ctx = await assembler.assemble(
        persona_prompt=persona,
        round_context=round_ctx,
        intelligence=intelligence,
        divergences=divergences,
        recent_events=recent_events,
        free_coaching=coaching,
        review_gate_enabled=False,
        bare_mode=False,
    )
    bare_ctx = await assembler.assemble(
        persona_prompt=persona,
        round_context=round_ctx,
        intelligence=intelligence,
        divergences=divergences,
        recent_events=recent_events,
        free_coaching=coaching,
        review_gate_enabled=False,
        bare_mode=True,
    )

    assert len(bare_ctx.user_prompt) < len(full_ctx.user_prompt), (
        "Bare-mode prompt should be shorter than full-mode prompt"
    )
    assert "INTELLIGENCE" not in bare_ctx.user_prompt
    assert "COACHING" not in bare_ctx.user_prompt
    assert "TRANSCRIPT" in bare_ctx.user_prompt
    assert bare_ctx.metadata.get("bare_mode") is True

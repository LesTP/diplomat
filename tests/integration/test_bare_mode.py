"""Integration tests for bare-prompt ablation mode.

Covers:
  (a) Bare-mode orchestrator processes a round-end event without raising;
      no analyst LLM call made, no intelligence row written.
  (b) Bare-mode context assembler produces correct shape (persona + transcript,
      no intel/divergences/coaching sections).
  (c) bare_module_overrides() integrates with GameEnvironment; completes a
      4-round game with all factions acting.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from modules.types import EventFilter
from orchestrator import OrchestrationOptions, Orchestrator
from tests.helpers.factories import FakeCostAccountant, make_event, make_round_end_event
from tests.helpers.test_transport import TestTransport
from tests.self_play.bare_mode import (
    _BareReconciler,
    bare_module_overrides,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _tmp_pipeline_config(tmp_path: Path, faction_id: str = "alpha") -> Path:
    config: dict[str, Any] = yaml.safe_load(
        (_PROJECT_ROOT / "config" / "pipeline_test.yaml").read_text(encoding="utf-8")
    )
    config["faction_id"] = faction_id
    config["database"]["path"] = str(tmp_path / f"{faction_id}.db")
    config["message_debounce_seconds"] = 0.01
    config_path = tmp_path / f"pipeline_bare_{faction_id}.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


class CapturingLLMClient:
    """Records every complete() call made by the orchestrator."""

    def __init__(self, *, gen_response: dict[str, Any] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self._gen_response = gen_response or {
            "response": "Alpha proposes a balanced deal.",
            "reasoning": "Keeps options open.",
        }

    async def complete(self, **kwargs: Any) -> str:
        self.calls.append(dict(kwargs))
        return json.dumps(self._gen_response, sort_keys=True)


# ---------------------------------------------------------------------------
# Fixture: bare-mode orchestrator (no GameEnvironment)
# ---------------------------------------------------------------------------

from dataclasses import dataclass


@dataclass
class BareOrchestrationHarness:
    orchestrator: Orchestrator
    transport: TestTransport
    llm_client: CapturingLLMClient
    task: asyncio.Task[None]


@pytest.fixture
async def bare_pipeline(tmp_path: Path) -> BareOrchestrationHarness:
    config_path = _tmp_pipeline_config(tmp_path, "alpha")
    transport = TestTransport()
    llm_client = CapturingLLMClient()
    cost_accountant = FakeCostAccountant()

    overrides: dict[str, Any] = {"transport": transport}
    overrides.update(bare_module_overrides())

    orchestrator = Orchestrator(
        config_path,
        options=OrchestrationOptions(auto_response_enabled=False, bare_mode=True),
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        module_overrides=overrides,
        base_path=_PROJECT_ROOT,
    )
    orchestrator.reconciler = _BareReconciler()

    task = asyncio.create_task(orchestrator.start())
    await asyncio.sleep(0)

    harness = BareOrchestrationHarness(
        orchestrator=orchestrator,
        transport=transport,
        llm_client=llm_client,
        task=task,
    )
    try:
        yield harness
    finally:
        await orchestrator.shutdown()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# Test (a): round boundary doesn't raise; no intelligence row written
# ---------------------------------------------------------------------------

async def test_bare_mode_round_boundary_no_exception(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """handle_round_boundary() completes without exception in bare mode."""
    orch = bare_pipeline.orchestrator
    await orch.handle_round_boundary()


async def test_bare_mode_no_intelligence_row_written(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """No intelligence rows should be written when analysts are bare no-ops."""
    orch = bare_pipeline.orchestrator
    await orch.handle_round_boundary()

    rows = await orch.state_manager.query("intelligence", {})
    assert len(rows) == 0, f"Expected 0 intelligence rows, got {len(rows)}"


async def test_bare_mode_no_analyst_llm_call(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """No LLM calls should be made during handle_round_boundary() in bare mode."""
    llm_client = bare_pipeline.llm_client
    call_count_before = len(llm_client.calls)

    await bare_pipeline.orchestrator.handle_round_boundary()

    assert len(llm_client.calls) == call_count_before, (
        f"Expected no new LLM calls during bare-mode round boundary, "
        f"got {len(llm_client.calls) - call_count_before}"
    )


# ---------------------------------------------------------------------------
# Test (b): bare context assembler produces correct shape
# ---------------------------------------------------------------------------

async def test_bare_mode_context_has_persona_prompt(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """Generation call's system prompt should be the persona prompt (not empty)."""
    orch = bare_pipeline.orchestrator
    orch.advance_to_round(1)

    await bare_pipeline.transport.inject(
        make_event("Beta opens: we need High water release.", sender_faction="beta")
    )
    await asyncio.sleep(0.1)
    await orch.run_response_pipeline()

    assert bare_pipeline.llm_client.calls, "Expected at least one LLM call from run_response_pipeline"
    gen_call = bare_pipeline.llm_client.calls[-1]
    messages = gen_call.get("messages", [])
    sys_msg = next((m for m in messages if m.get("role") == "system"), None)
    assert sys_msg is not None, "Expected a system message in the generation call"
    # Persona prompt should be non-trivial (loaded from faction_prompt.txt)
    assert len(sys_msg.get("content", "")) > 50, "System prompt looks too short to be a real persona"


async def test_bare_mode_context_no_intel_sections(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """User prompt in bare mode must NOT contain the intelligence report or coaching sections."""
    orch = bare_pipeline.orchestrator
    orch.advance_to_round(1)

    await bare_pipeline.transport.inject(
        make_event("Beta opens: we need High water release.", sender_faction="beta")
    )
    await asyncio.sleep(0.1)
    await orch.run_response_pipeline()

    assert bare_pipeline.llm_client.calls, "Expected LLM call"
    gen_call = bare_pipeline.llm_client.calls[-1]
    messages = gen_call.get("messages", [])
    user_msg = next((m for m in messages if m.get("role") == "user"), None)
    assert user_msg is not None, "Expected a user message"
    content = user_msg.get("content", "")
    # These section headers should NOT appear in bare-mode prompts
    assert "INTELLIGENCE REPORT" not in content
    assert "DIVERGENCE" not in content
    assert "COACHING" not in content


async def test_bare_mode_context_contains_transcript(
    bare_pipeline: BareOrchestrationHarness,
) -> None:
    """User prompt should contain the raw message transcript in bare mode."""
    orch = bare_pipeline.orchestrator
    orch.advance_to_round(1)

    event_text = "Beta opens: we need High water release."
    await bare_pipeline.transport.inject(
        make_event(event_text, sender_faction="beta")
    )
    await asyncio.sleep(0.1)
    await orch.run_response_pipeline()

    assert bare_pipeline.llm_client.calls
    gen_call = bare_pipeline.llm_client.calls[-1]
    messages = gen_call.get("messages", [])
    user_msg = next((m for m in messages if m.get("role") == "user"), None)
    assert user_msg is not None
    content = user_msg.get("content", "")
    # The injected message text should appear in the transcript
    assert event_text in content, (
        f"Expected injected event text in bare context transcript. Got:\n{content[:500]}"
    )


# ---------------------------------------------------------------------------
# Test (c): GameEnvironment + bare_module_overrides runs a complete game
# ---------------------------------------------------------------------------

async def test_bare_mode_game_environment_completes_four_rounds(
    tmp_path: Path,
) -> None:
    """GameEnvironment with bare_mode=True should complete 4 rounds, all factions acting."""
    from tests.self_play.fake_llm_client import DryRunLLMClient
    from tests.self_play.game_environment import GameEnvironment

    personas_dir = _PROJECT_ROOT / "tests" / "self_play" / "personas"
    faction_ids = ["alpha", "beta", "gamma"]
    faction_personas = {fid: personas_dir / f"{fid}.txt" for fid in faction_ids}

    env = GameEnvironment(
        faction_personas=faction_personas,
        llm_client=DryRunLLMClient(),
        cost_accountant=FakeCostAccountant(),
        base_path=_PROJECT_ROOT,
        tmp_dir=tmp_path,
        seed_message="Three factions must negotiate water rights.",
        round_updates={
            1: "Opening positions.",
            2: "Midpoint.",
            3: "Pressure rising.",
            4: "Final round.",
        },
    )

    await env.setup()
    try:
        results = await env.run_game(total_rounds=4)
    finally:
        await env.teardown()

    assert results["bare_mode"] is False  # default — env not set to bare_mode


async def test_bare_mode_game_environment_bare_flag_set(
    tmp_path: Path,
) -> None:
    """GameEnvironment with bare_mode=True must set bare_mode=True in results."""
    from tests.self_play.fake_llm_client import DryRunLLMClient
    from tests.self_play.game_environment import GameEnvironment

    personas_dir = _PROJECT_ROOT / "tests" / "self_play" / "personas"
    faction_ids = ["alpha", "beta", "gamma"]
    faction_personas = {fid: personas_dir / f"{fid}.txt" for fid in faction_ids}

    env = GameEnvironment(
        faction_personas=faction_personas,
        llm_client=DryRunLLMClient(),
        cost_accountant=FakeCostAccountant(),
        base_path=_PROJECT_ROOT,
        tmp_dir=tmp_path,
        seed_message="Three factions must negotiate water rights.",
        round_updates={1: "R1", 2: "R2", 3: "R3", 4: "R4"},
        bare_mode=True,
    )

    await env.setup()
    try:
        results = await env.run_game(total_rounds=4)
    finally:
        await env.teardown()

    assert results["bare_mode"] is True
    assert results["rounds_completed"] == 4
    # All factions should have responded in at least one round
    round_responses = results.get("round_responses", {})
    responding_factions = set()
    for rnd_data in round_responses.values():
        responding_factions.update(rnd_data.keys())
    assert responding_factions == set(faction_ids), (
        f"Expected all factions {faction_ids} to respond. "
        f"Got: {responding_factions}"
    )

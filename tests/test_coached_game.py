from __future__ import annotations

from pathlib import Path

import pytest

from modules.review_gate import AutoApproveReviewGate
from tests.helpers.factories import FakeCostAccountant
from tests.helpers.stub_analyst import StubAnalyst
from tests.self_play.coached_game import (
    CoachedGameEnvironment,
    CoachedGameTransport,
    DryRunTelegramReviewGate,
)
from tests.self_play.fake_llm_client import DryRunLLMClient
from tests.self_play.game_environment import LoggingLLMClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSONAS_DIR = PROJECT_ROOT / "tests" / "self_play" / "personas"
INTELLIGENCE_FIXTURE = (
    PROJECT_ROOT / "tests" / "integration" / "fixtures" / "intelligence_stub.json"
)


def _faction_personas() -> dict[str, Path]:
    return {
        "alpha": PERSONAS_DIR / "alpha.txt",
        "beta": PERSONAS_DIR / "beta.txt",
        "gamma": PERSONAS_DIR / "gamma.txt",
    }


def _scenario_analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta", "gamma"],
        "issues": [
            {
                "name": "tariff_rates",
                "outcomes": ["strict", "moderate", "relaxed"],
            }
        ],
        "scoring": {
            "alpha": {"tariff_rates": {"strict": 8, "moderate": 5, "relaxed": 2}},
            "beta": {"tariff_rates": {"strict": 4, "moderate": 7, "relaxed": 3}},
            "gamma": {"tariff_rates": {"strict": 2, "moderate": 4, "relaxed": 9}},
        },
        "batna": {"alpha": 4, "beta": 4, "gamma": 4},
        "game_mode": "competitive",
    }


def _build_environment(tmp_path: Path) -> CoachedGameEnvironment:
    llm_client = LoggingLLMClient(DryRunLLMClient())
    cost_accountant = FakeCostAccountant()
    extra_overrides = {
        "primary_analyst": StubAnalyst(INTELLIGENCE_FIXTURE, provider_id="primary"),
        "secondary_analyst": StubAnalyst(INTELLIGENCE_FIXTURE, provider_id="secondary"),
    }
    return CoachedGameEnvironment(
        coach_faction="beta",
        dry_run=True,
        telegram_client=None,
        public_channel_id=None,
        coaching_channel_id=None,
        operator_user_ids=set(),
        faction_personas=_faction_personas(),
        llm_client=llm_client,
        cost_accountant=cost_accountant,
        base_path=PROJECT_ROOT,
        tmp_dir=tmp_path,
        extra_module_overrides=extra_overrides,
        seed_message="Self-play coaching smoke test.",
        round_updates={
            1: "Round one update.",
            2: "Round two update.",
            3: "Round three update.",
            4: "Round four update.",
        },
        scenario_analysis=_scenario_analysis(),
    )


@pytest.mark.asyncio
async def test_coached_game_routes_one_faction_through_telegram_standin(tmp_path: Path):
    env = _build_environment(tmp_path)

    await env.setup()
    try:
        beta = env.agents["beta"]
        alpha = env.agents["alpha"]
        gamma = env.agents["gamma"]

        assert isinstance(beta.transport, CoachedGameTransport)
        assert isinstance(beta.orchestrator.pipeline.orchestrator.review_gate, DryRunTelegramReviewGate)
        assert isinstance(alpha.orchestrator.pipeline.orchestrator.review_gate, AutoApproveReviewGate)
        assert isinstance(gamma.orchestrator.pipeline.orchestrator.review_gate, AutoApproveReviewGate)

        results = await env.run_game(total_rounds=4)

        assert results["rounds_completed"] == 4
        assert set(results["round_responses"]) == {"1", "2", "3", "4"}
        assert len(results["round_responses"]["1"]) == 3
        assert any(msg["sender"] == "beta" for msg in results["transcript"])
        assert results["transcript"][0]["sender"] == "moderator"
        assert results["transcript"][0]["channel"] == "public"
        assert results["transcript"][-1]["content"] == "[ROUND END]"
    finally:
        await env.teardown()

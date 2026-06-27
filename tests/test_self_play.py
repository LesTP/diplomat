"""Unit tests for self-play infrastructure.

These use FakeLLMClient and FakeCostAccountant — no real API calls.
They validate GameEnvironment mechanics: config generation, broadcast,
round lifecycle, and results collection.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from tests.helpers.factories import FakeCostAccountant, FakeLLMClient, make_event
from tests.helpers.test_transport import TestTransport
from tests.self_play.game_environment import GameEnvironment
from tests.self_play.analysis import analyze_results
from tests.self_play.run_simulation import _apply_game_mode_override
from tests.self_play.scenario import ROUND_UPDATES, SEED_MESSAGE


PERSONAS_DIR = Path(__file__).resolve().parent / "self_play" / "personas"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Helpers ──────────────────────────────────────────────────────────


def _faction_personas() -> dict[str, Path]:
    return {
        "alpha": PERSONAS_DIR / "alpha.txt",
        "beta": PERSONAS_DIR / "beta.txt",
        "gamma": PERSONAS_DIR / "gamma.txt",
    }


def _make_env(
    tmp_path: Path,
    factions: dict[str, Path] | None = None,
    llm_responses: list | None = None,
    scenario_analysis: dict | None = None,
) -> GameEnvironment:
    responses = llm_responses or [
        {
            "response": "Test diplomatic response.",
            "reasoning": "Testing infrastructure.",
        },
        {
            "reveals": [],
            "commits_to": [],
            "exploitable": [],
            "counter_moves": [],
            "summary": "No exploit found.",
        },
    ]
    llm_client = FakeLLMClient(responses * 20)  # plenty for multi-round
    cost = FakeCostAccountant()

    # Inject StubAnalysts so tests work without toolkit installed.
    from tests.helpers.stub_analyst import StubAnalyst

    fixture_path = PROJECT_ROOT / "tests" / "integration" / "fixtures" / "intelligence_stub.json"
    extra_overrides = {
        "primary_analyst": StubAnalyst(fixture_path, provider_id="primary"),
        "secondary_analyst": StubAnalyst(fixture_path, provider_id="secondary"),
    }

    return GameEnvironment(
        faction_personas=factions or _faction_personas(),
        llm_client=llm_client,
        cost_accountant=cost,
        base_path=PROJECT_ROOT,
        tmp_dir=tmp_path,
        extra_module_overrides=extra_overrides,
        scenario_analysis=scenario_analysis,
    )


def _pareto_scenario() -> dict:
    return {
        "factions": ["alpha", "beta"],
        "issues": [
            {
                "name": "resource_split",
                "outcomes": ["optimum", "fallback"],
            }
        ],
        "scoring": {
            "alpha": {"resource_split": {"optimum": 10, "fallback": 4}},
            "beta": {"resource_split": {"optimum": 10, "fallback": 6}},
        },
        "batna": {"alpha": 4, "beta": 6},
    }


def _three_faction_nash_scenario() -> dict:
    return {
        "factions": ["alpha", "beta", "gamma"],
        "issues": [
            {
                "name": "resource_split",
                "outcomes": ["aggressive", "balanced"],
            }
        ],
        "scoring": {
            "alpha": {"resource_split": {"aggressive": 100, "balanced": 30}},
            "beta": {"resource_split": {"aggressive": 1, "balanced": 30}},
            "gamma": {"resource_split": {"aggressive": 1, "balanced": 30}},
        },
        "batna": {"alpha": 0, "beta": 0, "gamma": 0},
    }


def _process_signature_results() -> dict:
    return {
        "rounds_completed": 4,
        "transcript": [
            {"round": 1, "sender": "alpha", "content": "Opening position."},
            {"round": 3, "sender": "moderator", "content": "Deal reached."},
        ],
        "agents": {
            "alpha": {
                "promises": [
                    {"promise_id": "p1", "status": "kept"},
                    {"promise_id": "p2", "status": "broken"},
                ],
                "coalitions": [
                    {"coalition_id": "c1", "status": "active"},
                    {"coalition_id": "c2", "status": "dissolved", "ended_round": 2},
                ],
            },
            "beta": {
                "promises": [
                    {"promise_id": "p2", "status": "broken"},
                    {"promise_id": "p3", "status": "pending"},
                    {"promise_id": "p4", "status": "kept"},
                ],
                "coalitions": [
                    {"coalition_id": "c1", "status": "active"},
                ],
            },
        },
        "round_responses": {
            "1": {
                "alpha": "Alpha proposes optimum.",
                "beta": "Beta proposes fallback.",
            }
        },
        "scores": {
            "deal_reached": True,
            "faction_scores": {
                "alpha": {"points": 4, "batna": 4},
                "beta": {"points": 10, "batna": 6},
            },
        },
        "scenario_analysis": _pareto_scenario(),
    }


class TestGameModeOverride:
    def test_applies_runtime_game_mode_without_mutating_source(self) -> None:
        analysis = {"game_mode": "cooperative", "factions": ["alpha"]}

        updated = _apply_game_mode_override(analysis, "competitive")

        assert updated["game_mode"] == "competitive"
        assert analysis["game_mode"] == "cooperative"

    def test_none_keeps_original_analysis_object(self) -> None:
        analysis = {"game_mode": "mixed", "factions": ["alpha"]}

        assert _apply_game_mode_override(analysis, None) is analysis


def test_analysis_report_uses_entity_types_from_schema(tmp_path, capsys) -> None:
    schema_path = tmp_path / "state_patch.json"
    schema_path.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {
                    "promises": {"type": "array"},
                    "treaties": {"type": "array"},
                },
            }
        ),
        encoding="utf-8",
    )
    results = {
        "rounds_completed": 1,
        "transcript": [],
        "agents": {
            "alpha": {
                "promises": [],
                "treaties": [{"treaty_id": "t1"}],
                "intelligence": [],
                "round": 1,
            }
        },
        "round_responses": {},
    }

    analyze_results(results, state_patch_schema_path=schema_path)

    captured = capsys.readouterr()
    assert "Promises tracked:       0" in captured.out
    assert "Treaties tracked:       1" in captured.out


# ── Config generation ────────────────────────────────────────────────


class TestConfigGeneration:
    def test_generates_valid_yaml_per_faction(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        db_path = tmp_path / "alpha.db"
        config_path = env._generate_faction_config(
            "alpha", PERSONAS_DIR / "alpha.txt", db_path
        )

        assert config_path.is_file()
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["faction_id"] == "alpha"
        assert config["database"]["path"] == str(db_path)

    def test_faction_prompt_points_to_persona(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        persona_path = PERSONAS_DIR / "beta.txt"
        config_path = env._generate_faction_config(
            "beta", persona_path, tmp_path / "beta.db"
        )
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["paths"]["faction_prompt"] == str(persona_path)

    def test_all_factions_get_same_module_classes(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        configs = {}
        for fid in ("alpha", "beta", "gamma"):
            path = env._generate_faction_config(
                fid, PERSONAS_DIR / f"{fid}.txt", tmp_path / f"{fid}.db"
            )
            configs[fid] = yaml.safe_load(path.read_text(encoding="utf-8"))

        # All factions should have identical module classes.
        for key in ("generator", "primary_analyst", "adversarial", "review_gate"):
            classes = {c["modules"][key]["class"] for c in configs.values()}
            assert len(classes) == 1, f"Module {key} differs across factions: {classes}"

    def test_debounce_is_fast(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        config_path = env._generate_faction_config(
            "alpha", PERSONAS_DIR / "alpha.txt", tmp_path / "alpha.db"
        )
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["message_debounce_seconds"] == 0.01


# ── Broadcast ────────────────────────────────────────────────────────


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_excludes_sender(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        # Manually set up transports without full Orchestrator.
        from tests.self_play.game_environment import AgentHandle

        for fid in ("alpha", "beta", "gamma"):
            env.agents[fid] = AgentHandle(
                faction_id=fid,
                orchestrator=None,  # type: ignore[arg-type]
                transport=TestTransport(),
                task=None,  # type: ignore[arg-type]
            )

        await env.broadcast("alpha", "Hello from Alpha")

        # Alpha should NOT receive its own message.
        alpha_msgs = await env.agents["alpha"].transport.get_output()
        alpha_input: list = []
        try:
            while True:
                alpha_input.append(env.agents["alpha"].transport._input.get_nowait())
        except asyncio.QueueEmpty:
            pass
        assert len(alpha_input) == 0

        # Beta and Gamma SHOULD receive the message.
        for fid in ("beta", "gamma"):
            items: list = []
            try:
                while True:
                    items.append(env.agents[fid].transport._input.get_nowait())
            except asyncio.QueueEmpty:
                pass
            assert len(items) == 1
            assert items[0].content == "Hello from Alpha"
            assert items[0].sender_faction == "alpha"

    @pytest.mark.asyncio
    async def test_broadcast_to_all_includes_sender(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        from tests.self_play.game_environment import AgentHandle

        for fid in ("alpha", "beta"):
            env.agents[fid] = AgentHandle(
                faction_id=fid,
                orchestrator=None,  # type: ignore[arg-type]
                transport=TestTransport(),
                task=None,  # type: ignore[arg-type]
            )

        await env.broadcast_to_all("moderator", "Game starting")

        for fid in ("alpha", "beta"):
            items: list = []
            try:
                while True:
                    items.append(env.agents[fid].transport._input.get_nowait())
            except asyncio.QueueEmpty:
                pass
            assert len(items) == 1
            assert items[0].content == "Game starting"

    @pytest.mark.asyncio
    async def test_broadcast_appends_to_channel_log(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        from tests.self_play.game_environment import AgentHandle

        env.agents["alpha"] = AgentHandle(
            faction_id="alpha",
            orchestrator=None,  # type: ignore[arg-type]
            transport=TestTransport(),
            task=None,  # type: ignore[arg-type]
        )

        await env.broadcast("beta", "Test message")
        assert len(env.channel_log) == 1
        assert env.channel_log[0]["sender"] == "beta"
        assert env.channel_log[0]["content"] == "Test message"


# ── Scenario data ────────────────────────────────────────────────────


class TestScenario:
    def test_seed_message_mentions_all_factions(self) -> None:
        assert "Alpha" in SEED_MESSAGE
        assert "Beta" in SEED_MESSAGE
        assert "Gamma" in SEED_MESSAGE

    def test_round_updates_cover_all_rounds(self) -> None:
        for r in (1, 2, 3, 4):
            assert r in ROUND_UPDATES
            assert len(ROUND_UPDATES[r]) > 20

    def test_final_round_says_binding(self) -> None:
        assert "binding" in ROUND_UPDATES[4].lower()


# ── Persona files ────────────────────────────────────────────────────


class TestPersonas:
    @pytest.mark.parametrize("faction", ["alpha", "beta", "gamma"])
    def test_persona_file_exists(self, faction: str) -> None:
        path = PERSONAS_DIR / f"{faction}.txt"
        assert path.is_file(), f"Missing persona: {path}"

    @pytest.mark.parametrize("faction", ["alpha", "beta", "gamma"])
    def test_persona_has_round_context_marker(self, faction: str) -> None:
        text = (PERSONAS_DIR / f"{faction}.txt").read_text(encoding="utf-8")
        assert "## CURRENT ROUND CONTEXT" in text

    @pytest.mark.parametrize("faction", ["alpha", "beta", "gamma"])
    def test_persona_mentions_faction_name(self, faction: str) -> None:
        text = (PERSONAS_DIR / f"{faction}.txt").read_text(encoding="utf-8")
        assert faction.capitalize() in text


# ── Full round lifecycle (fake-backed) ───────────────────────────────


class TestRoundLifecycle:
    @pytest.mark.asyncio
    async def test_setup_creates_agents(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        await env.setup()
        try:
            assert len(env.agents) == 3
            for fid in ("alpha", "beta", "gamma"):
                assert fid in env.agents
                assert env.agents[fid].orchestrator is not None
                assert env.agents[fid].transport is not None
        finally:
            await env.teardown()

    @pytest.mark.asyncio
    async def test_single_round_produces_responses(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        await env.setup()
        try:
            # Seed message so agents have context.
            await env.broadcast_to_all("moderator", SEED_MESSAGE)
            await asyncio.sleep(0.05)

            responses = await env.run_round(1)
            # At least some agents should respond (FakeLLMClient always succeeds).
            assert isinstance(responses, dict)
        finally:
            await env.teardown()

    @pytest.mark.asyncio
    async def test_collect_results_structure(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        await env.setup()
        try:
            results = await env.collect_results()
            assert "agents" in results
            assert "transcript" in results
            assert "faction_models" in results
            for fid in ("alpha", "beta", "gamma"):
                assert fid in results["agents"]
                agent_data = results["agents"][fid]
                assert "promises" in agent_data
                assert "coalitions" in agent_data
                assert "inconsistencies" in agent_data
                assert "intelligence" in agent_data
        finally:
            await env.teardown()

    @pytest.mark.asyncio
    async def test_collect_results_emits_faction_models(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        # Pin env defaults so the fallback assertion is deterministic.
        monkeypatch.delenv("DIPLOMAT_PRIMARY_PROVIDER", raising=False)
        monkeypatch.delenv("DIPLOMAT_PRIMARY_COMMODITY_MODEL", raising=False)
        env = _make_env(tmp_path)
        # alpha overridden; beta/gamma fall back to env-default primary commodity.
        env.per_faction_providers = {
            "alpha": {"provider": "anthropic", "model": "claude-haiku-4-5"}
        }
        await env.setup()
        try:
            results = await env.collect_results()
            faction_models = results["faction_models"]
            assert faction_models["alpha"] == {
                "provider": "anthropic",
                "model": "claude-haiku-4-5",
            }
            assert faction_models["beta"] == {
                "provider": "openai",
                "model": "gpt-4.1-mini",
            }
            assert faction_models["gamma"] == {
                "provider": "openai",
                "model": "gpt-4.1-mini",
            }
        finally:
            await env.teardown()

    @pytest.mark.asyncio
    async def test_teardown_stops_agents(self, tmp_path: Path) -> None:
        env = _make_env(tmp_path)
        await env.setup()
        tasks = [h.task for h in env.agents.values()]
        await env.teardown()

        # All tasks should be done (cancelled or finished).
        await asyncio.sleep(0.1)
        for t in tasks:
            assert t.done()


# ── Analysis ─────────────────────────────────────────────────────────


class TestAnalysis:
    def test_analyze_results_runs_without_error(self, capsys) -> None:
        from tests.self_play.analysis import analyze_results

        results = {
            "rounds_completed": 2,
            "transcript": [
                {"sender": "alpha", "channel": "public", "content": "Hello"},
                {"sender": "beta", "channel": "public", "content": "Hi"},
            ],
            "agents": {
                "alpha": {
                    "promises": [],
                    "coalitions": [],
                    "inconsistencies": [],
                    "intelligence": [],
                    "round": 3,
                },
                "beta": {
                    "promises": [
                        {
                            "from_faction": "alpha",
                            "to_faction": "beta",
                            "status": "pending",
                            "description": "Support in round 2",
                        }
                    ],
                    "coalitions": [],
                    "inconsistencies": [],
                    "intelligence": [],
                    "round": 3,
                },
            },
            "round_responses": {
                "1": {"alpha": "Response A", "beta": "Response B"},
                "2": {"alpha": "Response A2", "beta": "Response B2"},
            },
        }

        analyze_results(results)
        captured = capsys.readouterr()
        assert "SELF-PLAY ANALYSIS REPORT" in captured.out
        assert "alpha" in captured.out.lower()
        assert "beta" in captured.out.lower()

    def test_analyze_results_renders_no_deal_aware_scoring(self, capsys) -> None:
        from tests.self_play.analysis import analyze_results

        results = _process_signature_results()
        results["scores"].update(
            {
                "pareto_efficiency": 0.500,
                "negotiated_surplus_share": 0.000,
                "delta_above_batna_sum": 4.000,
                "min_faction_delta": 0.000,
                "surplus_distribution_stdev": 2.000,
                "faction_deltas": {"alpha": 0.0, "beta": 4.0},
                "faction_ranks": {"alpha": 2, "beta": 1},
                "equal_split_baseline": 10.0,
                "vs_equal_split": {"alpha": 0.0, "beta": 4.0},
                "skill_premium_vs_batna": {"alpha": 0.0, "beta": 1.0},
                "nash_deal_sum": 20.0,
                "nash_product": 24.0,
                "vs_nash_efficiency": 1.0,
                "nash_deal_scores": {"alpha": 10.0, "beta": 10.0},
            }
        )

        analyze_results(results)

        captured = capsys.readouterr()
        assert "NO-DEAL-AWARE SCORING" in captured.out
        assert "negotiated_surplus_share: 0.000" in captured.out
        assert "delta_above_batna_sum: 4.000" in captured.out
        assert "min_faction_delta: 0.000" in captured.out
        assert "surplus_distribution_stdev: 2.000" in captured.out
        assert "alpha: +0.000" in captured.out
        assert "beta: +4.000" in captured.out
        assert "faction_ranks" in captured.out
        assert "1. beta" in captured.out
        assert "BASELINE COMPARISONS" in captured.out
        assert "equal_split_baseline: 10.000" in captured.out
        assert "skill_premium_vs_batna" in captured.out
        assert "nash_deal_sum: 20.000" in captured.out


# ── Pareto efficiency scoring ───────────────────────────────────────


class TestParetoEfficiency:
    def test_optimal_deal_returns_full_efficiency(self) -> None:
        from tests.self_play.game_environment import _pareto_efficiency_metrics

        metrics = _pareto_efficiency_metrics(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 10, "batna": 4},
                    "beta": {"points": 10, "batna": 6},
                },
            },
        )

        assert metrics["max_pareto_sum"] == 20
        assert metrics["achieved_score_sum"] == 20
        assert metrics["pareto_efficiency"] == 1.0
        assert metrics["negotiated_surplus_share"] == 1.0

    def test_batna_sum_returns_batna_to_pareto_ratio(self) -> None:
        from tests.self_play.game_environment import _pareto_efficiency_metrics

        metrics = _pareto_efficiency_metrics(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 4, "batna": 4},
                    "beta": {"points": 6, "batna": 6},
                },
            },
        )

        assert metrics["achieved_score_sum"] == 10
        assert metrics["pareto_efficiency"] == pytest.approx(0.5)
        assert metrics["sum_batnas"] == 10
        assert metrics["faction_deltas"] == {"alpha": 0.0, "beta": 0.0}
        assert metrics["delta_above_batna_sum"] == 0.0
        assert metrics["min_faction_delta"] == 0.0
        assert metrics["surplus_distribution_stdev"] == 0.0
        assert metrics["negotiated_surplus_share"] == 0.0

    def test_no_deal_case_uses_returned_batna_scores(self) -> None:
        from tests.self_play.game_environment import _pareto_efficiency_metrics

        metrics = _pareto_efficiency_metrics(
            _pareto_scenario(),
            {
                "deal_reached": False,
                "faction_scores": {
                    "alpha": {"points": 4, "batna": 4},
                    "beta": {"points": 6, "batna": 6},
                },
            },
        )

        assert metrics["pareto_efficiency"] == pytest.approx(0.5)
        assert metrics["negotiated_surplus_share"] == 0.0

    def test_below_batna_case_returns_negative_surplus_share(self) -> None:
        from tests.self_play.game_environment import _pareto_efficiency_metrics

        metrics = _pareto_efficiency_metrics(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 3, "batna": 4},
                    "beta": {"points": 6, "batna": 6},
                },
            },
        )

        assert metrics["faction_deltas"] == {"alpha": -1.0, "beta": 0.0}
        assert metrics["delta_above_batna_sum"] == -1.0
        assert metrics["min_faction_delta"] == -1.0
        assert metrics["surplus_distribution_stdev"] == pytest.approx(0.5)
        assert metrics["negotiated_surplus_share"] == pytest.approx(-0.1)

    def test_zero_surplus_denominator_returns_zero_share(self) -> None:
        from tests.self_play.game_environment import _pareto_efficiency_metrics

        scenario = _pareto_scenario()
        scenario["batna"] = {"alpha": 10, "beta": 10}

        metrics = _pareto_efficiency_metrics(
            scenario,
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 10, "batna": 10},
                    "beta": {"points": 10, "batna": 10},
                },
            },
        )

        assert metrics["max_pareto_sum"] == 20
        assert metrics["sum_batnas"] == 20
        assert metrics["negotiated_surplus_share"] == 0.0


class TestResolveDealScores:
    def test_full_agreement_scores_the_deal(self) -> None:
        from tests.self_play.game_environment import _resolve_deal_scores

        out = _resolve_deal_scores(
            _pareto_scenario(),
            {"deal_reached": True, "agreed_outcomes": {"resource_split": "optimum"}},
        )
        assert out["deal_reached"] is True
        assert out["faction_scores"]["alpha"]["points"] == 10
        assert out["faction_scores"]["beta"]["points"] == 10

    def test_no_deal_is_all_batna(self) -> None:
        from tests.self_play.game_environment import _resolve_deal_scores

        out = _resolve_deal_scores(_pareto_scenario(), {"deal_reached": False})
        assert out["deal_reached"] is False
        assert out["faction_scores"]["alpha"]["points"] == 4  # BATNA
        assert out["faction_scores"]["beta"]["points"] == 6

    def test_partial_coalition_without_values_marked_no_deal(self) -> None:
        # The succ_1 anomaly: deal_reached True + partial coalition + no
        # coalition_values must score at BATNA AND normalize deal_reached False.
        from tests.self_play.game_environment import _resolve_deal_scores

        out = _resolve_deal_scores(
            _three_faction_nash_scenario(),
            {
                "deal_reached": True,
                "agreed_outcomes": {"resource_split": "balanced"},
                "coalition_members": ["alpha", "beta"],
            },
        )
        assert out["deal_reached"] is False
        assert out["no_deal_reason"] == "partial_coalition_without_coalition_values"
        assert all(
            out["faction_scores"][f]["points"] == 0
            for f in ("alpha", "beta", "gamma")
        )
        # coalition_members preserved for transparency
        assert out["coalition_members"] == ["alpha", "beta"]

    def test_deal_reached_without_outcomes_marked_no_deal(self) -> None:
        from tests.self_play.game_environment import _resolve_deal_scores

        out = _resolve_deal_scores(_pareto_scenario(), {"deal_reached": True})
        assert out["deal_reached"] is False
        assert out["no_deal_reason"] == "deal_reached_without_agreed_outcomes"
        assert out["faction_scores"]["alpha"]["points"] == 4

    def test_deal_below_batna_for_a_faction_marked_no_deal(self) -> None:
        # The succ2 case: an "agreement" that leaves a faction below its BATNA
        # (e.g. covering only a subset of issues) is not a real deal.
        from tests.self_play.game_environment import _resolve_deal_scores

        scenario = {
            "factions": ["alpha", "beta"],
            "issues": [{"name": "x", "outcomes": ["a", "b"]}],
            "scoring": {
                "alpha": {"x": {"a": 10, "b": 1}},
                "beta": {"x": {"a": 1, "b": 10}},
            },
            "batna": {"alpha": 5, "beta": 5},
        }
        out = _resolve_deal_scores(
            scenario, {"deal_reached": True, "agreed_outcomes": {"x": "b"}}
        )
        assert out["deal_reached"] is False  # alpha scores 1 < BATNA 5
        assert out["no_deal_reason"] == "deal_below_batna_for_some_faction"
        assert out["faction_scores"]["alpha"]["points"] == 5
        assert out["faction_scores"]["beta"]["points"] == 5


class TestRankAmongFactions:
    def test_distinct_scores_rank_descending(self) -> None:
        from tests.self_play.game_environment import _rank_among_factions

        result = _rank_among_factions(
            _three_faction_nash_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 100, "batna": 0},
                    "beta": {"points": 30, "batna": 0},
                    "gamma": {"points": 1, "batna": 0},
                },
            },
        )

        assert result["faction_ranks"] == {"alpha": 1, "beta": 2, "gamma": 3}
        assert result["ranked_factions"] == ["alpha", "beta", "gamma"]

    def test_ties_use_competition_ranking(self) -> None:
        from tests.self_play.game_environment import _rank_among_factions

        result = _rank_among_factions(
            _three_faction_nash_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 30, "batna": 0},
                    "beta": {"points": 30, "batna": 0},
                    "gamma": {"points": 1, "batna": 0},
                },
            },
        )

        # alpha and beta tie for 1st; gamma is 3rd (competition ranking skips 2).
        assert result["faction_ranks"] == {"alpha": 1, "beta": 1, "gamma": 3}

    def test_ranks_by_absolute_points_not_delta(self) -> None:
        from tests.self_play.game_environment import _rank_among_factions

        # beta has the larger gain over BATNA (+7 vs alpha's +1) but lower
        # absolute points; the literal §3.5 lens ranks by absolute points.
        result = _rank_among_factions(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 9, "batna": 8},
                    "beta": {"points": 7, "batna": 0},
                },
            },
        )

        assert result["faction_ranks"] == {"alpha": 1, "beta": 2}


class TestBaselines:
    def test_equal_split_baseline_shows_gain_and_loss(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        scenario = _pareto_scenario()
        scenario["scoring"]["alpha"]["resource_split"]["optimum"] = 12
        scenario["scoring"]["beta"]["resource_split"]["optimum"] = 8

        metrics = _compute_baselines(
            scenario,
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 12, "batna": 4},
                    "beta": {"points": 8, "batna": 6},
                },
            },
        )

        assert metrics["equal_split_baseline"] == 10
        assert metrics["vs_equal_split"] == {"alpha": 2.0, "beta": -2.0}

    def test_equal_split_baseline_is_negative_when_no_deal_occurs(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        metrics = _compute_baselines(
            _pareto_scenario(),
            {
                "deal_reached": False,
                "faction_scores": {
                    "alpha": {"points": 4, "batna": 4},
                    "beta": {"points": 6, "batna": 6},
                },
            },
        )

        assert metrics["vs_equal_split"] == {"alpha": -6.0, "beta": -4.0}

    def test_batna_clearing_skill_premium_ranges_to_one_at_optimum(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        metrics = _compute_baselines(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 10, "batna": 4},
                    "beta": {"points": 10, "batna": 6},
                },
            },
        )

        assert metrics["max_possible_per_faction"] == {"alpha": 10, "beta": 10}
        assert metrics["skill_premium_vs_batna"] == {"alpha": 1.0, "beta": 1.0}

    def test_batna_clearing_skill_premium_is_zero_at_batna(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        metrics = _compute_baselines(
            _pareto_scenario(),
            {
                "deal_reached": False,
                "faction_scores": {
                    "alpha": {"points": 4, "batna": 4},
                    "beta": {"points": 6, "batna": 6},
                },
            },
        )

        assert metrics["skill_premium_vs_batna"] == {"alpha": 0.0, "beta": 0.0}

    def test_nash_matches_pareto_optimum_for_two_factions_one_issue(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        metrics = _compute_baselines(
            _pareto_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 10, "batna": 4},
                    "beta": {"points": 10, "batna": 6},
                },
            },
        )

        assert metrics["nash_deal_scores"] == {"alpha": 10, "beta": 10}
        assert metrics["nash_deal_sum"] == 20
        assert metrics["nash_product"] == 24.0
        assert metrics["vs_nash_efficiency"] == 1.0

    def test_nash_fields_are_none_when_no_deal_clears_all_batnas(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        scenario = _pareto_scenario()
        scenario["batna"] = {"alpha": 10, "beta": 10}

        metrics = _compute_baselines(
            scenario,
            {
                "deal_reached": False,
                "faction_scores": {
                    "alpha": {"points": 10, "batna": 10},
                    "beta": {"points": 10, "batna": 10},
                },
            },
        )

        assert metrics["nash_deal_scores"] is None
        assert metrics["nash_deal_sum"] is None
        assert metrics["nash_product"] is None
        assert metrics["vs_nash_efficiency"] is None

    def test_nash_can_differ_from_sum_maximizing_deal(self) -> None:
        from tests.self_play.game_environment import _compute_baselines

        metrics = _compute_baselines(
            _three_faction_nash_scenario(),
            {
                "deal_reached": True,
                "faction_scores": {
                    "alpha": {"points": 100, "batna": 0},
                    "beta": {"points": 1, "batna": 0},
                    "gamma": {"points": 1, "batna": 0},
                },
            },
        )

        assert metrics["nash_deal_scores"] == {
            "alpha": 30,
            "beta": 30,
            "gamma": 30,
        }
        assert metrics["nash_deal_sum"] == 90
        assert metrics["nash_product"] == 27000.0
        assert metrics["vs_nash_efficiency"] == pytest.approx(102 / 90)

    @pytest.mark.asyncio
    async def test_score_game_outputs_numeric_pareto_efficiency(
        self, tmp_path: Path
    ) -> None:
        env = _make_env(
            tmp_path,
            llm_responses=[
                {
                    "deal_reached": True,
                    "agreed_outcomes": {"resource_split": "optimum"},
                    "faction_scores": {
                        "alpha": {"points": 10, "batna": 4},
                        "beta": {"points": 10, "batna": 6},
                    },
                    "reasoning": "All factions agreed to the optimum.",
                }
            ],
            scenario_analysis=_pareto_scenario(),
        )

        scores = await env.score_game(
            {
                "alpha": "We agree to optimum.",
                "beta": "We agree to optimum.",
            }
        )

        assert isinstance(scores["pareto_efficiency"], float)
        assert scores["pareto_efficiency"] == 1.0
        assert scores["max_pareto_sum"] == 20


def _coalition_scenario() -> dict:
    # 3-faction coalition-coercive: AB pair has defined coalition value,
    # AC and BC do not (will fall through to no-deal at BATNA).
    return {
        "factions": ["a", "b", "c"],
        "issues": [{"name": "coalition_choice", "outcomes": ["form", "skip"]}],
        "scoring": {
            "a": {"coalition_choice": {"form": 7, "skip": 0}},
            "b": {"coalition_choice": {"form": 7, "skip": 0}},
            "c": {"coalition_choice": {"form": 7, "skip": 0}},
        },
        "batna": {"a": 2, "b": 2, "c": 2},
        "coalition_values": [
            {"members": ["a", "b"], "values": {"a": 9, "b": 10}},
        ],
    }


@pytest.mark.asyncio
async def test_score_game_partial_coalition_with_values(tmp_path: Path) -> None:
    # AB coalition forms; coalition_values defines AB -> a:9, b:10. C dissents.
    env = _make_env(
        tmp_path,
        llm_responses=[{
            "deal_reached": True,
            "agreed_outcomes": {"coalition_choice": "form"},
            "coalition_members": ["a", "b"],
            "reasoning": "A and B agreed; C dissented.",
        }],
        scenario_analysis=_coalition_scenario(),
    )

    scores = await env.score_game({"a": "form", "b": "form", "c": "skip"})

    fs = scores["faction_scores"]
    assert fs["a"]["points"] == 9
    assert fs["b"]["points"] == 10
    assert fs["c"]["points"] == 2  # excluded -> BATNA
    assert fs["c"]["batna"] == 2


@pytest.mark.asyncio
async def test_score_game_partial_coalition_without_matching_values_falls_back_to_batna(
    tmp_path: Path,
) -> None:
    # AC coalition forms; coalition_values has NO entry for AC -> all at BATNA.
    env = _make_env(
        tmp_path,
        llm_responses=[{
            "deal_reached": True,
            "agreed_outcomes": {"coalition_choice": "form"},
            "coalition_members": ["a", "c"],
            "reasoning": "A and C agreed; B dissented. No coalition_values for AC.",
        }],
        scenario_analysis=_coalition_scenario(),
    )

    scores = await env.score_game({"a": "form", "b": "skip", "c": "form"})

    fs = scores["faction_scores"]
    assert fs["a"]["points"] == 2  # all fall back to BATNA
    assert fs["b"]["points"] == 2
    assert fs["c"]["points"] == 2


@pytest.mark.asyncio
async def test_score_game_full_agreement_ignores_coalition_members(
    tmp_path: Path,
) -> None:
    # All 3 factions agree; coalition_members may be returned but is not a strict
    # subset -> falls through to standard faction_score() path.
    env = _make_env(
        tmp_path,
        llm_responses=[{
            "deal_reached": True,
            "agreed_outcomes": {"coalition_choice": "form"},
            "coalition_members": ["a", "b", "c"],  # full set; not partial
            "reasoning": "All three converged.",
        }],
        scenario_analysis=_coalition_scenario(),
    )

    scores = await env.score_game({"a": "form", "b": "form", "c": "form"})

    fs = scores["faction_scores"]
    # faction_score(form) = 7 for each per the scenario.
    assert fs["a"]["points"] == 7
    assert fs["b"]["points"] == 7
    assert fs["c"]["points"] == 7


@pytest.mark.asyncio
async def test_score_game_no_deal_all_batna(tmp_path: Path) -> None:
    env = _make_env(
        tmp_path,
        llm_responses=[{
            "deal_reached": False,
            "reasoning": "No agreement reached.",
        }],
        scenario_analysis=_coalition_scenario(),
    )

    scores = await env.score_game({"a": "skip", "b": "skip", "c": "skip"})

    fs = scores["faction_scores"]
    assert fs["a"]["points"] == 2
    assert fs["b"]["points"] == 2
    assert fs["c"]["points"] == 2


# ── Process signatures ──────────────────────────────────────────────


class TestProcessSignatures:
    def test_broken_promise_rate(self) -> None:
        from tests.self_play.analysis import compute_process_signatures

        signatures = compute_process_signatures(_process_signature_results())

        assert signatures["broken_promise_rate"] == pytest.approx(0.25)

    def test_coalition_stability(self) -> None:
        from tests.self_play.analysis import compute_process_signatures

        signatures = compute_process_signatures(_process_signature_results())

        assert signatures["coalition_stability"] == pytest.approx(0.5)

    def test_time_to_deal(self) -> None:
        from tests.self_play.analysis import compute_process_signatures

        signatures = compute_process_signatures(_process_signature_results())

        assert signatures["time_to_deal"] == 3

    def test_opening_gap(self) -> None:
        from tests.self_play.analysis import compute_process_signatures

        signatures = compute_process_signatures(_process_signature_results())

        assert signatures["opening_gap"]["alpha"] == pytest.approx(0.6)
        assert signatures["opening_gap"]["beta"] == pytest.approx(0.4)


# ── LoggingLLMClient ─────────────────────────────────────────────────


class _StubInner:
    """Minimal async LLM client stub for LoggingLLMClient tests."""

    def __init__(self, response: str = "ok") -> None:
        self._response = response
        self.calls: list[dict] = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class TestLoggingLLMClient:
    @pytest.mark.asyncio
    async def test_records_call_with_current_faction(self) -> None:
        from tests.self_play.game_environment import LoggingLLMClient

        inner = _StubInner("response-text")
        client = LoggingLLMClient(inner)
        client.set_faction("alpha")

        result = await client.complete(
            messages=[{"role": "user", "content": "hi"}],
            config={"provider": "openai"},
            tier="commodity",
            max_tokens=100,
        )

        assert result == "response-text"
        assert len(client.call_log) == 1
        record = client.call_log[0]
        assert record.faction_id == "alpha"
        assert record.config_provider == "openai"
        assert record.response == "response-text"
        assert record.error is None

    @pytest.mark.asyncio
    async def test_records_error_and_reraises(self) -> None:
        from tests.self_play.game_environment import LoggingLLMClient

        class _FailInner:
            async def complete(self, **kwargs):
                raise RuntimeError("boom")

        client = LoggingLLMClient(_FailInner())
        client.set_faction("beta")

        with pytest.raises(RuntimeError, match="boom"):
            await client.complete(
                messages=[{"role": "user", "content": "x"}],
                config={"provider": "anthropic"},
                tier=None,
            )

        assert len(client.call_log) == 1
        assert client.call_log[0].error == "boom"
        assert client.call_log[0].faction_id == "beta"

    @pytest.mark.asyncio
    async def test_snapshot_faction_survives_concurrent_set(self) -> None:
        """If set_faction is called *after* complete starts, the log
        still records the faction that was set *before* the call started.

        This guards against a race where two TaggedLLMClient wrappers
        interleave: each sets its own tag, then awaits; without the
        snapshot, both records would show the second wrapper's tag.
        """
        from tests.self_play.game_environment import LoggingLLMClient

        # An inner stub that pauses long enough for an external set_faction
        # to fire between start and finish.
        class _PausingInner:
            async def complete(self, **kwargs):
                await asyncio.sleep(0.05)
                return "done"

        client = LoggingLLMClient(_PausingInner())
        client.set_faction("alpha")

        async def call() -> str:
            return await client.complete(
                messages=[{"role": "user", "content": "x"}],
                config={"provider": "openai"},
                tier=None,
            )

        async def stomp_after_delay() -> None:
            # Give complete() time to enter and snapshot, then change the tag.
            await asyncio.sleep(0.01)
            client.set_faction("beta")

        results = await asyncio.gather(call(), stomp_after_delay())
        assert results[0] == "done"
        # The call started with "alpha"; the log should still say "alpha"
        # even though _current_faction is now "beta".
        assert len(client.call_log) == 1
        assert client.call_log[0].faction_id == "alpha"
        assert client._current_faction == "beta"

    @pytest.mark.asyncio
    async def test_attribution_overrides_current_faction(self) -> None:
        from tests.self_play.game_environment import LoggingLLMClient
        inner = _StubInner("ok")
        client = LoggingLLMClient(inner)
        client.set_faction("alpha")

        await client.complete(
            messages=[{"role": "user", "content": "reconcile"}],
            config={"provider": "openai"},
            tier="commodity",
            attribution="recon:alpha",
        )

        assert len(client.call_log) == 1
        assert client.call_log[0].faction_id == "recon:alpha"
        assert inner.calls[0]["attribution"] == "recon:alpha"

    @pytest.mark.asyncio
    async def test_two_attributed_calls_dont_cross_tags_concurrently(self) -> None:
        from tests.self_play.game_environment import LoggingLLMClient

        class _PausingInner:
            async def complete(self, **kwargs):
                await asyncio.sleep(0.02)
                return "ok"

        client = LoggingLLMClient(_PausingInner())

        await asyncio.gather(
            client.complete(
                messages=[{"role": "user", "content": "a"}],
                config={"provider": "openai"},
                tier=None,
                attribution="recon:alpha",
            ),
            client.complete(
                messages=[{"role": "user", "content": "b"}],
                config={"provider": "openai"},
                tier=None,
                attribution="recon:beta",
            ),
        )

        assert len(client.call_log) == 2
        tags = sorted(r.faction_id for r in client.call_log)
        assert tags == ["recon:alpha", "recon:beta"]


class TestWriteResultsMetadata:
    """Unit tests for _write_results cost metadata (Phase 49)."""

    def test_dry_run_writes_dry_run_metadata(self, tmp_path: Path) -> None:
        from tests.self_play.run_simulation import _write_results

        results: dict = {"llm_call_log": [{"x": 1}, {"x": 2}]}
        out = str(tmp_path / "result.json")
        _write_results(results, out, accountant=None)

        import json
        written = json.loads(Path(out).read_text())
        meta = written["metadata"]
        assert meta["cost_source"] == "dry_run"
        assert meta["cost_usd"] == 0.0
        assert meta["n_llm_calls"] == 2

    def test_metered_writes_session_total(self, tmp_path: Path) -> None:
        from tests.self_play.run_simulation import _write_results

        accountant = FakeCostAccountant(session_total=1.23)
        results: dict = {"llm_call_log": [{"x": 1}]}
        out = str(tmp_path / "result.json")
        _write_results(results, out, accountant=accountant)

        import json
        written = json.loads(Path(out).read_text())
        meta = written["metadata"]
        assert meta["cost_source"] == "metered"
        assert meta["cost_usd"] == pytest.approx(1.23)
        assert meta["n_llm_calls"] == 1

    def test_empty_llm_call_log_gives_zero_count(self, tmp_path: Path) -> None:
        from tests.self_play.run_simulation import _write_results

        results: dict = {}
        out = str(tmp_path / "result.json")
        _write_results(results, out, accountant=None)

        import json
        written = json.loads(Path(out).read_text())
        assert written["metadata"]["n_llm_calls"] == 0

    def test_fake_cost_accountant_session_total_property(self) -> None:
        fake = FakeCostAccountant(session_total=3.50)
        assert fake.session_total == pytest.approx(3.50)

    def test_fake_cost_accountant_default_session_total_is_zero(self) -> None:
        fake = FakeCostAccountant()
        assert fake.session_total == 0.0


class TestBackfillCost:
    """Unit tests for tools/backfill_cost.py (Phase 49.3)."""

    def _make_result(
        self,
        log_entries: list | None = None,
        faction_models: dict | None = None,
        metadata: dict | None = None,
    ) -> dict:
        result: dict = {}
        if log_entries is not None:
            result["llm_call_log"] = log_entries
        if faction_models is not None:
            result["faction_models"] = faction_models
        if metadata is not None:
            result["metadata"] = metadata
        return result

    def _make_log_entry(
        self,
        faction_id: str = "alpha",
        provider: str = "openai",
        content: str = "a" * 400,  # 100 input tokens
        response: str = "b" * 200,  # 50 output tokens
    ) -> dict:
        return {
            "faction_id": faction_id,
            "config_provider": provider,
            "tier": "commodity",
            "messages": [{"role": "user", "content": content}],
            "response": response,
        }

    def test_estimate_cost_from_empty_log(self) -> None:
        from tools.backfill_cost import estimate_cost_from_log

        result = self._make_result(log_entries=[])
        cost, n_calls = estimate_cost_from_log(result)
        assert cost == pytest.approx(0.0)
        assert n_calls == 0

    def test_estimate_cost_nonzero_for_nonempty_log(self) -> None:
        from tools.backfill_cost import estimate_cost_from_log

        result = self._make_result(log_entries=[self._make_log_entry()])
        cost, n_calls = estimate_cost_from_log(result)
        assert cost > 0.0
        assert n_calls == 1

    def test_estimate_cost_uses_faction_models(self) -> None:
        """Faction model resolution uses faction_models when available."""
        from tools.backfill_cost import estimate_cost_from_log

        # anthropic pricing differs from openai; faction_models overrides config_provider
        entry_openai = self._make_log_entry(faction_id="alpha", provider="openai")
        result_with_fm = self._make_result(
            log_entries=[entry_openai],
            faction_models={"alpha": {"model": "claude-sonnet-4-6", "provider": "anthropic"}},
        )
        result_without_fm = self._make_result(log_entries=[entry_openai])

        cost_with_fm, _ = estimate_cost_from_log(result_with_fm)
        cost_without_fm, _ = estimate_cost_from_log(result_without_fm)

        # claude-sonnet-4-6 is priced higher than gpt-4.1-mini
        assert cost_with_fm > cost_without_fm

    def test_backfill_result_writes_metadata(self, tmp_path: Path) -> None:
        from tools.backfill_cost import backfill_result

        result = self._make_result(log_entries=[self._make_log_entry()])
        path = tmp_path / "run.json"
        path.write_text(json.dumps(result), encoding="utf-8")

        status = backfill_result(result, write_back=True, path=path)

        assert "estimated" in status or "wrote" in status
        written = json.loads(path.read_text())
        meta = written["metadata"]
        assert meta["cost_source"] == "estimated_from_log"
        assert meta["cost_usd"] > 0.0
        assert meta["n_llm_calls"] == 1

    def test_backfill_result_idempotent_for_metered(self, tmp_path: Path) -> None:
        from tools.backfill_cost import backfill_result

        result = self._make_result(
            log_entries=[self._make_log_entry()],
            metadata={"cost_usd": 9.99, "cost_source": "metered", "n_llm_calls": 5},
        )
        path = tmp_path / "run.json"
        path.write_text(json.dumps(result), encoding="utf-8")

        status = backfill_result(result, write_back=False, path=path)

        assert "skipped" in status
        # File unchanged (write_back=False and skipped anyway)
        written = json.loads(path.read_text())
        assert written["metadata"]["cost_usd"] == pytest.approx(9.99)

    def test_backfill_result_preserves_existing_metadata_keys(self, tmp_path: Path) -> None:
        from tools.backfill_cost import backfill_result

        result = self._make_result(
            log_entries=[self._make_log_entry()],
            metadata={"recovery": [{"tool": "rescore_run.py"}]},
        )
        path = tmp_path / "run.json"
        path.write_text(json.dumps(result), encoding="utf-8")

        backfill_result(result, write_back=True, path=path)

        written = json.loads(path.read_text())
        meta = written["metadata"]
        # Existing key preserved
        assert "recovery" in meta
        assert meta["recovery"] == [{"tool": "rescore_run.py"}]
        # Cost keys added
        assert meta["cost_source"] == "estimated_from_log"

    def test_estimate_cost_no_faction_models_uses_provider_default(self) -> None:
        """Without faction_models, cost is estimated from provider default model."""
        from tools.backfill_cost import estimate_cost_from_log

        # Two entries same content, different providers → different cost
        entry_google = self._make_log_entry(faction_id="alpha", provider="google")
        entry_openai = self._make_log_entry(faction_id="alpha", provider="openai")

        cost_google, _ = estimate_cost_from_log(self._make_result(log_entries=[entry_google]))
        cost_openai, _ = estimate_cost_from_log(self._make_result(log_entries=[entry_openai]))

        # gemini-2.5-flash-lite ($0.1/$0.4) vs gpt-4.1-mini ($0.4/$1.6) — openai costs more
        assert cost_openai > cost_google

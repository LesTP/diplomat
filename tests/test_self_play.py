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

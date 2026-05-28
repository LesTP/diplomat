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
    )


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

"""Tests for the reverse scenario builder search loop."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from modules.persona import FileBasedPersona
from tools.scenario_builder import _search_loop, build_and_save_scenario
from tools.scenario_fitness import compute_fitness
from tools.scenario_spec import IssueSpec, ScenarioSpec

from tests.self_play.verify_scenario_optimum import enumerate_deals, find_pareto_frontier


def _feasible_spec() -> ScenarioSpec:
    return ScenarioSpec(
        factions=["alpha", "beta"],
        issues=[
            IssueSpec(name="allocation", outcomes=["A", "B"]),
            IssueSpec(name="payment", outcomes=["A", "B"]),
        ],
        pareto_count_target=3,
        pareto_distribution_spread=0.5,
        batna_clearing_count_target=1,
        batna_to_pareto_gap_pct=0.05,
        requires_logrolling=False,
        priority_collision="none",
        asymmetric_batna_fractions={"alpha": 0.5, "beta": 10 / 19},
        game_mode="mixed",
        seed=17,
    )


def _emittable_analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta"],
        "game_mode": "mixed",
        "issues": [
            {"name": "allocation", "outcomes": ["A", "B"], "description": "Allocation"},
            {"name": "payment", "outcomes": ["A", "B"], "description": "Payment"},
        ],
        "scoring": {
            "alpha": {
                "allocation": {"A": 10, "B": 1},
                "payment": {"A": 1, "B": 10},
            },
            "beta": {
                "allocation": {"A": 1, "B": 9},
                "payment": {"A": 10, "B": 1},
            },
        },
        "batna": {"alpha": 10, "beta": 10},
        "deception_tactics": {"alpha": "", "beta": ""},
        "logrolling": [],
    }


class TestSearchLoop:
    def test_is_deterministic_for_seed(self) -> None:
        spec = _feasible_spec()

        first = _search_loop(spec, max_restarts=250, max_local_moves=100, seed=23)
        second = _search_loop(spec, max_restarts=250, max_local_moves=100, seed=23)

        assert first == second

    def test_converges_on_known_feasible_spec(self) -> None:
        spec = _feasible_spec()

        analysis = _search_loop(spec, max_restarts=500, max_local_moves=150, seed=23)
        fitness = compute_fitness(analysis, spec)
        frontier = find_pareto_frontier(analysis, enumerate_deals(analysis))

        assert fitness.satisfies(0.10)
        assert len(frontier) == 3
        assert analysis["factions"] == ["alpha", "beta"]


class TestBuildAndSaveScenario:
    def test_emits_canonical_analysis_and_persona_files(
        self, tmp_path: Path, monkeypatch: object
    ) -> None:
        spec = _feasible_spec()
        monkeypatch.setattr(
            "tools.scenario_builder._search_loop",
            lambda *args, **kwargs: _emittable_analysis(),
        )

        analysis, analysis_path, persona_paths = build_and_save_scenario(
            spec,
            tmp_path,
            scenario_title="Reverse Builder v1",
            max_restarts=1,
            max_local_moves=1,
            seed=23,
        )

        assert analysis == _emittable_analysis()
        assert analysis_path.name == "scenario_analysis.json"
        assert analysis_path.is_file()
        loaded_analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
        assert loaded_analysis == _emittable_analysis()

        frontier = find_pareto_frontier(loaded_analysis, enumerate_deals(loaded_analysis))
        assert len(frontier) == 3

        assert set(persona_paths) == {"alpha", "beta"}
        alpha_path = persona_paths["alpha"]
        beta_path = persona_paths["beta"]
        assert alpha_path.is_file()
        assert beta_path.is_file()

        alpha_persona = FileBasedPersona(alpha_path)
        base_prompt = asyncio.run(alpha_persona.get_base_prompt())
        assert "You are Alpha in Reverse Builder v1" in base_prompt
        assert "## CURRENT ROUND CONTEXT" not in base_prompt

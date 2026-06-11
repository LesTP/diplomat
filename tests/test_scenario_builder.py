"""Tests for the reverse scenario builder search loop."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import logging
import random
from pathlib import Path

import pytest

from modules.persona import FileBasedPersona
from tools.scenario_builder import (
    _anneal_local,
    _analysis_from_scoring_table,
    _random_scoring_table,
    _seed_scoring_table,
    _run,
    _search_loop,
    build_and_save_scenario,
)
from tools.scenario_fitness import FitnessResult, compute_fitness
from tools.scenario_spec import IssueSpec, ScenarioSpec, dump_spec

from tests.self_play.verify_scenario_optimum import (
    enumerate_deals,
    find_pareto_frontier,
    find_priority_issues,
)


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


def _biased_spec() -> ScenarioSpec:
    return ScenarioSpec(
        factions=["alpha", "beta", "gamma"],
        issues=[
            IssueSpec(name="mission_objective", outcomes=["Science-Priority", "Exploration-Priority", "Commercial-Tech-Demo"]),
            IssueSpec(name="hardware_lead", outcomes=["Alpha-Lead", "Joint-Build", "Gamma-Lead"]),
            IssueSpec(name="funding_split", outcomes=["Equal-Thirds", "Commercial-Heavy", "Government-Heavy"]),
        ],
        score_range=(1, 10),
        pareto_count_target=(3, 5),
        pareto_distribution_spread=0.35,
        batna_clearing_count_target=10,
        batna_to_pareto_gap_pct=0.45,
        requires_logrolling=True,
        priority_collision="soft",
        asymmetric_batna_fractions={"alpha": 0.5, "beta": 0.5, "gamma": 0.5},
        game_mode="mixed",
        seed=42,
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
        "pressure": {
            "round_cost_decay": 0.0,
            "asymmetric_clocks": {},
            "penalty_floor_offset": 0.0,
        },
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

    def test_debug_search_emits_stable_restart_schema(
        self, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spec = _feasible_spec()
        scoring = {
            "alpha": {
                "allocation": {"A": 10, "B": 1},
                "payment": {"A": 1, "B": 10},
            },
            "beta": {
                "allocation": {"A": 1, "B": 9},
                "payment": {"A": 10, "B": 1},
            },
        }

        monkeypatch.setattr(
            "tools.scenario_builder._random_scoring_table",
            lambda *args, **kwargs: copy.deepcopy(scoring),
        )
        monkeypatch.setattr("tools.scenario_builder._candidate_is_acceptable", lambda *a, **k: False)
        caplog.set_level(logging.INFO, logger="tools.scenario_builder")

        def collect_schema() -> list[list[str]]:
            return [
                sorted(json.loads(record.getMessage()).keys())
                for record in caplog.records
                if record.name == "tools.scenario_builder"
            ]

        with pytest.raises(RuntimeError):
            _search_loop(spec, max_restarts=1, max_local_moves=1, seed=23, debug_search=True)
        first_schema = collect_schema()
        caplog.clear()

        with pytest.raises(RuntimeError):
            _search_loop(spec, max_restarts=1, max_local_moves=1, seed=23, debug_search=True)
        second_schema = collect_schema()

        assert first_schema == second_schema == [
            [
                "end_total_distance",
                "event",
                "exit_reason",
                "per_target_distance",
                "restart_index",
                "start_total_distance",
            ]
        ]

    def test_seeded_tables_bias_soft_collision_and_logrolling(self) -> None:
        spec = _biased_spec()
        scoring = _seed_scoring_table(spec, random.Random(42))
        analysis = _analysis_from_scoring_table(spec, scoring)
        priorities = find_priority_issues(analysis)
        priority_issues = [priorities[faction][0] for faction in spec.factions]
        max_scores = {
            faction: sum(max(scoring[faction][issue.name].values()) for issue in spec.issues)
            for faction in spec.factions
        }

        assert any(priority_issues.count(issue) >= 2 for issue in set(priority_issues))
        assert any(
            all(
                sum(scoring[faction][issue["name"]][deal[issue["name"]]] for issue in analysis["issues"])
                >= 0.8 * max_scores[faction]
                for faction in spec.factions
            )
            for deal in enumerate_deals(analysis)
        )

    def test_seeded_tables_start_with_lower_average_fitness_than_random(self) -> None:
        spec = _biased_spec()
        seeded_total = 0.0
        random_total = 0.0

        for seed in range(50):
            seeded_scoring = _seed_scoring_table(spec, random.Random(seed))
            random_scoring = _random_scoring_table(spec, random.Random(seed))
            seeded_total += compute_fitness(
                _analysis_from_scoring_table(spec, seeded_scoring), spec
            ).total_distance
            random_total += compute_fitness(
                _analysis_from_scoring_table(spec, random_scoring), spec
            ).total_distance

        assert seeded_total / 50 < random_total / 50


class TestAnnealLocal:
    def test_is_deterministic_for_seed(self) -> None:
        spec = _feasible_spec()
        rng_init = random.Random(7)
        scoring = _random_scoring_table(spec, rng_init)
        analysis = _analysis_from_scoring_table(spec, scoring)
        fitness = compute_fitness(analysis, spec)

        first, _, _, _ = _anneal_local(
            spec, copy.deepcopy(scoring), analysis, fitness,
            max_local_moves=30, rng=random.Random(42)
        )
        second, _, _, _ = _anneal_local(
            spec, copy.deepcopy(scoring), analysis, fitness,
            max_local_moves=30, rng=random.Random(42)
        )
        assert first == second

    def test_accepts_uphill_move_on_plateau_trap(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SA accepts uphill moves: escapes a trap where all neighbors are worse."""
        spec = _feasible_spec()
        initial_scoring = _random_scoring_table(spec, random.Random(5))
        analysis = _analysis_from_scoring_table(spec, initial_scoring)
        start_distance = 0.50
        start_fitness = FitnessResult(
            total_distance=start_distance,
            per_target_distance={"pareto_count": start_distance},
        )
        # Every candidate is slightly worse — greedy would be permanently stuck.
        always_worse = FitnessResult(
            total_distance=start_distance + 0.05,
            per_target_distance={"pareto_count": start_distance + 0.05},
        )
        monkeypatch.setattr("tools.scenario_builder.compute_fitness", lambda *a: always_worse)

        # With T=1.0 at start, exp(-0.05/1.0) ≈ 0.951 per-move acceptance prob.
        # P(all 30 rejected) ≈ 0.049^30 ≈ 10^-42 — effectively zero.
        final_scoring, _, _, _ = _anneal_local(
            spec, copy.deepcopy(initial_scoring), analysis, start_fitness,
            max_local_moves=30, rng=random.Random(123)
        )
        assert final_scoring != initial_scoring

    def test_converges_on_feasible_spec(self) -> None:
        """_anneal_local (via _search_loop) converges on the 2×2×2 fixture."""
        spec = _feasible_spec()
        analysis = _search_loop(spec, max_restarts=500, max_local_moves=150, seed=23)
        fitness = compute_fitness(analysis, spec)
        frontier = find_pareto_frontier(analysis, enumerate_deals(analysis))

        assert fitness.satisfies(0.10)
        assert len(frontier) == 3


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


def _write_spec_file(tmp_path: Path) -> Path:
    spec = ScenarioSpec(
        factions=["alpha", "beta"],
        issues=[
            IssueSpec(name="allocation", outcomes=["A", "B"]),
            IssueSpec(name="payment", outcomes=["A", "B"]),
        ],
        pareto_count_target=1,
        pareto_distribution_spread=0.0,
        batna_clearing_count_target=1,
        batna_to_pareto_gap_pct=0.0,
    )
    spec_path = tmp_path / "spec.json"
    dump_spec(spec, spec_path)
    return spec_path


class TestCLI:
    def test_run_emits_files_without_verify(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spec_path = _write_spec_file(tmp_path)
        analysis = _emittable_analysis()
        analysis_path = tmp_path / "scenario_analysis.json"
        persona_paths = {
            "alpha": tmp_path / "alpha.txt",
            "beta": tmp_path / "beta.txt",
        }
        monkeypatch.setattr(
            "tools.scenario_builder.build_and_save_scenario",
            lambda *a, **kw: (analysis, analysis_path, persona_paths),
        )

        args = argparse.Namespace(
            spec=str(spec_path),
            output_dir=str(tmp_path),
            title="Test Scenario",
            seed=42,
            max_iterations=5,
            verify=False,
        )
        _run(args)  # must not raise

    def test_run_exits_1_on_missing_spec(self, tmp_path: Path) -> None:
        args = argparse.Namespace(
            spec=str(tmp_path / "nonexistent.json"),
            output_dir=str(tmp_path),
            title="Test",
            seed=None,
            max_iterations=10,
            verify=False,
        )
        with pytest.raises(SystemExit) as exc_info:
            _run(args)
        assert exc_info.value.code == 1

    def test_run_with_verify_passes_valid_analysis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        spec_path = _write_spec_file(tmp_path)
        analysis = _emittable_analysis()
        analysis_path = tmp_path / "scenario_analysis.json"
        analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
        persona_paths = {
            "alpha": tmp_path / "alpha.txt",
            "beta": tmp_path / "beta.txt",
        }
        monkeypatch.setattr(
            "tools.scenario_builder.build_and_save_scenario",
            lambda *a, **kw: (analysis, analysis_path, persona_paths),
        )

        args = argparse.Namespace(
            spec=str(spec_path),
            output_dir=str(tmp_path),
            title="Test",
            seed=1,
            max_iterations=5,
            verify=True,
        )
        _run(args)  # must not raise — valid analysis produces rc=0 from verifier

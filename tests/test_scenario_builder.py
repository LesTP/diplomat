"""Tests for the reverse scenario builder search loop."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import pytest

from modules.persona import FileBasedPersona
from tools.scenario_builder import _run, _search_loop, build_and_save_scenario
from tools.scenario_fitness import compute_fitness
from tools.scenario_spec import IssueSpec, ScenarioSpec, dump_spec

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

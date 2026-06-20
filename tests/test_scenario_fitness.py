"""Tests for reverse scenario builder fitness scoring."""

from __future__ import annotations

import pytest

from scenario_authoring.scenario_fitness import FitnessResult, compute_fitness
from scenario_authoring.scenario_spec import IssueSpec, ScenarioSpec


def _water_rights_beta_squeezed_analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta", "gamma"],
        "game_mode": "mixed",
        "issues": [
            {
                "name": "water_release_volume",
                "outcomes": ["High", "Low"],
                "description": "River release volume",
            },
            {
                "name": "payment_structure",
                "outcomes": ["Heavy-Downstream", "Shared"],
                "description": "Compensation structure",
            },
        ],
        "scoring": {
            "alpha": {
                "water_release_volume": {"High": 10, "Low": 1},
                "payment_structure": {"Heavy-Downstream": 10, "Shared": 1},
            },
            "beta": {
                "water_release_volume": {"High": 10, "Low": 1},
                "payment_structure": {"Heavy-Downstream": 10, "Shared": 1},
            },
            "gamma": {
                "water_release_volume": {"High": 10, "Low": 1},
                "payment_structure": {"Heavy-Downstream": 10, "Shared": 1},
            },
        },
        "batna": {"alpha": 19, "beta": 19, "gamma": 19},
        "deception_tactics": {"alpha": "", "beta": "", "gamma": ""},
        "logrolling": [],
    }


def _water_rights_beta_squeezed_spec() -> ScenarioSpec:
    return ScenarioSpec(
        factions=["alpha", "beta", "gamma"],
        issues=[
            IssueSpec(name="water_release_volume", outcomes=["High", "Low"]),
            IssueSpec(name="payment_structure", outcomes=["Heavy-Downstream", "Shared"]),
        ],
        pareto_count_target=1,
        pareto_distribution_spread=0.0,
        batna_clearing_count_target=1,
        batna_to_pareto_gap_pct=0.05,
        requires_logrolling=True,
        priority_collision="hard",
        asymmetric_batna_fractions={"alpha": 0.95, "beta": 0.95, "gamma": 0.95},
        game_mode="mixed",
    )


def _multi_pareto_analysis() -> dict[str, object]:
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


def _low_diversity_analysis() -> dict[str, object]:
    return {
        "factions": ["alpha", "beta"],
        "game_mode": "mixed",
        "issues": [
            {"name": "allocation", "outcomes": ["A", "B"], "description": "Allocation"},
            {"name": "payment", "outcomes": ["A", "B"], "description": "Payment"},
        ],
        "scoring": {
            "alpha": {
                "allocation": {"A": 10, "B": 9},
                "payment": {"A": 10, "B": 9},
            },
            "beta": {
                "allocation": {"A": 1, "B": 2},
                "payment": {"A": 1, "B": 2},
            },
        },
        "batna": {"alpha": 10, "beta": 2},
        "deception_tactics": {"alpha": "", "beta": ""},
        "logrolling": [],
    }


def _multi_pareto_spec() -> ScenarioSpec:
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
    )


class TestComputeFitness:
    def test_scores_known_single_frontier_water_rights_fixture(self) -> None:
        result = compute_fitness(_water_rights_beta_squeezed_analysis(), _water_rights_beta_squeezed_spec())

        assert isinstance(result, FitnessResult)
        assert result.total_distance == 0.0
        assert result.per_target_distance == {
            "pareto_count": 0.0,
            "pareto_outcome_diversity": 0.0,
            "pareto_distribution_spread": 0.0,
            "batna_clearing_count": 0.0,
            "batna_to_pareto_gap_pct": 0.0,
            "requires_logrolling": 0.0,
            "priority_collision": 0.0,
            "game_mode": 0.0,
            "asymmetric_batna_fractions.alpha": 0.0,
            "asymmetric_batna_fractions.beta": 0.0,
            "asymmetric_batna_fractions.gamma": 0.0,
        }
        assert result.satisfies(0.0)

    def test_scores_known_multi_pareto_fixture(self) -> None:
        result = compute_fitness(_multi_pareto_analysis(), _multi_pareto_spec())

        assert result.total_distance == 0.0
        assert result.satisfies(0.0)
        assert result.per_target_distance["pareto_count"] == 0.0
        assert result.per_target_distance["priority_collision"] == 0.0

    def test_uses_target_weights_for_total_distance(self) -> None:
        analysis = _multi_pareto_analysis()
        spec = _multi_pareto_spec()
        spec.pareto_count_target = 4
        spec.target_weights = {"pareto_count": 2.0}

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["pareto_count"] == 0.25
        assert result.total_distance == pytest.approx(0.5)

    def test_uses_default_weight_for_categorical_targets(self) -> None:
        analysis = _multi_pareto_analysis()
        spec = _multi_pareto_spec()
        spec.game_mode = "competitive"

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["game_mode"] == 1.0
        assert result.total_distance == pytest.approx(0.3)

    def test_scores_pareto_outcome_diversity_for_low_diversity_frontier(self) -> None:
        analysis = _low_diversity_analysis()
        spec = _multi_pareto_spec()
        spec.pareto_outcome_diversity = 0.5

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["pareto_outcome_diversity"] == 0.0

    def test_scores_pareto_outcome_diversity_for_distinct_frontier_winners(self) -> None:
        analysis = _multi_pareto_analysis()
        spec = _multi_pareto_spec()
        spec.pareto_outcome_diversity = 1.0

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["pareto_outcome_diversity"] == 0.0

    def test_scores_pareto_outcome_diversity_for_mixed_target(self) -> None:
        analysis = _low_diversity_analysis()
        spec = _multi_pareto_spec()
        spec.pareto_outcome_diversity = 0.75

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["pareto_outcome_diversity"] == pytest.approx(0.25)

    def test_ignores_pareto_outcome_diversity_when_target_is_zero(self) -> None:
        analysis = _multi_pareto_analysis()
        spec = _multi_pareto_spec()

        result = compute_fitness(analysis, spec)

        assert result.per_target_distance["pareto_outcome_diversity"] == 0.0

    def test_satisfies_uses_total_budget(self) -> None:
        result = FitnessResult(total_distance=0.29, per_target_distance={"game_mode": 1.0})

        assert result.satisfies(0.30)
        assert not result.satisfies(0.28)

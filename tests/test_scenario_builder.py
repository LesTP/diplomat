"""Tests for the reverse scenario builder search loop."""

from __future__ import annotations

from tools.scenario_builder import _search_loop
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

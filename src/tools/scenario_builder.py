"""Reverse scenario builder for constraint-driven negotiation scenarios.

The builder searches scoring-table space for a candidate analysis that matches
the requested outcome-shape targets in ``ScenarioSpec``. It reuses the existing
scenario compiler BATNA calibration and the verifier's pure-function frontier
analysis.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any

from tests.self_play.verify_scenario_optimum import enumerate_deals, find_pareto_frontier

from tools.scenario_compiler import DEFAULT_BATNA_FRACTION, force_batna_targets
from tools.scenario_fitness import compute_fitness
from tools.scenario_spec import ScenarioSpec


@dataclass(frozen=True)
class _Cell:
    faction: str
    issue: str
    outcome: str


def _score_range(spec: ScenarioSpec) -> range:
    low, high = spec.score_range
    return range(low, high + 1)


def _random_scoring_table(spec: ScenarioSpec, rng: random.Random) -> dict[str, dict[str, dict[str, int]]]:
    values = list(_score_range(spec))
    scoring: dict[str, dict[str, dict[str, int]]] = {}
    for faction in spec.factions:
        faction_scoring: dict[str, dict[str, int]] = {}
        for issue in spec.issues:
            outcome_scores = {outcome: rng.choice(values) for outcome in issue.outcomes}
            faction_scoring[issue.name] = outcome_scores
        scoring[faction] = faction_scoring
    return scoring


def _analysis_from_scoring_table(
    spec: ScenarioSpec,
    scoring: dict[str, dict[str, dict[str, int]]],
) -> dict[str, Any]:
    analysis: dict[str, Any] = {
        "factions": list(spec.factions),
        "issues": [issue.to_dict() for issue in spec.issues],
        "scoring": scoring,
        "batna": {faction: 0 for faction in spec.factions},
        "deception_tactics": {faction: "" for faction in spec.factions},
        "logrolling": [],
        "game_mode": spec.game_mode,
    }
    return force_batna_targets(
        analysis,
        target_fraction=DEFAULT_BATNA_FRACTION,
        target_fractions=spec.asymmetric_batna_fractions,
    )


def _target_pareto_count_matches(spec: ScenarioSpec, frontier_count: int) -> bool:
    target = spec.pareto_count_target
    if isinstance(target, tuple):
        low, high = target
        return low <= frontier_count <= high
    return frontier_count == target


def _candidate_is_acceptable(spec: ScenarioSpec, analysis: dict[str, Any]) -> bool:
    fitness = compute_fitness(analysis, spec)
    if not fitness.satisfies(0.10):
        return False
    frontier = find_pareto_frontier(analysis, enumerate_deals(analysis))
    return _target_pareto_count_matches(spec, len(frontier))


def _all_cells(spec: ScenarioSpec) -> list[_Cell]:
    cells: list[_Cell] = []
    for faction in spec.factions:
        for issue in spec.issues:
            for outcome in issue.outcomes:
                cells.append(_Cell(faction=faction, issue=issue.name, outcome=outcome))
    return cells


def _best_single_cell_flip(
    spec: ScenarioSpec,
    scoring: dict[str, dict[str, dict[str, int]]],
    current_distance: float,
) -> tuple[dict[str, dict[str, dict[str, int]]] | None, dict[str, Any] | None, float]:
    best_scoring: dict[str, dict[str, dict[str, int]]] | None = None
    best_analysis: dict[str, Any] | None = None
    best_distance = current_distance
    values = list(_score_range(spec))

    for cell in _all_cells(spec):
        current_value = scoring[cell.faction][cell.issue][cell.outcome]
        for value in values:
            if value == current_value:
                continue
            candidate_scoring = copy.deepcopy(scoring)
            candidate_scoring[cell.faction][cell.issue][cell.outcome] = value
            candidate_analysis = _analysis_from_scoring_table(spec, candidate_scoring)
            candidate_distance = compute_fitness(candidate_analysis, spec).total_distance
            if candidate_distance < best_distance:
                best_scoring = candidate_scoring
                best_analysis = candidate_analysis
                best_distance = candidate_distance
    return best_scoring, best_analysis, best_distance


def _search_loop(
    spec: ScenarioSpec,
    max_restarts: int = 1000,
    max_local_moves: int = 200,
    seed: int | None = None,
) -> dict[str, Any]:
    """Search scoring-table space with random restarts and greedy local flips."""
    rng = random.Random(spec.seed if seed is None else seed)

    for _restart in range(max_restarts):
        scoring = _random_scoring_table(spec, rng)
        analysis = _analysis_from_scoring_table(spec, scoring)
        fitness = compute_fitness(analysis, spec)

        if _candidate_is_acceptable(spec, analysis):
            return analysis

        plateau_moves = 0
        for _ in range(max_local_moves):
            candidate_scoring, candidate_analysis, candidate_distance = _best_single_cell_flip(
                spec,
                scoring,
                fitness.total_distance,
            )
            if candidate_scoring is None or candidate_analysis is None:
                plateau_moves += 1
                if plateau_moves >= 10:
                    break
                continue

            scoring = candidate_scoring
            analysis = candidate_analysis
            fitness = compute_fitness(analysis, spec)
            plateau_moves = 0

            if _candidate_is_acceptable(spec, analysis):
                return analysis

    raise RuntimeError("scenario search failed to produce an acceptable candidate")

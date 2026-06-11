"""Fitness scoring for reverse scenario builder candidates."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import pstdev
from typing import Any

from tests.self_play.verify_scenario_optimum import (
    beats_batna,
    enumerate_deals,
    faction_score,
    find_pareto_frontier,
    find_priority_issues,
)

_CATEGORICAL_TARGETS = {"requires_logrolling", "priority_collision", "game_mode"}
_DEFAULT_CATEGORICAL_TARGET_WEIGHT = 0.3


@dataclass
class FitnessResult:
    """Aggregate fitness score plus per-target distances."""

    total_distance: float
    per_target_distance: dict[str, float]

    def satisfies(self, tolerance: float) -> bool:
        """Return True when the weighted total distance stays within tolerance."""
        if tolerance < 0.0:
            raise ValueError("tolerance must be non-negative")
        return self.total_distance <= tolerance


def _max_possible_scores(analysis: dict[str, Any]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for faction in analysis.get("factions", []):
        total = 0.0
        faction_scoring = analysis.get("scoring", {}).get(faction, {})
        for issue in analysis.get("issues", []):
            outcomes = faction_scoring.get(issue["name"], {})
            if outcomes:
                total += max(outcomes.values())
        scores[faction] = total
    return scores


def _normalized_distance(value: float, target: float) -> float:
    scale = max(abs(target), 1.0)
    return abs(value - target) / scale


def _count_distance(observed: int, target: int | tuple[int, int]) -> float:
    if isinstance(target, int):
        return abs(observed - target) / max(target, 1)
    low, high = target
    if low <= observed <= high:
        return 0.0
    boundary = low if observed < low else high
    return abs(observed - boundary) / max(boundary, 1)


def _priority_collision_level(analysis: dict[str, Any]) -> str:
    priorities = find_priority_issues(analysis)
    faction_priorities = [priorities[faction][0] for faction in analysis.get("factions", [])]
    if len(set(faction_priorities)) == len(faction_priorities):
        return "none"
    if len(set(faction_priorities)) == 1:
        return "hard"
    return "soft"


def _target_weight(spec: Any, target_name: str) -> float:
    if target_name in spec.target_weights:
        return spec.target_weights[target_name]
    if target_name in _CATEGORICAL_TARGETS:
        return _DEFAULT_CATEGORICAL_TARGET_WEIGHT
    return 1.0


def compute_fitness(analysis: dict[str, Any], spec: Any) -> FitnessResult:
    """Score a candidate analysis against a ScenarioSpec.

    Distances are normalized to stay roughly within [0, 1] when the candidate
    is near target. Counts use relative error, and scalar fractions use
    absolute fractional error.
    """
    deals = enumerate_deals(analysis)
    frontier = find_pareto_frontier(analysis, deals)
    factions = list(analysis.get("factions", []))
    max_scores = _max_possible_scores(analysis)

    per_target_distance: dict[str, float] = {}

    observed_pareto_count = len(frontier)
    per_target_distance["pareto_count"] = _count_distance(
        observed_pareto_count, spec.pareto_count_target
    )

    distinct_winners: set[str] = set()
    for _, scores in frontier:
        if not scores:
            continue
        distinct_winners.add(max(scores, key=scores.get))
    winner_denominator = min(len(frontier), len(factions))
    observed_outcome_diversity = (
        len(distinct_winners) / winner_denominator if winner_denominator > 0 else 0.0
    )
    target_outcome_diversity = getattr(spec, "pareto_outcome_diversity", 0.0)
    per_target_distance["pareto_outcome_diversity"] = (
        _normalized_distance(observed_outcome_diversity, target_outcome_diversity)
        if target_outcome_diversity > 0.0
        else 0.0
    )

    frontier_ranges: list[float] = []
    for faction in factions:
        scores = [scores[faction] for _, scores in frontier]
        if scores:
            frontier_ranges.append(max(scores) - min(scores))
        else:
            frontier_ranges.append(0.0)
    observed_spread = pstdev(frontier_ranges) if len(frontier_ranges) > 1 else 0.0
    per_target_distance["pareto_distribution_spread"] = _normalized_distance(
        observed_spread, spec.pareto_distribution_spread
    )

    batna_clearing_count = sum(
        1
        for deal in deals
        if beats_batna(analysis, {faction: faction_score(analysis, faction, deal) for faction in factions})
    )
    per_target_distance["batna_clearing_count"] = _count_distance(
        batna_clearing_count, spec.batna_clearing_count_target
    )

    pareto_clearing_gaps: list[float] = []
    for deal, scores in frontier:
        if not beats_batna(analysis, scores):
            continue
        faction_gaps = []
        for faction in factions:
            max_score = max_scores.get(faction, 0.0)
            if max_score <= 0:
                continue
            faction_gaps.append((scores[faction] - analysis["batna"][faction]) / max_score)
        if faction_gaps:
            pareto_clearing_gaps.append(min(faction_gaps))
    observed_gap_pct = max(pareto_clearing_gaps, default=0.0)
    per_target_distance["batna_to_pareto_gap_pct"] = _normalized_distance(
        observed_gap_pct, spec.batna_to_pareto_gap_pct
    )

    observed_logrolling = any(
        all(scores[faction] >= 0.75 * max_scores.get(faction, 0.0) for faction in factions)
        for _, scores in frontier
    )
    expected_logrolling = bool(spec.requires_logrolling)
    per_target_distance["requires_logrolling"] = 0.0 if observed_logrolling == expected_logrolling else 1.0

    observed_collision = _priority_collision_level(analysis)
    collision_order = {"none": 0, "soft": 1, "hard": 2}
    per_target_distance["priority_collision"] = abs(
        collision_order[observed_collision] - collision_order[spec.priority_collision]
    ) / 2.0

    observed_game_mode = analysis.get("game_mode", "mixed")
    per_target_distance["game_mode"] = 0.0 if observed_game_mode == spec.game_mode else 1.0

    for faction, target_fraction in spec.asymmetric_batna_fractions.items():
        max_score = max_scores.get(faction, 0.0)
        actual_fraction = 0.0 if max_score <= 0 else analysis["batna"][faction] / max_score
        per_target_distance[f"asymmetric_batna_fractions.{faction}"] = abs(
            actual_fraction - target_fraction
        )

    total_distance = sum(
        _target_weight(spec, target_name) * distance
        for target_name, distance in per_target_distance.items()
    )
    return FitnessResult(total_distance=total_distance, per_target_distance=per_target_distance)

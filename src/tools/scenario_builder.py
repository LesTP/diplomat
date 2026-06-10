"""Reverse scenario builder for constraint-driven negotiation scenarios.

The builder searches scoring-table space for a candidate analysis that matches
the requested outcome-shape targets in ``ScenarioSpec``. It reuses the existing
scenario compiler BATNA calibration and the verifier's pure-function frontier
analysis.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import random
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from tests.self_play.verify_scenario_optimum import enumerate_deals, find_pareto_frontier

from tools.scenario_compiler import (
    DEFAULT_BATNA_FRACTION,
    force_batna_targets,
    generate_persona,
    save_analysis,
    save_persona,
)
from tools.scenario_fitness import compute_fitness
from tools.scenario_spec import ScenarioSpec, load_spec


logger = logging.getLogger(__name__)


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


def _log_search_restart(
    *,
    restart_index: int,
    start_fitness: Any,
    end_fitness: Any,
    exit_reason: str,
    debug_search: bool,
) -> None:
    if not debug_search:
        return

    logger.info(
        json.dumps(
            {
                "event": "scenario_builder.search_restart",
                "restart_index": restart_index,
                "start_total_distance": start_fitness.total_distance,
                "end_total_distance": end_fitness.total_distance,
                "exit_reason": exit_reason,
                "per_target_distance": end_fitness.per_target_distance,
            },
            sort_keys=True,
        )
    )


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
    debug_search: bool = False,
) -> dict[str, Any]:
    """Search scoring-table space with random restarts and greedy local flips."""
    rng = random.Random(spec.seed if seed is None else seed)

    for restart_index in range(max_restarts):
        scoring = _random_scoring_table(spec, rng)
        analysis = _analysis_from_scoring_table(spec, scoring)
        start_fitness = compute_fitness(analysis, spec)
        fitness = start_fitness

        if _candidate_is_acceptable(spec, analysis):
            _log_search_restart(
                restart_index=restart_index,
                start_fitness=start_fitness,
                end_fitness=fitness,
                exit_reason="accepted",
                debug_search=debug_search,
            )
            return analysis

        exit_reason = "budget_exhausted"
        for _ in range(max_local_moves):
            candidate_scoring, candidate_analysis, _candidate_distance = _best_single_cell_flip(
                spec,
                scoring,
                fitness.total_distance,
            )
            if candidate_scoring is None or candidate_analysis is None:
                exit_reason = "plateau"
                break

            scoring = candidate_scoring
            analysis = candidate_analysis
            fitness = compute_fitness(analysis, spec)

            if _candidate_is_acceptable(spec, analysis):
                _log_search_restart(
                    restart_index=restart_index,
                    start_fitness=start_fitness,
                    end_fitness=fitness,
                    exit_reason="accepted",
                    debug_search=debug_search,
                )
                return analysis

        _log_search_restart(
            restart_index=restart_index,
            start_fitness=start_fitness,
            end_fitness=fitness,
            exit_reason=exit_reason,
            debug_search=debug_search,
        )

    raise RuntimeError("scenario search failed to produce an acceptable candidate")


def _save_search_outputs(
    analysis: dict[str, Any],
    output_dir: Path,
    scenario_title: str,
) -> tuple[Path, dict[str, Path]]:
    """Persist the canonical scenario analysis and per-faction persona files."""
    analysis_path = save_analysis(analysis, output_dir)
    persona_paths: dict[str, Path] = {}
    for faction_id in analysis["factions"]:
        persona_text = generate_persona(faction_id, analysis, scenario_title)
        persona_paths[faction_id] = save_persona(faction_id, persona_text, output_dir)
    return analysis_path, persona_paths


def build_and_save_scenario(
    spec: ScenarioSpec,
    output_dir: str | Path,
    scenario_title: str = "a reverse-engineered negotiation",
    *,
    max_restarts: int = 1000,
    max_local_moves: int = 200,
    seed: int | None = None,
    debug_search: bool = False,
) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    """Search for a matching scenario and save the emitted artifacts."""
    analysis = _search_loop(
        spec,
        max_restarts=max_restarts,
        max_local_moves=max_local_moves,
        seed=seed,
        debug_search=debug_search,
    )
    analysis_path, persona_paths = _save_search_outputs(
        analysis,
        Path(output_dir),
        scenario_title,
    )
    return analysis, analysis_path, persona_paths


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reverse scenario builder — constraint-driven scenario generator.",
    )
    parser.add_argument("--spec", required=True, help="Path to scenario spec JSON")
    parser.add_argument("--output-dir", required=True, help="Directory to write scenario artifacts")
    parser.add_argument(
        "--title",
        default="a reverse-engineered negotiation",
        help="Scenario title used in persona text",
    )
    parser.add_argument("--seed", type=int, default=None, help="Random seed override")
    parser.add_argument(
        "--debug-search",
        action="store_true",
        help="Emit structured restart logs while searching",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=1000,
        help="Maximum hill-climb restarts (default 1000)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "After emitting the scenario, run verify_scenario_optimum on the "
            "emitted JSON; exit non-zero if verification fails."
        ),
    )
    return parser.parse_args()


def _run(args: argparse.Namespace) -> None:
    spec_path = Path(args.spec)
    if not spec_path.is_file():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    debug_search = getattr(args, "debug_search", False)

    if debug_search:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    spec = load_spec(spec_path)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building scenario from spec: {spec_path.name}")
    print(f"  Factions: {', '.join(spec.factions)}")
    print(f"  Issues: {', '.join(i.name for i in spec.issues)}")
    print(f"  Pareto count target: {spec.pareto_count_target}")
    print(f"  Max restarts: {args.max_iterations}")

    try:
        analysis, analysis_path, persona_paths = build_and_save_scenario(
            spec,
            output_dir,
            scenario_title=args.title,
            max_restarts=args.max_iterations,
            seed=args.seed,
            debug_search=debug_search,
        )
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\nScenario emitted:")
    print(f"  Analysis: {analysis_path}")
    for faction_id, path in persona_paths.items():
        print(f"  Persona ({faction_id}): {path}")

    if args.verify:
        from tests.self_play.verify_scenario_optimum import main as _verify_main

        old_argv = sys.argv
        sys.argv = ["verify_scenario_optimum", "--analysis", str(analysis_path)]
        try:
            rc = _verify_main()
        finally:
            sys.argv = old_argv
        if rc != 0:
            print(f"\nVERIFY FAILED (exit code {rc})", file=sys.stderr)
            sys.exit(rc)
        print("\nVERIFY PASSED")


def main() -> None:
    args = _parse_args()
    _run(args)


if __name__ == "__main__":
    main()

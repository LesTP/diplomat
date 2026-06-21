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
import math
import random
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from scenario_authoring.verify_scenario_optimum import enumerate_deals, find_pareto_frontier

from scenario_authoring.scenario_compiler import (
    DEFAULT_BATNA_FRACTION,
    force_batna_targets,
    generate_persona,
    save_analysis,
    save_persona,
)
from scenario_authoring.scenario_fitness import FitnessResult, compute_fitness
from scenario_authoring.scenario_spec import ScenarioSpec, load_spec, resolve_pareto_count_target


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


def _seed_scoring_table(spec: ScenarioSpec, rng: random.Random) -> dict[str, dict[str, dict[str, int]]]:
    """Seed a random table with soft categorical and logrolling hints."""
    scoring = _random_scoring_table(spec, rng)
    values = list(_score_range(spec))
    low = values[0]
    high = values[-1]
    planted_floor = max(low, math.ceil(0.8 * high))
    issue_lookup = {issue.name: issue for issue in spec.issues}

    planted_deal = {issue.name: rng.choice(issue.outcomes) for issue in spec.issues}
    if spec.requires_logrolling:
        planted_cap = max(low, planted_floor - 1)
        for faction in spec.factions:
            for issue in spec.issues:
                outcomes = scoring[faction][issue.name]
                planted_outcome = planted_deal[issue.name]
                for outcome in issue.outcomes:
                    if outcome == planted_outcome:
                        outcomes[outcome] = max(outcomes[outcome], planted_floor)
                    else:
                        outcomes[outcome] = min(outcomes[outcome], planted_cap)

    if spec.priority_collision == "soft" and len(spec.factions) >= 2:
        consensus_issue = rng.choice(spec.issues)
        # F.1 (Phase 42): scale the shared-priority bias with faction count.
        # Previously fixed at min(2, F), which left F>=6 with only 1/3 of
        # factions in the collision pattern -- too weak a signal for the
        # search to reliably converge (Phase 3 finding: F=6 was fragile).
        # max(2, F // 2) keeps the F<=5 behavior (still 2 factions) and
        # scales up at F>=6 so at least half the factions share a priority.
        shared_count = max(2, len(spec.factions) // 2)
        shared_factions = set(rng.sample(spec.factions, k=shared_count))
        remaining_factions = [faction for faction in spec.factions if faction not in shared_factions]
        remaining_issues = [issue for issue in spec.issues if issue.name != consensus_issue.name]
        if not remaining_issues:
            remaining_issues = list(spec.issues)

        issue_assignment: dict[str, str] = {
            faction: consensus_issue.name
            for faction in spec.factions
            if faction in shared_factions
        }
        for index, faction in enumerate(remaining_factions):
            issue_assignment[faction] = remaining_issues[index % len(remaining_issues)].name

        priority_cap = max(low, high - 1)
        # Iterate factions in the spec's fixed list order (not set/dict
        # iteration order) so RNG is consumed deterministically. Set/dict
        # iteration of faction-name strings is PYTHONHASHSEED-dependent, which
        # previously made the builder non-reproducible across processes and
        # broke the scale probe as a regression gate.
        for faction in spec.factions:
            issue_name = issue_assignment[faction]
            issue = issue_lookup[issue_name]
            issue_scores = scoring[faction][issue_name]
            priority_outcome = rng.choice(issue.outcomes)
            for outcome in issue.outcomes:
                if outcome == priority_outcome:
                    issue_scores[outcome] = high
                else:
                    issue_scores[outcome] = min(issue_scores[outcome], priority_cap)

            for other_issue in spec.issues:
                if other_issue.name == issue_name:
                    continue
                other_scores = scoring[faction][other_issue.name]
                for outcome in other_issue.outcomes:
                    other_scores[outcome] = min(other_scores[outcome], priority_cap)

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
        "coalition_values": [],
        "game_mode": spec.game_mode,
        "priority_collision": spec.priority_collision,
        "pressure": spec.pressure.to_dict(),
    }
    return force_batna_targets(
        analysis,
        target_fraction=DEFAULT_BATNA_FRACTION,
        target_fractions=spec.asymmetric_batna_fractions,
    )


def _target_pareto_count_matches(
    spec: ScenarioSpec, frontier_count: int, deal_count: int
) -> bool:
    target = resolve_pareto_count_target(spec.pareto_count_target, deal_count)
    if isinstance(target, tuple):
        low, high = target
        return low <= frontier_count <= high
    return frontier_count == target


def _candidate_is_acceptable(spec: ScenarioSpec, analysis: dict[str, Any]) -> bool:
    fitness = compute_fitness(analysis, spec)
    if not fitness.satisfies(0.10):
        return False
    deals = enumerate_deals(analysis)
    frontier = find_pareto_frontier(analysis, deals)
    return _target_pareto_count_matches(spec, len(frontier), len(deals))


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


def _anneal_local(
    spec: ScenarioSpec,
    scoring: dict[str, dict[str, dict[str, int]]],
    analysis: dict[str, Any],
    fitness: FitnessResult,
    max_local_moves: int,
    rng: random.Random,
) -> tuple[dict[str, dict[str, dict[str, int]]], dict[str, Any], FitnessResult, str]:
    """Simulated annealing over single-cell flips.

    Temperature cools geometrically from T_start=1.0 to T_end=0.01 over
    max_local_moves steps. Better candidates are always accepted; worse
    candidates are accepted with probability exp(-Δdistance / T).

    C5b note (Phase 42): a broadened neighborhood (multi-cell flips +
    issue-scoped / outcome-rank swaps) was prototyped and probed, and it made
    high-D convergence *worse* once the builder was made deterministic — see
    PHASE_42_PLAN.md "Commit 5b". The single-cell neighborhood is kept.

    Returns (scoring, analysis, fitness, exit_reason) where exit_reason is
    "accepted" when the candidate satisfies the spec, or "budget_exhausted".
    """
    T_START = 1.0
    T_END = 0.01
    cells = _all_cells(spec)
    values = list(_score_range(spec))
    n_steps = max(max_local_moves - 1, 1)

    for step in range(max_local_moves):
        T = T_START * (T_END / T_START) ** (step / n_steps)

        cell = rng.choice(cells)
        current_value = scoring[cell.faction][cell.issue][cell.outcome]
        other_values = [v for v in values if v != current_value]
        if not other_values:
            continue
        new_value = rng.choice(other_values)

        # A.4 (Phase 42): mutate-revert instead of deepcopy per move.
        # The old code did `copy.deepcopy(scoring)` here; that's O(F*I*O)
        # per move and was the dominant constant-factor cost in inner-loop
        # wall-clock. force_batna_targets() (called by
        # _analysis_from_scoring_table) does its own internal deepcopy on
        # the analysis it builds, so we don't risk leaving the scoring
        # dict in a partial state visible to anything downstream.
        scoring[cell.faction][cell.issue][cell.outcome] = new_value
        candidate_analysis = _analysis_from_scoring_table(spec, scoring)
        candidate_fitness = compute_fitness(candidate_analysis, spec)

        delta = candidate_fitness.total_distance - fitness.total_distance
        if delta < 0 or rng.random() < math.exp(-delta / T):
            analysis = candidate_analysis
            fitness = candidate_fitness
            if _candidate_is_acceptable(spec, analysis):
                return scoring, analysis, fitness, "accepted"
        else:
            # Revert the single-cell mutation.
            scoring[cell.faction][cell.issue][cell.outcome] = current_value

    return scoring, analysis, fitness, "budget_exhausted"


def _search_loop(
    spec: ScenarioSpec,
    max_restarts: int = 1000,
    max_local_moves: int = 200,
    seed: int | None = None,
    debug_search: bool = False,
) -> dict[str, Any]:
    """Search scoring-table space with random restarts and simulated annealing."""
    rng = random.Random(spec.seed if seed is None else seed)

    for restart_index in range(max_restarts):
        scoring = _seed_scoring_table(spec, rng)
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

        scoring, analysis, fitness, exit_reason = _anneal_local(
            spec, scoring, analysis, fitness, max_local_moves, rng
        )

        if exit_reason == "accepted":
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
        from scenario_authoring.verify_scenario_optimum import main as _verify_main

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

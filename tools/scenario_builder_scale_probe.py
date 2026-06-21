"""Scenario builder scale probe.

Empirically characterize scenario_builder convergence + wall-clock across
(factions x issues x outcomes_per_issue) dimensions beyond the current
3x3x3 baseline. Probe data feeds Phase 42 (algorithm fixes if needed).

Output: JSONL with one record per (cell, seed). Optional markdown summary
table.

Usage:
    python tools/scenario_builder_scale_probe.py \
        --cells matrix \
        --seeds 3 \
        --output scenarios/scale_probe_results.jsonl \
        --summary scenarios/scale_probe_summary.md

    # Smoke (single cell, single seed):
    python tools/scenario_builder_scale_probe.py \
        --cells 3x3x3 \
        --seeds 1 \
        --output /tmp/probe_smoke.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import tempfile
import time
from pathlib import Path

# Allow `from scenario_authoring.* import ...` when invoked from project root,
# AND allow scenario_authoring's import of `tests.self_play.verify_scenario_optimum`
# (the Phase 1 coupling we flagged) to resolve.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT))

from scenario_authoring.scenario_builder import build_and_save_scenario  # noqa: E402
from scenario_authoring.scenario_fitness import compute_fitness  # noqa: E402
from scenario_authoring.scenario_spec import IssueSpec, ScenarioSpec  # noqa: E402


# Default matrix per PHASE_3_PLAN.md, with 5x cells deferred until after first
# run. Operator can override via --cells.
DEFAULT_MATRIX: list[tuple[int, int, int]] = [
    (3, 3, 3),  # baseline (D=27)
    # Single-axis sweeps: vary one dimension at a time.
    (4, 3, 3),  # +faction (D=27)
    (5, 3, 3),  # +faction (D=27)
    (6, 3, 3),  # +faction (D=27)
    (3, 4, 3),  # +issue (D=81)
    (3, 5, 3),  # +issue (D=243)
    (3, 6, 3),  # +issue (D=729)
    (3, 3, 4),  # +outcome (D=64)
    (3, 3, 5),  # +outcome (D=125)
    (3, 3, 6),  # +outcome (D=216)
    # Balanced scale target per PROJECT.md success criterion.
    (4, 4, 4),  # D=256
    # Deferred until after first run: (5, 4, 4), (4, 5, 5), (5, 5, 5).
]


def synthesize_spec(
    factions: int,
    issues: int,
    outcomes_per_issue: int,
    *,
    seed: int,
) -> ScenarioSpec:
    """Build a synthetic spec with anonymous labels + fixed fitness targets.

    Fitness targets are held constant across all cells so the probe measures
    "as deal space grows, does the algorithm still find the requested
    profile?" without confounding spec-difficulty changes.
    """
    faction_ids = [f"f{i}" for i in range(factions)]
    return ScenarioSpec(
        factions=faction_ids,
        issues=[
            IssueSpec(
                name=f"i{i}",
                outcomes=[f"o{j}" for j in range(outcomes_per_issue)],
            )
            for i in range(issues)
        ],
        score_range=(1, 10),
        pareto_count_target=(3, 5),
        pareto_distribution_spread=0.35,
        pareto_outcome_diversity=0.66,
        batna_clearing_count_target=5,
        batna_to_pareto_gap_pct=0.20,
        requires_logrolling=True,
        priority_collision="soft",
        asymmetric_batna_fractions={fid: 0.5 for fid in faction_ids},
        target_weights={"pareto_distribution_spread": 0.0},
        game_mode="mixed",
        seed=seed,
    )


def run_cell(
    factions: int,
    issues: int,
    outcomes_per_issue: int,
    *,
    seed: int,
    max_restarts: int,
    max_local_moves: int,
) -> dict:
    """Run the builder once on a synthetic spec; capture timing + outcome."""
    spec = synthesize_spec(factions, issues, outcomes_per_issue, seed=seed)
    deal_space = outcomes_per_issue ** issues
    base_record: dict = {
        "F": factions,
        "I": issues,
        "O": outcomes_per_issue,
        "D": deal_space,
        "seed": seed,
        "max_restarts": max_restarts,
        "max_local_moves": max_local_moves,
    }
    with tempfile.TemporaryDirectory() as td:
        t0 = time.monotonic()
        try:
            analysis, _, _ = build_and_save_scenario(
                spec,
                td,
                max_restarts=max_restarts,
                max_local_moves=max_local_moves,
                seed=seed,
            )
        except RuntimeError as exc:
            elapsed = time.monotonic() - t0
            return {
                **base_record,
                "exit_reason": "budget_exhausted",
                "wall_clock_s": round(elapsed, 3),
                "end_total_distance": None,
                "error": str(exc),
            }
        elapsed = time.monotonic() - t0
        fitness = compute_fitness(analysis, spec)
        return {
            **base_record,
            "exit_reason": "accepted",
            "wall_clock_s": round(elapsed, 3),
            "end_total_distance": round(fitness.total_distance, 4),
        }


def run_matrix(
    cells: list[tuple[int, int, int]],
    seeds: int,
    *,
    max_restarts: int,
    max_local_moves: int,
    output_path: Path,
) -> list[dict]:
    """Iterate cells x seeds, write JSONL, return all records."""
    results: list[dict] = []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fp:
        for cell in cells:
            f, i, o = cell
            for seed in range(seeds):
                print(f"[{f}x{i}x{o} seed={seed}] running...", flush=True)
                record = run_cell(
                    f, i, o,
                    seed=seed,
                    max_restarts=max_restarts,
                    max_local_moves=max_local_moves,
                )
                fp.write(json.dumps(record, sort_keys=True) + "\n")
                fp.flush()
                results.append(record)
                print(
                    f"  -> {record['exit_reason']} in {record['wall_clock_s']}s"
                    + (f" (distance={record['end_total_distance']})"
                       if record["end_total_distance"] is not None else ""),
                    flush=True,
                )
    return results


def summarize(results: list[dict]) -> str:
    """Render a markdown summary table grouped by cell."""
    by_cell: dict[tuple[int, int, int], list[dict]] = {}
    for r in results:
        by_cell.setdefault((r["F"], r["I"], r["O"]), []).append(r)

    lines = [
        "# Scenario Builder Scale Probe — Summary",
        "",
        "Auto-generated by `tools/scenario_builder_scale_probe.py`.",
        "",
        "| Cell | D | Seeds | Accept rate | Median wall-clock | Median end_distance (accepted) |",
        "|---|---|---|---|---|---|",
    ]
    for cell, rs in sorted(by_cell.items(), key=lambda kv: (kv[0][1] * kv[0][2], kv[0][0])):
        f, i, o = cell
        d = o ** i
        n = len(rs)
        accepted = [r for r in rs if r["exit_reason"] == "accepted"]
        accept_rate = f"{len(accepted)}/{n}"
        med_wall = statistics.median(r["wall_clock_s"] for r in rs)
        med_dist = (
            f"{statistics.median(r['end_total_distance'] for r in accepted):.3f}"
            if accepted else "—"
        )
        lines.append(
            f"| {f}x{i}x{o} | {d} | {n} | {accept_rate} | {med_wall:.2f}s | {med_dist} |"
        )
    lines.append("")
    lines.append("## Findings")
    lines.append("")
    lines.append("_Operator-written summary of what the data shows. Suggested headings:_")
    lines.append("")
    lines.append("- Where does the builder scale cleanly?")
    lines.append("- Where does it break (budget exhaustion, wall-clock blowup)?")
    lines.append("- Which axis (F, I, O) dominates cost in practice?")
    lines.append("- Hypotheses to investigate in Phase 42 (algorithm fixes).")
    return "\n".join(lines) + "\n"


def parse_cells(arg: str) -> list[tuple[int, int, int]]:
    """Parse --cells: 'matrix' or comma-separated 'FxIxO' triples."""
    if arg.strip().lower() == "matrix":
        return list(DEFAULT_MATRIX)
    cells: list[tuple[int, int, int]] = []
    for raw in arg.split(","):
        parts = raw.strip().lower().split("x")
        if len(parts) != 3:
            raise ValueError(
                f"--cells entry {raw!r} not in 'FxIxO' form (e.g. '3x3x3')"
            )
        try:
            f, i, o = (int(p) for p in parts)
        except ValueError as exc:
            raise ValueError(
                f"--cells entry {raw!r} has non-integer dimension"
            ) from exc
        if f < 1 or i < 1 or o < 1:
            raise ValueError(f"--cells entry {raw!r} has non-positive dimension")
        cells.append((f, i, o))
    return cells


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cells",
        default="matrix",
        help="'matrix' for the default sweep, or comma-separated FxIxO triples",
    )
    parser.add_argument("--seeds", type=int, default=3, help="seeds per cell")
    parser.add_argument(
        "--max-restarts", type=int, default=50,
        help="builder restart budget per cell (default 50; CLI default is 1000)",
    )
    parser.add_argument(
        "--max-local-moves", type=int, default=200,
        help="builder SA inner-loop step cap per restart (default 200)",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="JSONL output path (one record per cell x seed)",
    )
    parser.add_argument(
        "--summary", type=Path, default=None,
        help="Optional markdown summary output path",
    )
    args = parser.parse_args(argv)

    # Quiet the builder's per-restart INFO logging so the probe progress stays
    # readable. Operators wanting the structured logs can use --debug-search
    # on a direct scenario_builder invocation.
    logging.getLogger("scenario_authoring.scenario_builder").setLevel(logging.WARNING)

    cells = parse_cells(args.cells)
    print(
        f"Probing {len(cells)} cells x {args.seeds} seeds = {len(cells) * args.seeds} runs",
        flush=True,
    )
    print(
        f"Budget per run: max_restarts={args.max_restarts}, max_local_moves={args.max_local_moves}",
        flush=True,
    )
    print(f"Output JSONL: {args.output}", flush=True)
    if args.summary:
        print(f"Summary markdown: {args.summary}", flush=True)
    print(flush=True)

    t_total = time.monotonic()
    results = run_matrix(
        cells, args.seeds,
        max_restarts=args.max_restarts,
        max_local_moves=args.max_local_moves,
        output_path=args.output,
    )
    total_elapsed = time.monotonic() - t_total

    print(flush=True)
    accepted = sum(1 for r in results if r["exit_reason"] == "accepted")
    print(
        f"Done. {accepted}/{len(results)} cells accepted in {total_elapsed:.1f}s "
        f"total wall-clock.",
        flush=True,
    )

    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(summarize(results), encoding="utf-8")
        print(f"Wrote summary to {args.summary}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())

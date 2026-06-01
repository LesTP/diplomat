"""Backfill Phase 27 no-deal-aware scoring metrics on a self-play run.

Usage:
    python tools/backfill_scoring_metrics.py \\
        --results tests/self_play/results/run9_symmetric_live.json \\
        --analysis tests/self_play/scenarios/water_rights_symmetric_050/scenario_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.self_play.game_environment import _pareto_efficiency_metrics


_METRIC_KEYS = (
    "achieved_score_sum",
    "max_pareto_sum",
    "pareto_efficiency",
    "sum_batnas",
    "faction_deltas",
    "delta_above_batna_sum",
    "min_faction_delta",
    "surplus_distribution_stdev",
    "negotiated_surplus_share",
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="Path to run JSON")
    parser.add_argument("--analysis", required=True, help="Path to scenario_analysis.json")
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Patch Phase 27 scoring metrics into results.scores",
    )
    args = parser.parse_args()

    results_path = Path(args.results)
    analysis_path = Path(args.analysis)
    results = json.loads(results_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    score_data = results.get("scores") or {}
    if not score_data.get("faction_scores"):
        print(
            f"ERROR: {results_path} has no scores.faction_scores; cannot backfill",
            file=sys.stderr,
        )
        sys.exit(2)

    metrics = _pareto_efficiency_metrics(analysis, score_data)

    print(f"\n{'='*60}")
    print(f"  PHASE 27 SCORING BACKFILL - {results_path.name}")
    print(
        "  scenario: "
        f"{analysis_path.parent.name}  game_mode: {analysis.get('game_mode')}"
    )
    print(f"{'='*60}\n")

    print("  Metrics:")
    for key in _METRIC_KEYS:
        value = metrics.get(key)
        if isinstance(value, dict):
            print(f"    {key}:")
            for subkey, subvalue in sorted(value.items()):
                print(f"      {subkey}: {_format_number(subvalue)}")
        else:
            print(f"    {key}: {_format_number(value)}")

    if args.write_back:
        score_data.update(metrics)
        results["scores"] = score_data
        results_path.write_text(
            json.dumps(results, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        print(f"\n  Wrote Phase 27 scoring fields back into {results_path}")


def _format_number(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{float(value):.3f}"
    return str(value)


if __name__ == "__main__":
    main()

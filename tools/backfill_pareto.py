"""Backfill pareto_efficiency on a historical self-play run.

Older run JSONs (pre-Phase 23) don't carry scenario_analysis or pareto fields.
Given a run JSON with scores.faction_scores and a matching scenario_analysis.json,
this script computes achieved_score_sum / max_pareto_sum / pareto_efficiency
using the same _pareto_efficiency_metrics() function that score_game() uses today.

Usage:
    python tools/backfill_pareto.py \\
        --results tests/self_play/results/run8_water_rights_3provider_v3.json \\
        --analysis scenarios/water_rights_compiled/scenario_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tests.self_play.verify_scenario_optimum import (
    enumerate_deals,
    find_pareto_frontier,
)


# Inlined from tests/self_play/game_environment.py to avoid the orchestrator+toolkit
# import chain. Kept byte-for-byte equivalent so the metric matches a live run.
def _pareto_efficiency_metrics(scenario_analysis, score_data):
    deals = enumerate_deals(scenario_analysis)
    frontier = find_pareto_frontier(scenario_analysis, deals)
    max_pareto_sum = max(
        (sum(scores.values()) for _, scores in frontier), default=0.0
    )
    faction_scores = score_data.get("faction_scores", {})
    achieved_sum = 0.0
    for faction in scenario_analysis.get("factions", faction_scores.keys()):
        faction_data = faction_scores.get(faction, {})
        achieved_sum += float(faction_data.get("points", 0.0))
    efficiency = achieved_sum / max_pareto_sum if max_pareto_sum > 0 else 0.0
    return {
        "achieved_score_sum": achieved_sum,
        "max_pareto_sum": max_pareto_sum,
        "pareto_efficiency": efficiency,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True, help="Path to run JSON")
    parser.add_argument("--analysis", required=True, help="Path to scenario_analysis.json")
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Patch scores.{achieved_score_sum,max_pareto_sum,pareto_efficiency} into the run JSON",
    )
    args = parser.parse_args()

    results = json.loads(Path(args.results).read_text(encoding="utf-8"))
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))

    score_data = results.get("scores") or {}
    if not score_data.get("faction_scores"):
        print(f"ERROR: {args.results} has no scores.faction_scores; cannot backfill",
              file=sys.stderr)
        sys.exit(2)

    metrics = _pareto_efficiency_metrics(analysis, score_data)
    faction_scores = score_data["faction_scores"]

    print(f"\n{'='*60}")
    print(f"  PARETO BACKFILL — {Path(args.results).name}")
    print(f"  scenario: {Path(args.analysis).parent.name}  game_mode: {analysis.get('game_mode')}")
    print(f"{'='*60}\n")

    print("  Faction scores (achieved):")
    for f in analysis.get("factions", faction_scores.keys()):
        pts = faction_scores.get(f, {}).get("points", "?")
        print(f"    {f}: {pts}")

    print(f"\n  achieved_score_sum: {metrics['achieved_score_sum']:.1f}")
    print(f"  max_pareto_sum:     {metrics['max_pareto_sum']:.1f}")
    print(f"  pareto_efficiency:  {metrics['pareto_efficiency']:.3f}")

    deals = enumerate_deals(analysis)
    frontier = find_pareto_frontier(analysis, deals)
    print(f"\n  Total deals: {len(deals)}    Pareto frontier size: {len(frontier)}")

    best = max(frontier, key=lambda x: sum(x[1].values()), default=None)
    if best is not None:
        deal, scores = best
        print(f"\n  Best Pareto deal (sum={sum(scores.values()):.1f}):")
        for issue, outcome in deal.items():
            print(f"    {issue} = {outcome}")
        print(f"  Faction scores at best deal:")
        for f, s in scores.items():
            print(f"    {f}: {s}")

    if args.write_back:
        score_data.update(metrics)
        results["scores"] = score_data
        Path(args.results).write_text(
            json.dumps(results, indent=2, sort_keys=False), encoding="utf-8"
        )
        print(f"\n  Wrote pareto fields back into {args.results}")


if __name__ == "__main__":
    main()

"""Re-score a self-play run using deterministic faction_score() math.

Replaces the original LLM-reported faction_scores with values computed
from scenario_analysis.scoring + agreed_outcomes via the same
faction_score() function the new live scoring path now uses. Then
recomputes all Phase 27 + Phase 29 derived metrics.

Use to backfill runs scored before 095b259+ (when the scorer LLM
was doing both extraction AND arithmetic, occasionally over-counting
faction points — see run14_bare_gpt54mini_beta_squeezed_2 where the
LLM gave gamma 22 vs canonical 20).

Usage:
    python3 tools/rescore_run.py \\
        --results tests/self_play/results/run14_bare_gpt54mini_beta_squeezed_2.json \\
        --analysis scenarios/water_rights_beta_squeezed/scenario_analysis.json

    # Or batch:
    for f in tests/self_play/results/run14_*.json; do
        python3 tools/rescore_run.py --results "$f" \\
            --analysis scenarios/water_rights_beta_squeezed/scenario_analysis.json
    done
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.self_play.game_environment import (
    _compute_baselines,
    _pareto_efficiency_metrics,
)
from tests.self_play.verify_scenario_optimum import faction_score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", required=True)
    parser.add_argument("--analysis", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print rescored values without writing back.",
    )
    args = parser.parse_args()

    results_path = Path(args.results)
    analysis_path = Path(args.analysis)
    results = json.loads(results_path.read_text(encoding="utf-8"))
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))

    score_data = dict(results.get("scores") or {})
    if score_data.get("error"):
        print(
            f"WARN: existing scores has error {score_data['error']!r}; "
            "use tools/recover_scores.py first for arithmetic-in-JSON failures, "
            "or skip this run (no agreed_outcomes available).",
            file=sys.stderr,
        )

    deal_reached = score_data.get("deal_reached")
    agreed_outcomes = score_data.get("agreed_outcomes") or {}
    batnas = analysis.get("batna", {})

    if deal_reached and agreed_outcomes:
        new_faction_scores = {
            f: {
                "points": float(faction_score(analysis, f, agreed_outcomes)),
                "batna": float(batnas.get(f, 0.0)),
            }
            for f in analysis.get("factions", [])
        }
    else:
        new_faction_scores = {
            f: {"points": float(batnas.get(f, 0.0)), "batna": float(batnas.get(f, 0.0))}
            for f in analysis.get("factions", [])
        }

    # Diff old vs new faction_scores for the audit trail.
    old_faction_scores = score_data.get("faction_scores") or {}
    diffs = []
    for f in analysis.get("factions", []):
        old = old_faction_scores.get(f, {}).get("points")
        new = new_faction_scores[f]["points"]
        if old is not None and abs(float(old) - new) > 0.01:
            diffs.append((f, float(old), new, new - float(old)))

    score_data["faction_scores"] = new_faction_scores
    score_data.update(_pareto_efficiency_metrics(analysis, score_data))
    score_data.update(_compute_baselines(analysis, score_data))

    print(f"Rescored {results_path.name}:")
    print(f"  deal_reached: {deal_reached}")
    print(f"  faction_scores: {new_faction_scores}")
    print(f"  pareto_efficiency: {score_data.get('pareto_efficiency')}")
    print(f"  negotiated_surplus_share: {score_data.get('negotiated_surplus_share')}")
    print(f"  delta_above_batna_sum: {score_data.get('delta_above_batna_sum')}")
    print(f"  faction_deltas: {score_data.get('faction_deltas')}")
    if diffs:
        print(f"  CHANGED from previous LLM-scored values:")
        for f, old, new, delta in diffs:
            sign = "+" if delta > 0 else ""
            print(f"    {f}: {old} -> {new} ({sign}{delta})")
    else:
        print(f"  (no change from LLM-scored values)")

    if args.dry_run:
        print("[dry-run] Not writing back.")
        return

    results["scores"] = score_data
    results.setdefault("metadata", {}).setdefault("recovery", []).append(
        {
            "tool": "tools/rescore_run.py",
            "reason": "deterministic re-scoring via faction_score() — LLM scorer was unreliable on arithmetic",
            "diffs": [{"faction": f, "old": old, "new": new} for f, old, new, _ in diffs],
        }
    )
    results_path.write_text(
        json.dumps(results, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    print(f"Wrote rescored {results_path.name}.")


if __name__ == "__main__":
    main()

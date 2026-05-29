"""Verify a compiled scenario's point tables produce a non-trivial optimum.

Reads a scenario_analysis.json produced by tools.scenario_compiler and reports:
- Per-faction max possible deal value, BATNA, and "good deal" threshold
- All possible deals (cartesian product of outcomes across issues)
- Pareto frontier
- Number of deals that beat all BATNAs
- Whether each faction has a clearly differentiated priority issue
- Logrolling structure (does the "everyone gets priority" deal exist and clear all BATNAs?)

Usage:
    python -m tests.self_play.verify_scenario_optimum \\
        --analysis tests/self_play/scenarios/scenario_analysis.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any


def faction_score(
    analysis: dict[str, Any], faction: str, deal: dict[str, str]
) -> float:
    """Score a deal (mapping issue->outcome) for a faction."""
    scoring = analysis["scoring"][faction]
    total = 0.0
    for issue, outcome in deal.items():
        total += scoring.get(issue, {}).get(outcome, 0)
    return total


def enumerate_deals(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Return all possible deals as a list of {issue: outcome} dicts."""
    issues = analysis["issues"]
    issue_names = [i["name"] for i in issues]
    outcome_lists = [i["outcomes"] for i in issues]
    deals = []
    for combo in itertools.product(*outcome_lists):
        deals.append(dict(zip(issue_names, combo)))
    return deals


def is_pareto_dominated(
    deal_scores: dict[str, float],
    other_scores: dict[str, float],
) -> bool:
    """Return True if other_scores Pareto-dominates deal_scores (>= on all, > on one)."""
    all_geq = all(other_scores[f] >= deal_scores[f] for f in deal_scores)
    any_gt = any(other_scores[f] > deal_scores[f] for f in deal_scores)
    return all_geq and any_gt


def find_pareto_frontier(
    analysis: dict[str, Any],
    deals: list[dict[str, str]],
) -> list[tuple[dict[str, str], dict[str, float]]]:
    """Return list of (deal, scores) on the Pareto frontier."""
    factions = analysis["factions"]
    scored = [
        (deal, {f: faction_score(analysis, f, deal) for f in factions})
        for deal in deals
    ]
    frontier = []
    for deal, scores in scored:
        dominated = False
        for _, other_scores in scored:
            if other_scores == scores:
                continue
            if is_pareto_dominated(scores, other_scores):
                dominated = True
                break
        if not dominated:
            frontier.append((deal, scores))
    return frontier


def beats_batna(analysis: dict[str, Any], scores: dict[str, float]) -> bool:
    """Does this deal beat every faction's BATNA?"""
    return all(scores[f] > analysis["batna"][f] for f in scores)


def find_priority_issues(analysis: dict[str, Any]) -> dict[str, tuple[str, str, float]]:
    """For each faction, find (issue, outcome, points) of their single highest-scoring outcome."""
    result = {}
    for faction in analysis["factions"]:
        scoring = analysis["scoring"][faction]
        best_issue = ""
        best_outcome = ""
        best_pts = -1.0
        for issue, outcomes in scoring.items():
            for outcome, pts in outcomes.items():
                if pts > best_pts:
                    best_pts = pts
                    best_issue = issue
                    best_outcome = outcome
        result[faction] = (best_issue, best_outcome, best_pts)
    return result


def format_deal(deal: dict[str, str]) -> str:
    return " | ".join(f"{k}={v}" for k, v in deal.items())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, help="Path to scenario_analysis.json")
    parser.add_argument(
        "--top-n", type=int, default=10,
        help="How many top deals (by sum-of-scores) to show",
    )
    args = parser.parse_args()

    analysis_path = Path(args.analysis)
    if not analysis_path.is_file():
        print(f"ERROR: {analysis_path} not found", file=sys.stderr)
        return 1

    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    factions = analysis["factions"]
    issues = analysis["issues"]

    print("=" * 70)
    print(f"SCENARIO VERIFICATION: {analysis_path}")
    print("=" * 70)
    print(f"\nFactions: {', '.join(factions)}")
    print(f"Issues:   {', '.join(i['name'] for i in issues)}")
    print(f"Game mode: {analysis.get('game_mode', '?')}")

    # Per-faction summary
    print("\n--- Per-Faction Profile ---")
    priorities = find_priority_issues(analysis)
    max_deals = {}
    for f in factions:
        scoring = analysis["scoring"][f]
        max_deal = sum(max(scoring.get(i["name"], {}).values(), default=0) for i in issues)
        batna = analysis["batna"][f]
        good_deal_threshold = max_deal * 0.75
        max_deals[f] = max_deal
        pri_issue, pri_outcome, pri_pts = priorities[f]
        print(
            f"  {f:6s}  max={max_deal:5.1f}  BATNA={batna:5.1f}  "
            f"good_deal_>={good_deal_threshold:5.1f}  "
            f"priority: {pri_issue}={pri_outcome} ({pri_pts:.0f}pts)"
        )

    # Check that priorities are differentiated
    pri_issues = [priorities[f][0] for f in factions]
    if len(set(pri_issues)) == len(factions):
        print("  -> priorities are DIFFERENTIATED (each faction has a unique top issue)")
    else:
        print(f"  -> WARNING: priorities overlap: {pri_issues}")

    # Enumerate deals
    deals = enumerate_deals(analysis)
    print(f"\n--- Deal Space ---")
    print(f"  Total deals: {len(deals)}")

    # Beat-all-BATNAs
    deals_with_scores = [
        (d, {f: faction_score(analysis, f, d) for f in factions})
        for d in deals
    ]
    deals_beating_batna = [(d, s) for d, s in deals_with_scores if beats_batna(analysis, s)]
    print(f"  Deals that beat ALL BATNAs: {len(deals_beating_batna)} / {len(deals)}")

    if not deals_beating_batna:
        print("\n  *** PROBLEM: no deal beats all BATNAs. Scenario is broken. ***")
        return 2

    # Pareto frontier
    frontier = find_pareto_frontier(analysis, deals)
    pareto_beating = [(d, s) for d, s in frontier if beats_batna(analysis, s)]
    print(f"  Pareto frontier size: {len(frontier)}")
    print(f"  Pareto-optimal AND beat-all-BATNAs: {len(pareto_beating)}")

    # The "everyone gets their priority" deal
    priority_deal = {}
    for f in factions:
        pri_issue, pri_outcome, _ = priorities[f]
        if pri_issue in priority_deal and priority_deal[pri_issue] != pri_outcome:
            # priorities conflict on same issue
            priority_deal = None
            break
        priority_deal[pri_issue] = pri_outcome

    print("\n--- 'Everyone-gets-priority' Deal ---")
    if priority_deal is None:
        print("  N/A — faction priorities conflict on the same issue")
    else:
        # Fill in remaining issues with whatever (use first outcome as filler)
        for issue in issues:
            if issue["name"] not in priority_deal:
                # Pick the outcome that maximizes sum across factions
                best_outcome = None
                best_sum = -1
                for outcome in issue["outcomes"]:
                    s = sum(
                        analysis["scoring"][f].get(issue["name"], {}).get(outcome, 0)
                        for f in factions
                    )
                    if s > best_sum:
                        best_sum = s
                        best_outcome = outcome
                priority_deal[issue["name"]] = best_outcome
        scores = {f: faction_score(analysis, f, priority_deal) for f in factions}
        print(f"  Deal: {format_deal(priority_deal)}")
        for f in factions:
            mark = "[OK]" if scores[f] > analysis["batna"][f] else "[NO]"
            pct = scores[f] / max_deals[f] * 100 if max_deals[f] > 0 else 0
            print(f"    {f}: {scores[f]:.1f}  (BATNA {analysis['batna'][f]:.1f}, {pct:.0f}% of max)  {mark}")
        if beats_batna(analysis, scores):
            print("  -> beats ALL BATNAs [OK]")
        else:
            print("  -> does NOT beat all BATNAs [NO]")
        if (priority_deal, scores) in frontier:
            print("  -> IS on Pareto frontier [OK]")
        else:
            on_frontier = any(d == priority_deal for d, _ in frontier)
            print(f"  -> on Pareto frontier: {on_frontier}")

    # Top deals by sum of scores (best for collective welfare)
    deals_with_scores.sort(key=lambda x: sum(x[1].values()), reverse=True)
    print(f"\n--- Top {args.top_n} Deals by Aggregate Score ---")
    for deal, scores in deals_with_scores[: args.top_n]:
        score_str = "  ".join(f"{f}={scores[f]:.1f}" for f in factions)
        batna_mark = "+" if beats_batna(analysis, scores) else "-"
        pareto_mark = "P" if any(d == deal for d, _ in frontier) else " "
        print(f"  [{pareto_mark}{batna_mark}]  sum={sum(scores.values()):.1f}  {score_str}")
        print(f"         {format_deal(deal)}")

    # Logrolling check: does any deal exist where each faction scores >= 75% of their max?
    print(f"\n--- Logrolling Quality ---")
    excellent_deals = [
        (d, s) for d, s in deals_with_scores
        if all(s[f] >= 0.75 * max_deals[f] for f in factions)
        and beats_batna(analysis, s)
    ]
    print(f"  Deals where every faction scores >= 75% of max AND beats BATNA: {len(excellent_deals)}")
    if excellent_deals:
        d, s = excellent_deals[0]
        print(f"  Best example: {format_deal(d)}")
        score_str = "  ".join(f"{f}={s[f]:.1f}/{max_deals[f]:.1f}" for f in factions)
        print(f"             {score_str}")

    good_deals = [
        (d, s) for d, s in deals_with_scores
        if all(s[f] >= 0.60 * max_deals[f] for f in factions)
        and beats_batna(analysis, s)
    ]
    print(f"  Deals where every faction scores >= 60% of max AND beats BATNA: {len(good_deals)}")

    # Verdict
    print("\n--- VERDICT ---")
    verdict_ok = True
    reasons = []
    if len(deals_beating_batna) == 0:
        reasons.append("no deal beats all BATNAs")
        verdict_ok = False
    elif len(deals_beating_batna) == len(deals):
        reasons.append("EVERY deal beats all BATNAs (BATNAs too low)")
    if len(set(pri_issues)) < len(factions):
        reasons.append("priorities not differentiated")
        verdict_ok = False
    if len(excellent_deals) == 0:
        reasons.append("no 75%-of-max logrolling deal exists")
    if len(excellent_deals) > len(deals) * 0.5:
        reasons.append("too many 75%+ deals — scenario is too easy")
    if verdict_ok and len(excellent_deals) > 0 and len(excellent_deals) < len(deals) * 0.3:
        print("  PASS: non-trivial optimum exists")
        print(f"  - {len(excellent_deals)} excellent deal(s) out of {len(deals)} possible")
        print(f"  - {len(deals_beating_batna)} deals beat all BATNAs ({100*len(deals_beating_batna)//len(deals)}%)")
        print(f"  - {len(frontier)} Pareto-optimal deals")
    else:
        print(f"  REVIEW NEEDED: {'; '.join(reasons) if reasons else 'edge case, inspect manually'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

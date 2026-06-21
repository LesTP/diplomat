"""Enumerate all possible deal outcomes for a scenario and rank them by
total score (sum of faction points), to characterize the negotiation
space the agents are searching."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scenario_authoring.verify_scenario_optimum import (
    enumerate_deals,
    faction_score,
    find_pareto_frontier,
)

if len(sys.argv) < 2:
    print("Usage: python3 tools/enumerate_outcomes.py <scenario_analysis.json>")
    sys.exit(1)

analysis = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
factions = analysis["factions"]
batnas = analysis.get("batna", {})
sum_batnas = sum(batnas.values())

print(f"Scenario: {sys.argv[1]}")
print(f"Factions: {factions}  (BATNAs: {batnas}, sum {sum_batnas})")
print()

issues = analysis["issues"]
print("Issues:")
for issue in issues:
    print(f"  {issue['name']}: {len(issue['outcomes'])} outcomes -> {issue['outcomes']}")
n_deals_possible = 1
for issue in issues:
    n_deals_possible *= len(issue["outcomes"])
print(f"\nTotal possible deals (cartesian product): {n_deals_possible}")
print()

# Score every deal
deals = enumerate_deals(analysis)
scored = []
for deal in deals:
    per_faction = {f: faction_score(analysis, f, deal) for f in factions}
    total = sum(per_faction.values())
    # All factions must clear BATNA for the deal to be voluntarily acceptable
    above_batna_all = all(per_faction[f] >= batnas.get(f, 0) for f in factions)
    scored.append((total, per_faction, deal, above_batna_all))

scored.sort(key=lambda x: -x[0])

# Distribution of total sums
sum_distribution = Counter(int(t) for t, _, _, _ in scored)
print(f"Distribution of achievable score sums ({len(scored)} deals total):")
for s in sorted(sum_distribution.keys(), reverse=True):
    bar = "#" * sum_distribution[s]
    print(f"  sum={s:>4} : {sum_distribution[s]:>3} deal(s)  {bar}")
print()

# How many clear BATNAs?
voluntary = [s for s in scored if s[3]]
print(f"Deals where ALL factions clear BATNA (voluntarily acceptable): {len(voluntary)} of {len(scored)}")
print()

# Pareto frontier
frontier = find_pareto_frontier(analysis, deals)
print(f"Pareto-frontier deals: {len(frontier)}")
print()

# Top 10 by sum
print("=== Top 10 deals by total score ===")
print(f"{'sum':>4} {'alpha':>6} {'beta':>6} {'gamma':>6} {'all>=batna':>10}  outcome")
for total, per_faction, deal, above_batna in scored[:10]:
    pf = " ".join(f"{f}={per_faction[f]:>5.1f}" for f in factions)
    flag = "YES" if above_batna else "no"
    deal_str = " | ".join(f"{k.split('_')[0]}={v[:18]}" for k, v in deal.items())
    print(f"{int(total):>4} {pf}  {flag:>10}  {deal_str}")
print()

# Best deal where everyone wins
voluntary_sorted = sorted(voluntary, key=lambda x: -x[0])
if voluntary_sorted:
    print(f"=== Best Pareto-optimal deal where every faction clears BATNA ===")
    top_total, top_pf, top_deal, _ = voluntary_sorted[0]
    print(f"Sum: {top_total}  Per faction: {top_pf}")
    deltas = {f: top_pf[f] - batnas.get(f, 0) for f in factions}
    print(f"Deltas above BATNA: {deltas}  (sum: {sum(deltas.values())})")
    print(f"Outcomes: {top_deal}")

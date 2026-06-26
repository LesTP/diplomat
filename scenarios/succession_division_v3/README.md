# succ-v3 (Verdanian Succession, Resolvable Contest)

- **Factions:** alpha, beta, gamma
- **Issues:** industrial_heartland, central_treasury, defense_command
- **Game mode:** mixed

## Goal

A distributive contest that discriminates negotiation skill: constant-sum payoffs (no Pareto-dominant attractor) with a CONTESTED asset (alpha and beta both rank industrial_heartland #1) so there is no 'everyone-takes-their-own-priority' focal point. Unlike succ (Run 19, focal-point convergence) and succ2 (Run 20, deadlock), the sweet spot is a contest that RESOLVES: enough BATNA-clearing deals that games close, and each faction can win the contested asset outright (winner_spread). Skill shows in WHO wins, not in WHETHER anyone closes. NOTE: no_exact_ties is deliberately NOT required - a few tied-top deals among the contest set are tolerated (the balanced/symmetric structure that avoids seat-bias inherently produces some ties; the reference `succ` scenario has them too). The live mixed-model run is the real discrimination check.

## Brief check

**Result: PASS**

| Feature | Expected | Observed | Result |
|---|---|---|---|
| constant_sum | True | True | PASS |
| priority_collision | 'soft' | 'soft' | PASS |
| no_focal_point | True | True | PASS |
| winner_spread | {'min_per_faction': 2} | {'per_faction': {'alpha': 3, 'beta': 4, 'gamma': 4}, 'min': 3} | PASS |
| batna_clearing_count | {'min': 6, 'max': 18} | 12 | PASS |

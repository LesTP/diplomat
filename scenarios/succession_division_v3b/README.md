# succ3b (Verdanian Succession, Two-Way Heartland)

- **Factions:** alpha, beta, gamma
- **Issues:** industrial_heartland, central_treasury, defense_command
- **Game mode:** mixed

## Goal

succ3b - a 2-outcome-heartland variant of succ-v3. industrial_heartland has only Alpha-Administered / Beta-Administered (no neutral-steward option), so the heartland is a GENUINE two-way contest by construction - it must go to alpha or beta, and gamma cannot punt-win it (the gamma-steward prevalence that dogged succ-v3 is eliminated structurally). gamma is a PURE KINGMAKER: it cannot win (its ceiling is below a heartland winner's at any non-trivial BATNA), but its treasury/defense vote is needed for a deal to clear. Discrimination signal: WHO wins the contested heartland (alpha vs beta). With seat rotation (runrotate) each model plays every seat, so gamma games are a constant wash and the alpha-vs-beta games carry the skill signal.

## Brief check

**Result: PASS**

| Feature | Expected | Observed | Result |
|---|---|---|---|
| constant_sum | True | True | PASS |
| priority_collision | 'soft' | 'soft' | PASS |
| no_focal_point | True | True | PASS |
| batna_clearing_count | {'min': 4, 'max': 14} | 7 | PASS |

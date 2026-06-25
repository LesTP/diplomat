# succ (succession_division_v1) — design brief

**Intent.** A distributive negotiation that discriminates *claiming* skill: a
constant-sum payoff structure (so no deal Pareto-dominates another) with a set
of BATNA-clearing "contest" deals, each favoring a different faction. Which deal
is agreed should turn on negotiation skill, not on seat assignment.

**Required discriminating properties** (see `brief.json` `features`):

- `constant_sum` — every deal sums to the same total across factions, so there
  is no mathematically dominant attractor.
- `no_focal_point` — there must be **no** "everyone takes their own priority
  asset" deal that clears all BATNAs; such a deal is a behavioral Schelling
  point that all models coordinate on regardless of skill.
- `no_exact_ties` — no BATNA-clearing deal may leave the top two factions
  exactly tied (an equal-split focal point).
- `winner_spread` — across the contest deals, each faction should be able to win
  at least one outright.
- `batna_clearing_count` — a healthy contest set (not so few that the game
  deadlocks, not so many it is trivially cooperative).

**Why this brief exists.** Run 19 (2026-06-22) ran `succ` live before any
structural gate existed and found every game converged on the same
"Alpha-Administered / Beta-Custody / Gamma-Command" deal — rank was decided by
seat, not skill. `verify_scenario_optimum --brief brief.json` now FAILs this
scenario on `no_focal_point` (that focal deal scores 13/11/12 and clears every
BATNA) and on `no_exact_ties`, surfacing the defect without a paid run. See
`TUNING_LOG.md` Run 19.

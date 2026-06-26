# succ3b (succession_division_v3b) - design brief

**Intent.** A 2-outcome-heartland variant of succ-v3 that gives a *structurally
clean* alpha-vs-beta contest. `industrial_heartland` has only `Alpha-Administered`
/ `Beta-Administered` - no neutral-steward option - so the heartland MUST go to a
contestant and the gamma-steward prevalence that dogged succ-v3 (8-9 of 12
clearing deals routed the heartland to gamma) is **eliminated by construction**.

**gamma is a pure kingmaker.** With the heartland off-limits, gamma's ceiling
(18) sits below a heartland winner's (22), so at any non-trivial BATNA gamma
cannot win - but its treasury/defense vote is required for a deal to clear (in
every clearing deal gamma scores a constant 12, having taken treasury or
defense). This is intentional: see "winner_spread" below.

**How it relates to the succ line:**
- `succ` (Run 19): focal-point convergence (everyone-takes-own).
- `succ2` (Run 20): hard collision -> deadlock.
- `succ-v3` (3-outcome heartland): resolves, but ~67% of clearing deals route the
  heartland to the neutral steward (gamma), a structural artifact of strict
  constant-sum + a 3-outcome contested asset.
- `succ3b` (this): drops the steward outcome entirely -> a two-way heartland
  contest with gamma as kingmaker.

**Verified structure (brief-check, all declared features PASS) at BATNA 6:**

| Feature | Target | Measured |
|---|---|---|
| `constant_sum` | true | true (every deal sums to 36) |
| `priority_collision` | soft | soft (alpha+beta both top-rank the heartland) |
| `no_focal_point` | true | true (alpha & beta collide on the heartland) |
| `batna_clearing_count` | 4-14 | 7 |

Deal space is 2x3x3 = 18. Of the 7 clearing deals the heartland splits alpha 3 /
beta 4, no ties, and gamma is compensated (=12) in all 7.

**Why `winner_spread` is NOT in this brief.** The brief-check's `winner_spread`
feature requires EVERY faction to win >= N deals. That is the wrong test for a
kingmaker design: gamma cannot win at any non-trivial BATNA (a BATNA sweep
showed gamma wins 0 at BATNA 6-7, and only reaches 2 wins at BATNA 4 where all 18
deals clear - degenerate). The discrimination signal here is the **alpha-vs-beta
heartland split** (3/4), not a 3-way winner spread. With seat rotation
(`runrotate`) every model plays every seat, so the gamma games are a constant
wash for all models and the alpha/beta games carry the skill signal (did you win
the heartland from the alpha or beta seat?).

**Tooling note / limitation surfaced.** The brief-check cannot currently express
"winner_spread among a subset of factions" (contestants only). A future
enhancement could add a subset-scoped winner_spread; for now the alpha/beta
balance is documented and visible via `verify_scenario_optimum`.

**succ-v3 vs succ3b - both are kept; they measure different things:**
- `succ-v3` - a full 3-way distributive contest (all factions can win), with some
  gamma-steward noise.
- `succ3b` - a purer 2-way "who wins the contested asset" contest with a
  controlled kingmaker.

**The live run is the real discrimination check.** Run:
```bash
bash tools/ablation_multi.sh runrotate 'M1,M2,M3' succ3b bare 3   # seat-rotated mixed-model
python -m tests.self_play.rank_aggregator                         # mean_rank leaderboard
```

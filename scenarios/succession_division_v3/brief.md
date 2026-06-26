# succ-v3 (succession_division_v3) - design brief

**Intent.** The discriminating distributive scenario Runs 19/20 were reaching
for: a contest where deals **close** AND the **winner varies by skill**, so the
section 3.5 rank lens produces signal. Skill shows in WHO wins the contested
asset, not in WHETHER anyone closes.

**How it threads the needle between succ and succ2:**

- `succ` (Run 19) had a **behavioral focal point** - each faction's priority was
  on a distinct issue, so "everyone takes their own asset" cleared all BATNAs and
  every model coordinated there (rank = seat).
- `succ2` (Run 20) added a **hard heartland collision** to kill the focal point
  but **overshot into deadlock** - only 4 BATNA-clearing deals, all tied at the
  top, BATNA 9 too high relative to the loser's compensation (5/6 games no-deal).
- `succ-v3` keeps the contested heartland (alpha and beta both rank it #1, so no
  focal point) but **lowers BATNAs to 7 and widens the loser's compensation** so
  the contest **resolves**: 12 BATNA-clearing deals and each faction can win
  outright.

**Verified structure (brief-check, all required features PASS):**

| Feature | Target | Measured |
|---|---|---|
| `constant_sum` | true | true (every deal sums to 36) |
| `priority_collision` | soft | soft (alpha+beta contest the heartland; gamma distinct) |
| `no_focal_point` | true | true (no everyone-takes-own deal clears) |
| `winner_spread` | min_per_faction >= 2 | {alpha:3, beta:4, gamma:4} |
| `batna_clearing_count` | 6-18 | 12 |

**Deliberately NOT required: `no_exact_ties`.** A balanced/symmetric contest
(no seat-bias) inherently produces a few tied-top deals - the reference `succ`
has them too. Eliminating every tie would require asymmetry that re-introduces
seat-bias. A few ties among the contest deals are tolerated; they are not a
single Schelling focal point.

**Gamma-steward tightening (2026-06-25).** The `Gamma-Administered` (neutral
steward) payoff for the contestants was lowered (alpha 4->3, beta 5->4; gamma
3->5) to discourage punting the heartland to gamma. Effect: the degenerate
"gamma takes all three" sweep (8/8/20) is **eliminated** (alpha now falls to its
BATNA there). However, ~8 of 12 clearing deals still route the heartland to the
neutral steward - this is driven by **gamma's strong uncontested treasury +
defense lane** (Gamma-Custody 8, Gamma-Command 9 -> gamma scores ~16 whenever it
also takes treasury or defense), NOT by the steward payoff, so the GA shift
cannot fully remove it under constant-sum.

**Known residual (live-run watch).** The winner still varies across the gamma-
steward deals ({alpha:3, beta:4, gamma:4}), so this is not a single focal point.
But if the live run shows convergence on gamma outcomes regardless of skill, the
real fix is to **weaken gamma's treasury/defense lane** (lower Gamma-Custody /
Gamma-Command, compensating alpha+beta). NOTE the tension: gamma's wins live in
those gamma-heavy deals, so weakening gamma (or raising BATNA above 7) quickly
drops gamma below the `winner_spread` floor (BATNA 8 -> gamma wins 1; BATNA 9 ->
gamma wins 0). The band is narrow; tune against the brief.

**The live run is the real discrimination check** - succ/succ2 were only revealed
as non-discriminating by Runs 19/20. The brief-check reduces wasted-run risk; it
does not replace the run.

**Run it:**

```bash
bash tools/ablation_multi.sh runrotate 'M1,M2,M3' succ3 bare 3   # seat-rotated mixed-model
python -m tests.self_play.rank_aggregator                        # mean_rank leaderboard
```

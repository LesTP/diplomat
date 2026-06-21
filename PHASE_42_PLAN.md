# Phase 42 Plan — Builder Algorithm + Spec-Language Fixes

> Working plan for Phase 42 (algorithm fixes triggered by Phase 41/3 probe
> data). Phase 4 docs are already complete and reference this work as
> queued; Phase 2b (runtime partial-agreement detection) remains out of
> scope. Delete this file once Phase 42 ships, same as Phase 1, 2a, 3.

---

## Cold Start — Resume from here

A future session can pick up by reading this file alone. Current state:

**Where we are:** Phase 42 Commits 1-4 + C5a landed. Wall-clock
improvements shipped (6× faster matrix sweep). F-axis cliff fixed
(PROJECT.md success criterion "4+ factions" met). I-axis cliff PARTIALLY
fixed by C5a: 3×4×3 (D=81) now 3/3 via relative
`batna_clearing_count_target`; but 4×4×4 (D=256) still 0/3 — that residual
wall is algorithmic, not spec-semantic (see C5a findings below). PROJECT.md
"4+ issues" criterion NOT yet met at 4×4×4; next work is C5b.

**Active commits:**
- `551caa9` — Phase 42 C1: F-aware biasing + deepcopy removal
- `257b1e0` — Phase 42 C2: Relative `pareto_count_target` (spec language)
- `d16248c` — Phase 42 C3: Skyline Pareto (9.7× speedup at D=256)
- `4c67abb` — Phase 42 C4: Re-probe + Phase 3 C3 decision
- `19e6a39` — Phase 42 C5a: Relative `batna_clearing_count_target` (spec
  language) + probe `--relative-batna` flag

**Where to look:**
- Data: `scenarios/scale_probe_results_post_phase42_absolute.jsonl` +
  `scenarios/scale_probe_summary_post_phase42_absolute.md` (side-by-side
  vs pre-42 baseline)
- Earlier baseline: `scenarios/scale_probe_results.jsonl` +
  `scenarios/scale_probe_summary.md`
- Spec / scoring entry points: `src/scenario_authoring/scenario_builder.py`,
  `scenario_fitness.py`, `scenario_spec.py`, `verify_scenario_optimum.py`
- Operator workflow guide: `SCENARIO_GUIDE.md`
- Architecture: `ARCH_scenario_authoring.md`

**Next concrete work:** Phase 42 Commit 5b (algorithmic neighborhood
broadening). C5a is done and confirmed the residual 4×4×4 cliff is
algorithmic, not spec-semantic — start with 5b.1 (multi-cell flips).

**What does NOT work to copy from C2:** "relativize one target and hope".
C2 proved that single-target relativization doesn't fix the I-axis cliff.
C5 needs to attack multiple structural issues at once OR adopt a sharper
hypothesis about which constraint is binding.

**Test gate:** `pytest tests/test_scenario_*` (112 tests) — green at end of C5a.
Targeted regression probe: `python tools/scenario_builder_scale_probe.py
--cells 3x3x3,4x3x3,6x3x3,3x4x3,4x4x4 --seeds 3 --max-restarts 50 --output
<tmp>.jsonl` — current state: 6×3×3 and 3×3×3 reliable; 3×4×3 now 3/3 under
`--relative-batna` (C5a); 4×4×4 still 0/3 under all target forms (algorithmic).

---

**Status:** In progress (Commits 1-4 + C5a done; C5b pending). I-axis cliff partially resolved (3×4×3 fixed by C5a); 4×4×4 residual wall is algorithmic — C5b is the load-bearing remaining work.
**Started:** 2026-06-21
**Completed:** TBD

**Progress:**
- [x] Commit 1 — Cheap wins: faction biasing scale-up + deepcopy removal (`551caa9`)
- [x] Commit 2 — Relative `pareto_count_target` dual semantics (`257b1e0`) — spec feature lands cleanly; convergence claim refuted by data
- [x] Commit 3 — Skyline Pareto algorithm (`d16248c`) — 9.7× wall-clock speedup at D=256; convergence unchanged as expected
- [x] Commit 4 — Re-probe + Phase 3 C3 decision (`4c67abb`) — PROJECT.md success criterion half-met (F-axis yes, I-axis no); Phase 3 C3 stays deferred
- [~] Commit 5 *(load-bearing remaining work)* — I-axis convergence. See sub-plan below.
  - [x] C5a — Relative `batna_clearing_count_target` + probe `--relative-batna` flag. **Fixes 3×4×3 (0/3→3/3); isolates 4×4×4 residual as algorithmic.**
  - [ ] C5b — Algorithmic neighborhood broadening (targets the 4×4×4 / D=256 wall)
  - [ ] C5c *(optional)* — Target-weight rebalancing

---

## Goal

Address the three convergence cliffs found by the Phase 3 scale probe:

1. **F=6 fragility** (1/3 acceptance at 6×3×3 despite D=27): biasing helpers
   only meaningfully touch 2 of N factions.
2. **I≥4 cliff** (0/3 acceptance at 3×4×3 onwards with fixed
   `pareto_count_target=(3, 5)`): natural Pareto frontier grows with deal
   space; fixed targets become infeasible.
3. **Wall-clock at D≥729**: ~10 min/seed; D=3125 projects to hours.

Concrete success criterion (matches PROJECT.md):

> Reverse scenario builder scales to 4+ factions / 4+ issues.

After Phase 42, 4×4×4 and 5×5×5 cells should achieve ≥2/3 acceptance in
the probe matrix at `max_restarts=50`.

## Decisions to confirm before Commit 1

These materially affect Commit 1+; default proposed in **bold**.

| Decision | Default | Alternatives |
|---|---|---|
| Spec language for relative targets | **Dual semantics: int/range = absolute (existing); float/float-range = fraction of D** | New field name (`pareto_count_target_relative`); flag (`scale_relative: true`); breaking migration |
| Skyline algorithm choice | **Kung-Luccio-Preparata** (classic, simple, O(D log D) for low dim) | BBS-tree; just bigger constants on O(D²) double-loop |
| Scope cap on Phase 42 | **Commits 1-4 only; defer C5 (delta-fitness / parallelism) unless re-probe shows we still can't reach 5×5×5** | Include C5 unconditionally |
| `joint_space_mission_v1/spec.json` migration | **Leave at absolute `[3, 5]` (existing semantics still work)**; document relative option in spec.json comments or SCENARIO_GUIDE | Auto-migrate to relative form |
| Probe-as-regression-gate at each commit | **Yes, small subset (3×3×3, 4×3×3, 4×4×4, 3×4×3) after each commit; full matrix only at Commit 4** | Full matrix every commit (expensive); none until C4 (risky) |

## Open questions deferred

1. **Builder-emitted `coalition_values`** — `ScenarioSpec.requires_coalition_values` flag was deferred from Phase 2a. Phase 42's spec-language work is the natural moment to add it, but it's orthogonal to the cliff fixes. Defer to a Phase 2b-adjacent commit unless the spec-language commit creates a natural slot for it.
2. **`fill_narrative()` extension for coalition_values** — Phase 2b candidate.
3. **`max_local_moves` exposure on CLI** — currently hardcoded at 200. Some Phase 42 work might want to vary it. Add the flag if needed during implementation; not a blocker.

---

## Execution order

### Commit 1 — Cheap wins (faction biasing + deepcopy removal) (DONE — `551caa9`)

**Goal:** Address the F=6 cliff + reduce per-move overhead without touching
algorithmic structure.

**Changes:**

| Component | Change | Expected impact |
|---|---|---|
| `_seed_scoring_table` (`scenario_builder.py`) | F.1: scale `priority_collision="soft"` biasing to `max(2, F // 2)` factions instead of `min(2, F)` | 6×3×3 acceptance should improve |
| `_seed_scoring_table` (`scenario_builder.py`) | F.2: when `requires_logrolling=True`, plant the priority-deal-with-all-factions pattern for all F factions, not just the soft-collision pair | Same |
| `_anneal_local` (`scenario_builder.py`) | A.4: replace `scoring = copy.deepcopy(scoring)` per move with mutate-then-revert if rejected | Per-move overhead drops; wall-clock relief everywhere |

**Tests:** existing tests should still pass; specifically `_seeded_tables_*`
tests in `test_scenario_builder.py` may need their assertions widened or
new variants added (the bias pattern changes shape).

**Probe regression check:** small subset — `3x3x3, 4x3x3, 6x3x3, 4x4x4` at
seeds=3. Target: 6×3×3 reaches ≥2/3 acceptance; other cells unchanged or
improved.

### Commit 2 — Relative `pareto_count_target` (DONE — `257b1e0`; partially refuted)

**Goal:** Address the I≥4 cliff by making the spec language scale-aware.

**Changes:**

| Component | Change |
|---|---|
| `scenario_spec.py` | Extend `pareto_count_target` validation to accept floats in (0, 1] or float-ranges `(lo, hi)` with both ∈ (0, 1] as "fraction of D". Reject ambiguous cases (e.g., bare 1.0 — disallow boundary value, require explicit fraction or absolute count) |
| `scenario_fitness.py` | `compute_fitness` detects target type at runtime; if float/float-range, computes `effective_target = round(spec_target * D)` (or range bounds) at evaluation time. Distance computation unchanged after that translation. |
| `scenario_builder.py` `_target_pareto_count_matches` | Same conversion logic; gate the strict Pareto-count check against the converted absolute target |
| `_log_search_restart` | Include the effective absolute target in the log record alongside the spec value, so debug output makes sense |
| Tests | New test cases for both float scalar and float range; mixed validation tests; conversion-correctness tests against several D values |

**Backward compat:** existing specs (integer / integer-range
`pareto_count_target`) work unchanged. `joint_space_mission_v1/spec.json`
stays at `[3, 5]`.

**Probe regression check:** same subset as Commit 1, PLUS a new probe spec
that uses relative targets: `pareto_count_target=0.10` (10% of D, scales
across cells naturally). Target: 4×4×4 and 5×5×5 (when added back to
matrix) reach ≥2/3 acceptance.

### Commit 3 — Skyline Pareto algorithm (DONE — `d16248c`; 9.7× at D=256)

**Goal:** Reduce the `O(D²)` Pareto bottleneck so D≥729 doesn't take 10 min.

**Changes:**

| Component | Change |
|---|---|
| `verify_scenario_optimum.py::find_pareto_frontier` | Replace naive `O(D²)` double-loop with Kung-Luccio-Preparata Skyline algorithm: sort by first faction's score, sweep, maintain dominated-by-best set. Cost: O(D log D) for low F (Skyline degrades to O(D²·log D / F!) at high F, but our F is small) |
| Tests | Existing `test_pareto_*` tests in `test_self_play.py` and `test_scenario_fitness.py` should still pass — correctness preserved |

**Correctness validation:** run the new Skyline implementation alongside
the old `O(D²)` implementation on a fixture set; assert identical frontier
output. Once verified, remove the old code.

**Probe regression check:** small subset + a wall-clock-focused probe at
3×6×3 (D=729). Target: ≥5× wall-clock reduction at D=729; acceptance
rates unchanged.

### Commit 4 — Re-probe + Phase 3 C3 decision (DONE — `4c67abb`)

**Goal:** Verify the success criterion and decide on the deferred Phase 3
regression test.

**Operator-supervised:** run the full matrix sweep:
```bash
python tools/scenario_builder_scale_probe.py \
    --cells matrix \
    --seeds 3 \
    --max-restarts 50 \
    --output scenarios/scale_probe_results_post_phase42.jsonl \
    --summary scenarios/scale_probe_summary_post_phase42.md
```

Update `scenarios/scale_probe_summary_post_phase42.md` with side-by-side
comparison to the pre-Phase-42 run. Verify:
1. 4×4×4 achieves ≥2/3 acceptance (PROJECT.md success criterion met)
2. 6×3×3 acceptance rate improved
3. Wall-clock at 3×6×3 reduced ≥5×
4. No regressions at small cells

**If success criterion is met:** activate Phase 3 Commit 3 (pytest regression
for `test_builds_4x4x4_in_budget`) — formerly deferred because it would have
just frozen the failure.

**If not met:** triage. Likely cause is one of the deferred algorithmic
items (delta-fitness, parallelism, or a deeper search-strategy change).
Proceed to Commit 5 or pause for re-planning.

### Commit 5 *(optional)* — Delta-fitness or parallel restarts

**Triggered by:** Commit 4 re-probe showing the success criterion isn't
met yet, OR an operator decision to push beyond 5×5×5.

Two candidates; pick one based on what the re-probe surfaces:

- **A.2 — Delta-fitness in `_anneal_local`.** A single-cell move only
  changes scores on deals containing that (issue, outcome) pair. Cache
  per-deal scores; on a move, recompute only affected deals' scores. Cost
  per move drops from O(D·F) (full enumerate + score) to O(D/O · F)
  (subset). Invasive — requires refactoring fitness into per-deal
  contributions. Scope L.
- **A.3 — Parallel restarts.** `_search_loop` is trivially parallel —
  each restart is independent. Spawn `multiprocessing.Pool(N)` with one
  worker per restart batch. Linear speedup in core count. Scope M.

Both addressed by Commit 5 in this slot; pick by what the data demands.

---

## Final verification

After Commits 1-4 land (and optionally 5):

1. `pytest tests/` — full non-integration suite passes (baseline: 426
   passed, 1 skipped from Phase 2a closure; should be +1 if Phase 3 Commit
   3 lands)
2. `python tools/scenario_builder_scale_probe.py --cells matrix --seeds 3 ...`
   — 4×4×4 ≥2/3 acceptance; 6×3×3 ≥2/3 acceptance
3. `scenarios/scale_probe_summary_post_phase42.md` shows acceptance
   improvements + wall-clock reductions vs. pre-Phase-42 baseline
4. PROJECT.md success criterion ("scales to 4+ factions / 4+ issues") is
   now empirically supported

## Out of scope (explicit)

- **Phase 2b** (runtime partial-agreement detection during gameplay) — distinct from algorithm work
- **`ScenarioSpec.requires_coalition_values`** builder flag — deferred from Phase 2a; can land alongside Phase 42 only if the spec-language commit has a natural slot for it
- **`fill_narrative()` extension** for coalition_values — Phase 2b
- **6×6×6+ cells** — practical wall remains; not in scope to chase
- **TypedDict / dataclass for `scenario_analysis`** — deferred indefinitely
- **Builder UX improvements** (target tuning, validation messages) — separate concern

## Notes for future phase planning
- Phase 42 is the first phase whose scope was *fully data-driven* by an
  earlier phase (Phase 3 / 41). The pattern worked: empirical sweep 
  concrete cliffs  prioritized fix list. Worth repeating for future
  algorithmic work.
- The probe (Phase 3 Commit 1) is the regression gate. Each Phase 42
  commit can validate against it cheaply.
- The "spec-language change" insight (Cliff 2 isn't algorithmic - it's
  spec semantics) was the highest-leverage finding. Easy to miss without
  the matrix data.

---

## Commit 5 — I-axis convergence (sub-plan)

The data from Commits 2 and 4 refuted the original hypothesis that
relativizing `pareto_count_target` alone would fix the I-axis cliff.
Three sub-commits proposed, ordered by directness of follow-up to
prior work + scope. Land them sequentially; re-probe after each to
update the live data.

### Decisions to confirm before C5a

| Decision | Default | Alternatives |
|---|---|---|
| Start with which sub-commit? | **5a** (relativize `batna_clearing_count_target`) — mirrors C2 mechanically, validates whether multi-target relativization is the binding constraint | 5b first (algorithmic neighborhood) if you believe the issue is search-space-not-spec |
| Spec migration for existing `joint_space_mission_v1/spec.json`? | **No** — `batna_clearing_count_target=10` stays absolute; new relative form is opt-in | Auto-migrate to relative form |
| Sub-commit scope cap | **C5a + C5b only; defer C5c (weight rebalancing) unless C5b's re-probe still fails** | Include C5c unconditionally |
| Add a `--target-overrides` flag to the probe | **Yes** — needed to test mixed absolute/relative target sweeps without rebuilding `synthesize_spec` each time | Just edit synthesize_spec |
| Algorithmic changes touch `RoundSteppedFlow` or scoring engine? | **No** — Phase 42 stays in `scenario_builder` / `scenario_fitness` / `scenario_spec` | Yes if needed (becomes Phase 2b adjacent) |

### Sub-commit 5a — Relativize `batna_clearing_count_target` (smallest scope)

**Hypothesis to test.** The reason the I-axis cells fail isn't
`pareto_count_target` alone — it's that `batna_clearing_count_target=5`
(absolute) is structurally easier as deal space grows, AND/OR
`requires_logrolling` becomes harder with more issues. By making
`batna_clearing_count_target` scale-aware (e.g., 0.20 = 20% of D
must beat all BATNAs), we test whether multi-target relativization
is sufficient.

**Changes:**
- `scenario_spec.py`: add `_validate_batna_clearing_count_target` accepting
  int (absolute, existing) or float in (0.0, 1.0] (fraction of D).
  Reject mixed-type ranges per the C2 convention.
- `scenario_fitness.py`: in `compute_fitness`, resolve the target via a
  new sibling helper `resolve_batna_clearing_count_target(target, D)`
  (mirrors `resolve_pareto_count_target`).
- Add resolver export to `scenario_spec.py` module-level.
- 6-8 new tests in `test_scenario_spec.py` for validator + resolver.

**Probe regression target (re-run with `--relative-targets`):** 4×4×4 ≥2/3
acceptance. If yes, the I-axis cliff is in fact a "multiple absolute
targets stacked" problem and 5b/5c may not be needed.

**Probable outcome to watch for:** if 4×4×4 still 0/3 after 5a's relative
batna_clearing, the cliff is genuinely algorithmic (5b). If 4×4×4 hits
≥2/3 acceptance, we've nailed the structural issue and can declare
PROJECT.md success criterion met.

**Result (2026-06-21) — DONE.** Implemented `_validate_batna_clearing_count_target`
+ `resolve_batna_clearing_count_target` (mirrors C2; absolute ints stay
*non-negative* so the legal 0 case is preserved), wired the resolver into
`compute_fitness`, and added a `--relative-batna` probe flag (0.20 = 20% of D,
≈ the baseline 5/27 proportion). Re-probe (seeds=3, max_restarts=50):

| Cell | absolute | rel-pareto only | rel-batna only | rel-both |
|---|---|---|---|---|
| 3×4×3 (D=81) | 0/3 | 0/3 | **3/3** | **3/3** |
| 4×4×4 (D=256) | 0/3 | 0/3 | — | 0/3 |

- **3×4×3 cliff resolved by C5a alone.** Relative `batna_clearing_count_target`
  fixes it outright (converges <1.5s) *with pareto left absolute*, so the batna
  relativization is the active ingredient. C2's pareto relativization is inert
  here (identical to absolute). Confirms the hypothesis: absolute
  `batna_clearing_count_target=5` is structurally mismatched as D grows.
- **4×4×4 unaffected by any target form** — exhausts the full 50-restart budget
  (~30s) every time. Per the decision rule, the residual D=256 cliff is
  **algorithmic, not spec-semantic** → proceed to C5b.
- PROJECT.md "4+ issues" criterion still NOT met at 4×4×4.

Evidence: `scenarios/c5a_probe_{absolute,rel_pareto,rel_both,rel_batna_only}.jsonl`.

### Sub-commit 5b — Algorithmic neighborhood broadening (if 5a insufficient)

**Hypothesis to test.** The single-cell SA neighborhood is too narrow for
high-D search. Even with right targets, the algorithm can't navigate
through good intermediate states because every move changes only one
score cell.

**Changes (pick one or layer):**
- **5b.1 — Multi-cell flips.** With probability p (e.g., 0.3), the SA
  proposal flips 2-3 cells simultaneously instead of 1. Wider exploration
  per move.
- **5b.2 — Issue-scoped swaps.** Propose swapping all scoring values
  within a single issue between two factions. Targets the priority-
  collision constraint structure.
- **5b.3 — Outcome-rank swaps.** Within a faction's single issue, swap
  the score values of two outcomes (preserving the score multiset).
  Targets logrolling structure.

5b.1 is the easiest to add and most generic; start there. 5b.2 / 5b.3
are domain-aware moves; add if 5b.1 isn't enough.

**Probe regression target:** 4×4×4 ≥2/3 acceptance under absolute targets
(NOT relying on relativized targets). If 5b alone gets us there, 5a's
relativization is a separate nice-to-have rather than load-bearing.

### Sub-commit 5c *(optional)* — Target-weight rebalancing

**Hypothesis to test.** At high-I specs, certain constraints (e.g.,
`pareto_distribution_spread`) are structurally hard to satisfy AND
not actually load-bearing for the scenario's purpose. Auto-deweighting
them at high dimensionality would let the search focus on what matters.

**Changes:**
- `scenario_fitness.py`: when computing fitness, detect spec dimensionality
  (D = `prod(len(issue.outcomes) for issue in issues)`) and auto-apply
  weight adjustments for known-fragile targets. E.g., at D ≥ 256:
  `pareto_distribution_spread` weight → 0.5; at D ≥ 1000 → 0.0.
- Operator override via existing `spec.target_weights` (no semantics change
  there; auto-adjusts apply only when operator hasn't set explicitly).

**Skip if** 5a+5b already make 4×4×4 reliable. Could be re-scoped as a
"smart defaults" feature in a follow-up phase.

### After Commit 5

1. Re-probe full matrix (mirror C4): expect 4×4×4 ≥2/3, no regressions
2. **Add pytest regression** (previously deferred from Phase 3 / scale-probe
   work): `tests/test_scenario_builder_scale.py` with `test_builds_4x4x4_in_budget`
   (and optionally `test_builds_3x4x3_in_budget`), marked `@pytest.mark.slow`
   if it takes > 30s under Skyline. Locks in the post-C5 success so future
   builder/algorithm regressions don't silently break 4×4×4.
3. Update PROJECT.md success criterion line to reflect "MET" status
4. Update `ARCH_scenario_authoring.md` "Scaling expectations" section
   with post-C5 data
5. Update `SCENARIO_GUIDE.md` "Practical authoring rules of thumb" with
   the post-C5 reliable dimensions
6. Delete `PHASE_42_PLAN.md` (Phase done)

### Risks

- 5a might land cleanly but not move 4×4×4 — would expand 5b's scope
- 5b multi-cell flips could change RNG flow significantly; may regress
  small cells. Watch for it.
- 5c is speculative; defer indefinitely if 5a+5b suffice.

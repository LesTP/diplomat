# Diplomat — Next Steps

> Working document. Updated 2026-06-07.
>
> Related: `DEVPLAN.md` (canonical phase plan), `TUNING_LOG.md` (run-by-run record),
> `ARCH_conversation_model.md` (Stage 1/2/3 migration), `RUN_PROTOCOL.md` (pre-flight),
> `ASSESSMENT.md` (scoring framework + workstream blocks).

> **Workstream block tags.** Every section heading and item carries one
> of `[A]`, `[B]`, `[C]`, or `[X]` per `ASSESSMENT.md` §5:
> - `[A]` agent architecture & memory (pipeline modules, state, conversation model)
> - `[B]` prompt tuning (personas, module prompts, strategy library, voice)
> - `[C]` game creation & scoring (compiler, BATNA, pressure, verification, scoring lenses)
> - `[X]` cross-cutting (toolkit infra, deployment, integration tests, meta-tests)
>
> Multiple tags = item touches multiple blocks; primary block listed first.

> **Loop-readiness classification.** Items are also classified for autonomous-loop suitability:
> - 🔨 **PURE BUILD** — code/refactor only, deterministic, no operator judgment mid-loop. Suitable for autonomous build phases.
> - 🔀 **MIX** — has a build component but needs operator decisions at boundaries.
> - 👁 **SUPERVISED** — experiments, prompt tuning, design judgment, or interactive work. Operator-driven only.

> **Tier-priority rationale (D-56 direction commit, 2026-06-16).** Under
> the negotiation-benchmark direction per `DECISIONS.md` D-56, **Tier 1 is
> now `[C]` game creation & scoring** (the primary investment surface),
> **Tier 2 is `[A]`/`[X]` infrastructure that serves the benchmark**, and
> **Tier 3 / Deferred holds coaching-product items** (infrastructure
> preserved, no new investment). This inverts the pre-D-56 tiering which
> had Block A foundational + Block C secondary + Block B prompt-tuning
> third. The "Open items by workstream tier" section below reflects the
> new ordering; per-section detail (§1.6 through §11) keeps historical
> numbering for stable cross-references.

> **State as of 2026-06-16 (post-D-56 pivot):** Phases 20–38 closed.
> Runs 9 + 10 + 13 + 14 (WR-β ablation matrix, 18 cells) + 15 (jsm1
> calibration) + 16 (jsm1 ablation matrix, 12 cells) + 17 (multi-provider
> calibration, 10 cells landed; R1 partially deferred for toolkit fix,
> then unblocked at toolkit `606e309` — R1 cell #1 landed before cap)
> closed. **D-56 commits to benchmark direction** — coaching product
> (Run 13b, §4 Pi coaching loop, §5 Clankmates, persona drift A/Bs)
> deferred; benchmark items (§11 competitive scoring, Path B coalition
> scoring, §3.5/3.6 scoring lenses, scenario-class authoring,
> Phase 41/42) promoted to Tier 1.
>
> **Cross-tier, cross-scenario harness findings (Runs 14 + 16 + 17 combined):** Harness contribution is in close-rate, not deal quality (every closing run on either scenario finds the *identical* Pareto deal for that scenario). Harness lift is scenario × tier dependent: WR-β weak +67% / mid +33% / strong 0%; jsm1 weak +33% / mid 0% / strong 0%. Multi-provider extension: DeepSeek V3 sits in a hybrid "mid+" tier (sonnet-like refusal on WR-β, harness-lift on jsm1). The "richness alone produces harness lift" formulation of Note 1 is partially refuted. Revised framing: **harness contribution = f(scenario shape, what the model already does well)**. See `RESEARCH_NOTES.md` Note 1 amendment 2026-06-12 + Note 2 resolution 2026-06-16.
>
> **Reverse scenario builder lineage:** Phase 35 shipped the tool; Phase 36 added soft-weighted fitness + simulated annealing + biased init; Phase 37 added `pareto_outcome_diversity`; Phase 38 closed the pressure-mechanisms small bundle; Phase 41/42 remain queued for larger-search-space verification — promoted to Tier 1 under D-56 — see §8.
>
> **Clankmates integration:** deferred under D-56 (coaching-product surface). Toolkit-side `clankmates_client` work continues independently per its own roadmap; diplomat-side `ClankmatesTransport` no longer Tier 1.

---

## Closed since 2026-05-30

Audit trail moved to **Appendix A** at the end of this document — 30+ closed
items across Phases 19-28 + Runs 9-17 + a handful of rescoped / rejected
items. Canonical detail lives in `DEVLOG.md` / `DEVLOG_archive.md` and
`TUNING_LOG.md` / `TUNING_LOG_archive.md`.

---

## Open items by workstream tier (D-56 direction commit)

Grouped by post-D-56 priority: `[C]` benchmark direction > `[A]`/`[X]`
infrastructure that serves the benchmark > deferred (coaching product,
infrastructure preserved). Section detail (§1.6 through §11) is below and
keeps the historical numbering for stable cross-references.

### Tier 1 — `[C]` benchmark direction (primary under D-56)

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **§3.6 coalition-value scoring engine** (Path B build) | `[C][A]` | 🔨 | §11 + ASSESSMENT §3.6 | Note 2 Path B. 1-2 day build: extend `scenario_analysis.json` with `coalition_values`; modify `score_game()` to detect partial-agreement coalitions + lookup value + apply split per transcript; assign BATNA to excluded faction. **Required for mixed-model coalition scenarios to produce "X wins, Y loses" outcomes.** Three-Party Coalition v1 patched and ready as first consumer. |
| **§3.5 rank-among-factions scoring lens** | `[C]` | ✅ per-game DONE (2026-06-22) | ASSESSMENT §3.5 | **Per-game lens + faction→model persistence shipped:** `_rank_among_factions` (`faction_ranks` by absolute points, competition ties) + render + tests; `faction_models` map now persisted to result JSON. **Remaining:** optional position-rotation harness (cross-game mean_rank aggregator DONE 2026-06-22: tests/self_play/rank_aggregator.py + tests/test_rank_aggregator.py). |
| **Mixed-model dispatcher extension** | `[C][X]` | 🔨 | (§11 follow-up) | Extend `tools/ablation_multi.sh` to take heterogeneous `--per-faction-providers` JSON + position rotation. Currently same-model-all-factions only. Cheap addition (~1 hour); unblocks §11.b Path A calibration. |
| **§11.b Path A calibration — mixed Three-Party Coalition × position rotation** | `[C]` | 👁 | §11 | 9 cells (3 lineups × 3 rotations × n=1). ~$1-2, ~30 min. Suggested lineup post-Run-17: sonnet + gpt-5.4-mini + deepseek/deepseek-chat. Tests whether mixed populations produce transcript differentiation in the current unanimity frame; outputs inform whether to invest in Path B vs Path C first. |
| **Path C scenario-class authoring** | `[C]` | 👁 | §11 / §2 | Distributive bargaining (fixed pie, identical-numbers deal-detection), asymmetric-BATNA-with-walkaway, hidden-value bluff. ~3 new scenarios via reverse builder + Phase 38 pressure. Produces rank-discriminating outcomes on the existing harness without requiring Path B build. |
| **Run 17 V3 full n=3 expansion** | `[C]` | 👁 | TUNING_LOG Run 17 follow-up | Solidify V3 baseline — current cells are V3 full n=1 + V3 bare n=3. ~$0.15, ~12 min. Confirms whether V3 jsm1 full = 1/1 holds at n=3 and whether V3 wrbeta full = 0/1 is robust. |
| **Run 17 R1 cells × 3 on both scenarios** (toolkit-unblocked) | `[C]` | 👁 | TUNING_LOG Run 17 follow-up | First reasoning-model data points. Toolkit `606e309` patch unblocked R1; cell #1 jsm1 already landed (DEAL, balanced-consensus). ~$2-4, ~30-90 min for 5 more cells. |
| **N4 — gpt-mini + Phase 38 pressure × 3 on jsm1** | `[C][B]` | 👁 | §10 / §2 | Pressure validation on mid-tier "stuck-but-engaged" pattern. ~$1.50 + ~36 min. Phase 38 schema ready; cleanest scenario-design lever test. |
| **Phase 41 scale-matrix verification** | `[C][X]` | 🔨 | §8 | Cheap instrumentation: run builder at 3×3×4, 4×4×4, 5×3×3, etc. with fixed simple spec; measure convergence rate + wall-clock. Reveals which shapes are feasible. ~4-5 steps; no algorithmic changes. **Unblocks richer scenarios that Note 1 untested axes need.** |
| **Phase 42 algorithm fixes** (conditional on Phase 41) | `[C][X]` | 🔨 | §8 | Scope determined by Phase 41 findings. Likely candidates: cached fitness deltas, larger neighborhoods, adaptive SA, LLM-guided init. |
| **Phase 39 exogenous events** | `[C]` | 🔨 | §2 | Mid-round shocks that recompute BATNAs. ~1.5× Phase 38 size. Promote when small-bundle pressure proves insufficient for benchmark scenarios. |
| **Per-run cost capture in result JSONs** | `[C][X]` | 🔨 | (cross-section) | `metadata.cost_usd: None` and stale `selfplay_cost_ledger.jsonl` make benchmark cost-coverage analysis back-of-envelope. Small phase, high benchmark value. |
| **Pricing audit §6** | `[X][C]` | 👁 | §6 | Cross-provider pricing accuracy across all models we actually use. Now Block C primary concern under D-56 (per-cell cost is benchmark-critical). |
| **ASSESSMENT §3.4 persuasion-shifts / concession-curve signatures** | `[C]` | 👁 | (loop-readiness) | Needs LLM-judge over transcripts. Higher cost; defer until other Tier 1 items land but stays Tier 1 (benchmark-relevant). |
| **Divorce scenario design** (Phase 38 showcase) | `[C]` | 👁 | §2 | Hand-author after benchmark scenario-class authoring (Path C) lands. Natural showcase for pressure mechanisms; specific benchmark cell. |
| **Surplus-distribution diagnosis** | `[C]` | 👁 | Backlog | Cross-scenario investigation of "why does gamma extract 52-55% of surplus?" Likely game-theoretic; if confirmed, a scenario-design lever. Stays Tier 1 — relevant to benchmark scenario authoring. |

### Tier 2 — `[A]`/`[X]` infrastructure that serves the benchmark

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Provider-native structured output** (`response_format: json_schema`) | `[X]` | 🔀 | Carry-forward | Token-level schema compliance; reduces flaky JSON failures in benchmark cells. Lower priority — current `structured_call` + retry is working. |
| **TurnBasedFlow / position-rotation harness** | `[A][C]` | 🔨 | ARCH_flow.md "Worked Example" | Required for tournament-style benchmark cells (Option D from Note 2 / Phase 40 candidate). Additive against Pipeline contract; no module changes. |
| **Reconciliation live validation** | `[C]` | 👁 | Backlog | Status transitions + inconsistency flagging untested in live runs. Run 10 B' and α-squeezed defection are natural inspection targets. Benchmark-relevant for understanding reconciler signal in mixed-model cells. |
| **Identify-the-blocker tool** | `[C][X]` | 🔀 | (loop-readiness) | Pre-game LLM analyst pass over scoring tables to predict squeeze target. Useful scenario-design aid for benchmark scenario authoring. |
| **Pareto-frontier annotation in analyst output** | `[C][B]` | 🔀 | §2 TODOs | Analyst schema + prompt change. Lower priority — under D-56 the analyst's job in benchmark cells is to produce intelligence for the *agent*, not the operator; Pareto annotation is a coaching-direction enhancement. |

### Deferred — coaching product (infrastructure preserved per D-56)

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Coaching test loop on Pi** | `[X]` | 👁 | §4 | Run 13 (2026-06-04) validated new gate end-to-end; Run 13b queued and **deferred under D-56**. Infrastructure intact; revisit if D-56 trigger condition (a) fires (real game opportunity with deadline). |
| **Run 13b** (coached game exercising `/revise:` + `/edits-summary`) | `[X]` | 👁 | §4 | Deferred under D-56. |
| **Game-platform exploration** (Clankmates / Discord / fallback) | `[X]` | 👁 | §5 | Deferred under D-56. Clankmates work continues toolkit-side independently; diplomat-side transport no longer Tier 1. |
| **TelegramReviewGate as production default** | `[X]` | 👁 | (decision) | Deferred under D-56 — production-default decisions for the coaching deployment are no longer pressing. |
| **Strategy routing** (hardball / integrative / tit-for-tat / etc.) | `[B]` | 👁 | §2.5 | Demoted under D-56. Useful as benchmark *experimental variable* if a campaign explicitly tests prompt-strategy effects, but no longer a Tier-1 build. |
| **Per-role model strategy** (consistency + cost + quality axes) | `[B]` | 👁 | §7 | Demoted under D-56. The per-role question is now subsumed under the benchmark's natural matrix (varying provider per-cell). The "production-default" framing belonged to coaching direction. |
| **Provider consistency tests** (all-Anthropic baseline + cross-scenario) | `[B][X]` | 👁 | §1.7 / §1.8 | Demoted under D-56. Information value retained — these tests would still produce benchmark-relevant data — but no longer Tier-1 priority. Can resurface if a campaign explicitly needs the data. |
| **Persona payment rigidity / drift / endgame over-anchoring** | `[B]` | 👁 | Carry-forward | Demoted under D-56. Persona tuning for live-game performance is coaching-direction work. |

### Deferred — `[A]` conversation model evolution

| Item | Tags | Loop | Where | Notes |
|---|---|---|---|---|
| **Conversation model evolution** (multi-pass / async) | `[A]` | 👁 | §3 | Stage 2a (K-pass rounds), 2b (convergence detection), 3 (true async). Original deprioritization 2026-06-02 preserved under D-56. Pursue when a benchmark scenario class demands within-round reactivity or timing-as-strategy. |

### Sequencing within Tier 1 (most actionable now, post-D-56)

If working down the tiers, the immediate decision is which Tier 1 item to do first. Recommended order under D-56:

1. **§3.6 coalition-value scoring engine (Path B build)** — load-bearing for benchmark v2 (per `PROJECT.md` MVP table). 1-2 day build; unblocks competitive mixed-model cells on coalition scenarios. Run 17 R1 + V3 expansion cells are interesting but additive; Path B is foundational.
2. **§3.5 rank-among-factions lens** — ~50 LOC, ships alongside or independently of Path B. Required competitive metric.
3. **Mixed-model dispatcher extension** + **§11.b Path A calibration** — cheap pair (~$1-2, 1 hour build). Produces the first heterogeneous-population data and informs whether to prioritize Path B (if signal in transcripts) or Path C (if no signal in unanimity frame).
4. **Path C scenario-class authoring** — distributive / asymmetric-BATNA / hidden-value via reverse builder. Independent of Path B, broadens benchmark scenario library.
5. **Run 17 V3 full n=3 + R1 expansion** — cheap follow-ups to close the Run 17 thread (~$2-5 total, ~30-90 min). Adds confirmed data points to the model matrix.
6. **N4 pressure on jsm1** + **Phase 41/42 scale verification** — Block C scenario-design work that broadens benchmark coverage.
7. **Per-run cost capture** + **Pricing audit** — small infrastructure that makes benchmark cost-coverage analysis credible.

### Sequencing within Tier 2 (operator-queued post-Phase-37)

All three queued phases share the `scenario_authoring.scenario_builder` codebase but are independent of each other; can be dispatched in any order once Phase 37 closes. Suggested order by leverage:

1. **Phase 38 — pressure mechanisms small bundle (closed)** (round-cost decay + penalty floor + asymmetric clocks). High leverage: directly addresses the Run 8/10 "agents sit at BATNA" finding and enables the divorce scenario. Builder is mostly pass-through; pipeline does the work.
2. **Phase 41 — scale matrix verification** (cheap instrumentation). Reveals which shapes work and which need algorithm fixes. Low cost, high information; can run before or after Phase 38 since they touch different parts of the code.
3. **Phase 42 — algorithm fixes for shapes Phase 41 reveals as broken**. Scope conditional on Phase 41 findings. Strategic value: enables 4+ faction / 4+ issue scenarios needed for the next round of ablation experiments against the Note 1 thesis.
4. **Phase 39 (deferred) — exogenous events** (mid-round shocks that recompute scoring). Larger phase — needs round-aware verifier and dynamic round-context. Pursue when the small-bundle pressure mechanisms (Phase 38) prove insufficient for the concession-curve behavior we want.
5. **Phase 40 (indefinitely deferred) — cascade scoring** (cross-game state). Wait for a real use case (tournament play, reputation experiments).

### Cross-tier dependencies worth knowing

- **Tier 3 §7** (per-role models) wants **Tier 1 §6** (pricing audit) — cost-quality tradeoffs need accurate cost numbers.
- **Tier 3 §1.7 + §1.8** (provider consistency tests) are *experimental data feeding into Tier 3 §7* — listed in Tier 3 because the deliverable is a tuning rule, but cheap + operator-driven so they can run independently of other tiers.

### Pure-build extensions (if extending the autonomous queue)

Items with a clean "build half" suitable for a future Phase 30+:

| Candidate | Build slice | What stays supervised |
|---|---|---|
| **`tools/identify_blocker.py`** | Read `scenario_analysis.json`; one `structured_call` to an analyst LLM asking "for the Pareto-optimal deal, which faction has to concede most on their priority issue?" Output ranked list of squeeze candidates. | Scenario-design judgment about whether to act on the recommendation. |

---

## 1.7. `[B][C]` Provider consistency as a deal-making variable (Run 10 finding)

**Headline.** Run 10 B' (alpha-squeezed BATNAs unchanged, beta's Generator
re-routed from OpenAI gpt-4.1-mini to Anthropic claude-haiku-4-5) reached the
Pareto-optimal deal that Run 9 alpha-squeezed had missed. The R3→R4 defection
pattern that broke Run 9 (beta-on-OpenAI proposed `Medium + Heavy-Downstream +
JFD` in R3 then pivoted to `High + Shared + JFD` in R4, killing the alpha+gamma
convergence) was reproduced in Run 10 C' — this time with *gamma* defecting on
the same OpenAI gpt-4.1-mini model. **Two-of-two instances of the same failure
mode on the same model, different factions.**

The cleanest reading: for OpenAI gpt-4.1-mini on Water-Rights-style scenarios,
R3 contingent commitments are unreliable — the model will textually commit then
propose something different at R4. Anthropic claude-haiku-4-5 honored beta's R3
contingent verbatim at R4 (Run 10 B').

**Why this matters.** BATNA pressure (Run 9 β-squeezed) and provider consistency
(Run 10 B') reached the *same* Pareto deal via different mechanisms. BATNA pressure
*forced* the OpenAI agent to be consistent (defecting back to BATNA was costly enough
to bind); Anthropic was consistent by default. Once you account for the provider
effect, the BATNA-pressure thesis simplifies: BATNA is a *substitute* for native
consistency on consistency-flaky models, and a *no-op* on consistency-reliable ones.

### TODOs

- [ ] **§1.7.a All-Anthropic baseline (Run 11 candidate).** Run all three Run 9
      BATNA variants (symmetric / α-squeezed / β-squeezed) with single-provider
      Anthropic claude-haiku-4-5. Tells us whether Anthropic reaches Pareto across
      the BATNA spectrum (confirming the provider-default consistency thesis) or
      only when structure favors it. ~$3-4 spend.
- [ ] **§1.7.b OpenAI defection on Three-Party Coalition / Trade Summit (§1.8).**
      Cheap (~$0.30) cross-scenario check. If the R3→R4 defection reproduces, it's
      a general OpenAI gpt-4.1-mini tuning rule (consistency-critical seats need
      Anthropic). If it doesn't, it's a Water-Rights-specific quirk likely tied to
      how the Payment issue is framed.
- [ ] **§1.7.c Update TUNING.md provider-assignment table.** Once §1.7.a + §1.7.b
      land, add a "Consistency-critical seats" row noting that beta-style
      bottleneck-holder roles should default to Anthropic for multi-round
      negotiations.
- [ ] **§1.7.d Promote provider consistency to ASSESSMENT.md §3.4.** Process
      signature "across-round commitment-following rate" is a meaningful skill
      dimension that wasn't on the original list. Worth adding once we have
      cross-scenario data.

---

## 1.8. `[B]` OpenAI gpt-4.1-mini R3→R4 defection — cross-scenario scope test

**Status.** Two instances on Water Rights so far (Run 9 α-squeezed beta, Run 10 C'
gamma). Both: faction commits at R3 to a position the other two are converging
toward, then proposes a personally-preferred alternative at R4 breaking consensus.

**Question.** Water-Rights-specific or general? If general, OpenAI gpt-4.1-mini
should not occupy any consistency-critical seat in multi-round negotiations.

### TODOs

- [ ] Re-run **Three-Party Coalition** (Run 6/7 scenario) with all OpenAI
      gpt-4.1-mini Generators, observe R3→R4 transitions for any faction.
      Use a scenario where coalition formation requires a faction to commit
      to A+B in R3 — the natural shape for the defection pattern. ~$0.30.
- [ ] Re-run **Trade Summit** (Run 5 scenario, dirty bargaining with deception
      tactics) on all OpenAI gpt-4.1-mini, observe whether the deception-then-reveal
      arc that worked in Run 5 still holds. Different question (tactical
      commitment vs cross-round commitment) but related. ~$0.30.

---

## 2. `[C]` Game pressure beyond BATNA

**Run 8 observation:** Agents sat at BATNA because BATNA was *survivable*. Alpha
won the tiebreak with score 11 = BATNA 11; nobody had structural urgency to
compromise. The Pareto-optimal Shared deal (alpha=14, beta=20, gamma=22) sat
on the table untouched.

The fix is structural, not prompt-tuning. Need mechanisms that create real
incentive to negotiate.

### Phase split (2026-06-11)

The five pressure mechanisms below split into phases by build cost:

- **Phase 38 (closed) — small bundle:** mechanisms 1 (round-cost decay), 3 (asymmetric clocks), 4 (penalty floor). All three add a `pressure` sub-object to `scenario_analysis.json`, share persona-template + round-context renderer work, and have deterministic scoring tweaks. Reverse builder mostly passes the fields through (operator-supplied values, not search targets). Phase scope: schema + renderer + verifier round-awareness + small-bundle integration test.
- **Phase 39 (deferred) — exogenous events:** mechanism 2. Needs round-aware verifier with BATNA recomputation, dynamic round-context that applies score deltas at each round. ~1.5x Phase 38 size. Pursue when small-bundle pressure proves insufficient for the concession-curve behavior we want.
- **Phase 40 (indefinitely deferred) — cascade scoring:** mechanism 5. Cross-game state model; sequential-game harness; persisted state across games. Whole new harness shape. Wait for a real use case (tournament play, reputation experiments).

### Pressure mechanisms

1. **Round-cost decay** — every round without a deal subtracts points from
   everyone. Models lawyer fees in divorce, status quo costs in trade disputes.
   Builds urgency without explicit endgame talk. **Phase 38 (closed).**
2. **Exogenous events per round** — e.g. "Round 3: drought reduces water
   supply 30%" — recomputes BATNAs mid-game and forces position revision.
   Inject as moderator round-update messages between rounds (existing
   `round_updates` mechanism in `RoundSteppedFlow`). **Phase 39 (deferred).**
3. **Asymmetric clocks** — one faction has a hard deadline (election, market
   close, covenant expiring); others can wait. Creates structural urgency for
   one player only. **Phase 38 (closed).**
4. **Penalty floor below BATNA** — "no deal" doesn't equal BATNA; it equals
   BATNA *minus* a regret cost (reputation, sunk fees). **Phase 38 (closed).**
5. **Cascade scoring** — points awarded not on the deal itself but on what
   the deal *enables* in a later phase. **Phase 40 (indefinitely deferred).**

### Endgame clarity

Run 7 confirmed FINAL ROUND markers work. To strengthen: have the marker
show *current vs threatened* score concretely.

Example: `Round 4: no deal = 11 points (your BATNA). Current best offer
on table = 14 points. Walking away costs you 3 points.`

That's loss aversion made explicit.

### TODOs (rolled into Phase 38; closed 2026-06-11 unless noted)

- [x] Extend scenario schema + compiler to carry the small-bundle pressure fields. Add to `PERSONA_TEMPLATE` and `build_round_context`. [Phase 38]
- [x] Build `verify_scenario_pressure.py` alongside `verify_scenario_optimum.py`
      that confirms BATNAs are under pressure — e.g. "by round 3, expected
      scores at BATNA fall by ≥X%." [Phase 38]
- [x] Add "pressure profile" metadata to each scenario: low/med/high time
      pressure, low/med/high external shock, etc. [Phase 38]
- [x] Strengthen FINAL ROUND marker: include current best on-table score and
      delta vs BATNA. [Phase 38]
- [ ] **Design and run a divorce scenario.** Natural showcase for the
      small-bundle pressure mechanisms (round-cost decay = lawyer fees;
      asymmetric BATNAs = one party has exit option; penalty floor below
      BATNA = reputation cost of acrimony). Operator-driven design work
      after Phase 38 closes:
  - Shared assets (house, savings, business) — divisible
  - Indivisible goods (kids — joint custody is real Pareto territory)
  - Ongoing relationship — cost of acrimony is real
  - Lawyer fees scale linearly with time → built-in round decay
  - External pressure (kids' school year, mortgage due) — needs Phase 39 if dynamic; otherwise hand-author as initial conditions
  - Multiple game modes embedded: zero-sum on money, integrative on
    parenting, mixed on the house
- [ ] **Pareto-frontier annotation in analyst output.** Schema change build;
      prompt change needs Layer 2 supervised validation. Add a "compromise
      opportunities" field that enumerates deals beating all known BATNAs.
      Currently the analyst identifies leverage and threats; this would surface
      the Pareto-optimal deals explicitly. Independent of Phase 38; could be its own small phase.

---

## 2.5. `[B]` Strategy routing

Treat as a separate experimental axis from scenario design. Build a small
strategy library, A/B test per-faction.

### Candidate strategies

| Strategy | Persona instruction sketch |
|---|---|
| **Hardball anchor** | Open extreme, concede in tiny increments, walk-away threat at round 3 |
| **Integrative seeker** | Open with information exchange, propose multi-issue trades, focus on Pareto frontier |
| **Sequential concession** | Match every opponent concession 1:1; if they don't concede, hold |
| **Tit-for-tat** | Mirror previous round's opponent behavior on cooperation/defection |
| **Reputation builder** | Make small early commitments, keep them visibly, leverage trust late |
| **Coalition pivoter** | Propose A+B early, switch to A+C if B holds out, then ABC at endgame |
| **Information broker** | Stay neutral on positions; trade intel for concessions |

### TODOs

- [ ] Create `config/personas/strategies/` directory with one template per
      strategy above.
- [ ] Extend scenario compiler to allow strategy selection per faction
      (orthogonal to scoring/BATNA, which stays scenario-driven).
- [ ] Run scenarios × strategies × providers matrix. Cells: 4 scenarios × 7
      strategies × 3 providers = lots; pick targeted cells per run.
- [ ] **Real-game value:** the operator should be able to pick a strategy
      mid-game (`WATCH: Beta playing tit-for-tat. Recommend integrative-seeker
      for us.`) and have the prompt machinery execute it immediately.

---

## 3. `[A]` Conversation model evolution (multi-pass / async)

> **Deprioritized 2026-06-02.** Stage 2a (K=2 open+react) was originally
> Tier 1 as a prerequisite for §2 pressure mechanisms. On review, pressure
> mechanisms work fine with extra rounds on the current Stage 1 sealed-bid
> model — the "pass" vs "round" distinction doesn't produce meaningfully
> different agent behavior. The full conversation model migration is
> interesting but not blocking anything. Pursue when a use case demands
> within-round reactivity or timing-as-strategy.

`ARCH_conversation_model.md` maps the staged migration:

1. **Stage 1 (current)** — each faction generates once per round, sealed-bid
   style. No within-round reactivity. All Runs 1–10 used this model.
2. **Stage 2a (K-pass rounds)** — every agent generates K times per round
   with intermediate broadcasts. K=2 = open+react. Doubles cost per round.
   Functionally similar to running 2× rounds with adjusted endgame markers.
3. **Stage 2b (K=N until convergence)** — agents keep responding until no
   new commitments are made or N caps it. First stage with genuinely new
   behavior — agents stop talking when they have nothing to add.
4. **Stage 3 (true async)** — agents decide *when* to speak. Silence
   becomes a strategic signal. Timing matters. Novel research territory.

### When to revisit

- If Stage 1 runs show agents talking past each other in ways that more
  rounds can't fix (not seen in Runs 1–10).
- If a real-game moderator wants within-round reaction dynamics.
- If async timing-as-strategy becomes a research goal.

### TODOs (deferred)

- [ ] Stage 2a: add `MultiPassMode` to `RoundSteppedFlow`; K configurable.
- [ ] Stage 2b: convergence detection (no new commitments for N passes, or LLM-judged).
- [ ] Stage 3: generation schema emits `next_response_delay`; timing as strategy.
- [ ] Update scenario compiler to produce round-events tables if multi-pass is used.

---

## 4. `[X]` Coaching test loop on Pi

**Status 2026-06-07:** Three iterations done. First coached game (2026-06-03) surfaced 4 UX bugs (§4a-§4d), all closed via Phase 31 + Phase 32 + a prompt change. Run 13 (2026-06-04) validated the new gate end-to-end on all-Gemini-flash Water Rights symmetric — gate, transport, chunking, lazy-fetch, commands-during-review all worked. **But operator chose approve-only across all 4 rounds, so the edit path is still untested in a live run** and the feedback loop (classify edits → feed patterns into faction_prompt) has zero data. Phase 33 closed 2026-06-07 — ships `/revise: <directive>` LLM-rewrite edit mode + auto-classifier for the edit log. **Run 13b** (live re-run exercising the new edit modes; renamed from "Run 14" to free that number for the §10 ablation series) is the immediate post-phase test.

**What happened on the first coached game (2026-06-03, pre-Phase 31):** Operator coached beta faction via Telegram on Water Rights symmetric (all-Anthropic). Beta spoke in Round 1, then R2-R4 drafts hit Telegram's 4096-char message limit and failed silently. Beta was muted for 75% of the game. Alpha and Gamma negotiated around the silence and converged on a deal that happened to include beta. Operator rubber-stamped the R1 draft because they had no visibility into what other factions were saying.

### UX fixes needed (priority order, all 🔨 PURE BUILD)

- [x] **4a. TG 4096 char limit.** Closed Phase 31 (2026-06-04). `OperatorReviewGate` chunks messages at `max_message_chars=4000` via `chunk_text()` with `[continued ...]` markers. Note: command-response sends had the same bug class — fixed cleanly by Phase 32 (toolkit-level auto-chunking).
- [x] **4b. Transcript visibility / operator commands during review.** Closed Phase 31 (2026-06-04). `Pipeline.dispatch_operator()` routes commands through `review_gate.handle_command()` first; `/state`, `/status`, `/divergences`, `/ledger` work during pending review. `/reasoning` and `/adversarial` lazy-fetch deeper context on demand. `/intel` was silently dropped due to the chunking-bug-class (fixed by Phase 32.1–32.3), and Phase 32.5 now trims `/intel` to the latest round only.
- [x] **4c. Verbose generation responses.** Closed 2026-06-04 (prompt change). Conciseness instruction added to `config/prompts/generation.txt`.
- [x] **4d. Re-run coached game after UX fixes.** Satisfied by Run 13 (2026-06-04) — all-Gemini-flash Water Rights symmetric, β coached. Game completed 4 rounds; gate validated end-to-end (chunking surface present, lazy fetch works, commands-during-review works for everything except `/intel` which was the chunking-bug-class). The narrower follow-ups shipped in Phase 32: queue-drain on listener startup (R1 staleness, 32.4) and `/intel` trim to latest round only (32.5). Operator chose approve-only — edit-classification per `diplomat-testing-doc.md` §7.3 was therefore not exercised; revisit if a future coached run involves real edits.
- [x] **4e. `/revise: <directive>` LLM-rewrite edit mode + auto-classifier for the edit log.** **Closed Phase 33 (2026-06-07).** (a) `/revise: <directive>` added to `OperatorReviewGate` — operator gives intent, model regenerates draft in-place using full `DecisionContext`, capped at 3 iterations per pending review, directive chain stored as JSON array in `review_gate_edits.revise_directives`. (b) `LLMEditClassifier` + `edit_classifications` table + `tools/classify_edit_log.py` CLI + `/edits-summary` operator command auto-categorize every `action='edited'` row into the six §7.3 categories. See `DEVPLAN.md` Phase 33 plan (collapsed at close) for full design decisions.
- [ ] **4f. Operator command response UX (`/ledger` info-density, `/intel-history` for full history).** Operator notes 2026-06-04 (Run 13): `/ledger` "works but it's not very informative" — currently returns only `{per_round_budget, session_budget, available_budget, current_round}`. Improvement ideas: add per-call counts since last query, current-round spend, top 3 most expensive calls, cost-per-faction breakdown. Related: after Phase 32 trims `/intel` to latest round only, may want an `/intel-history` companion command for the full archive (defer until operator asks for it — most-recent-only is the more useful default). Both are pure-UX polish; no urgency. Out of scope for Phase 33.

### What the first session confirmed

- Review gate wiring works end-to-end (bot DMs draft, operator approves, bot posts to group)
- Coaching tags and `/approve`/`/edit`/`/block` commands are functional
- The harness survives a muted faction gracefully (no crashes, deal still reached)
- `coached_game.py` dry-run + live both work (after `sys.path` fix for `src/`)

### Original TODOs (updated)

- [x] Build `coached_game.py` (Phase 28)
- [x] Test scenario: Water Rights symmetric, all-Anthropic (2026-06-03)
- [x] Run on Pi (incus container, `.venv/bin/python3`)
- [ ] **After Phase 33 ships: Run 13b — coached game exercising `/revise:` and `/edits-summary`.** (Queued — Phase 33 closed. Renumbered from "Run 14" 2026-06-07 to avoid collision with the Run 14a-14f ablation series in §10.) Goal is to validate the new edit modes end-to-end in a live game and produce the first non-trivial `review_gate_edits` log with `revise_directives` populated and `edit_classifications` populated. Suggested config: Water Rights symmetric (matches Run 13 baseline so edit signal isn't confounded by other variables), all-Gemini-flash or mixed providers per latest tuning. Cost: ~$0.50-1.00 for the game + ~$0.05 for classification. Per `RUN_PROTOCOL.md`.
- [ ] **After Run 13b: inspect edit log, classify edits, feed patterns back into `config/faction_prompt.txt`.** This is the actual feedback loop closing — recurring `constraint_enforcement` or `persona_correction` patterns become prompt edits per `ARCH_coaching.md` §"Review Gate Edit Log → Prompt Refinement". Phase 33 surfaces the patterns; this step does the prompt work.

---

## 5. `[X]` Game-platform exploration (Clankmates / Discord / fallback)

**Status 2026-06-11.** Clankmates is no longer purely theoretical —
toolkit-side `clankmates_client` is the active primitive (`CLANKMATES_CLIENT_PLAN.md`).
Diplomat-side `ClankmatesTransport` is gated on that toolkit primitive landing.
Discord remains a hedge candidate, untouched.

Until the toolkit primitive is ready, this section stays exploratory — the
diplomat-side `ClankmatesTransport` would be a thin adapter on top of
`toolkit.clankmates_client`, similar to how `TelegramBotTransport` wraps
`toolkit.telegram_client`.

### Why this is on the backlog rather than queued

The game-traffic surface (where factions post to each other) needs to be
*something*. Telegram has been ruled out for game traffic because it doesn't
deliver bot-to-bot messages in groups regardless of privacy mode (see
"Telegram-platform finding" in Backlog). Telegram stays as the operator
coaching + review-gate surface.

### Clankmates — primary candidate (blocked on third party)

Three angles to weigh:

1. **Forcing function** — building `ClankmatesTransport` before the platform
   ships is a credible signal to that team.
2. **Risk** — polling-based with unknown API stability; could be wasted
   effort if the interface changes pre-launch.
3. **Hedge** — build a thin Transport interface adapter, mock against
   *expected* API shape, verify against real API when available.

Reference: `for-clankers.md` documents the expected interface (browser for
human, CLI/API for the agent, inbox screening pattern).

### Discord — parallel hedge candidate (no partner dependency)

**Why consider Discord:**

- Public, stable Bot API (REST + WebSocket Gateway, versioned and well-documented).
- Standard webhook + slash-command patterns.
- Channels + threads map cleanly to public game channel + faction-pair DMs / private threads.
- Large bot ecosystem; mature Python libraries (`discord.py`, `hikari`).
- No partner dependency — we can prototype and test entirely on a private server.
- Bots can DM each other (unlike Telegram), so faction-to-faction private
  channels work natively.

**Pre-conditions before building:**

- Operator commits to Discord as either primary or hedge target.
- Game moderator agrees to host the game in a Discord server (or operator
  controls a server for testing).

**Effort estimate if greenlit:**

- `DiscordTransport` similar shape to `TelegramBotTransport`. Choose `discord.py`
  (most popular, well-maintained) or `hikari` (modern, type-hinted, more
  performant). Both have stable enough APIs that the choice is taste.
- ~2-3 day build for a transport equivalent in capability to
  `TelegramBotTransport`.
- Phase 22 Pipeline/Flow split means it's additive — new Transport
  implementation, no orchestrator/pipeline changes.

### Fallback patterns if both Clankmates and Discord stall

- **CLI transport for testing** — already exists (`CLITransport`); good for
  solo demos but no multi-party negotiation.
- **Bring-your-own-server** — Telegram with non-bot accounts (Telethon) on a
  private group. Sidesteps the bot-to-bot restriction.
- **Matrix.org bridge** — federated, self-hostable, supports bots without
  group restrictions. More setup overhead than Discord.

### TODOs (gated on platform decision)

- [ ] Operator alignment with partners on platform choice (or decision to
      hedge across both).
- [ ] If Clankmates greenlit: docs/API discovery → build `ClankmatesTransport`
      against the real API. If undocumented at the time: build
      `ClankmatesMockTransport` against `for-clankers.md` expectations + thin
      adapter for swap-in later.
- [ ] If Discord greenlit: API survey → library choice (`discord.py` vs
      `hikari`) → build `DiscordTransport`. Set up a test Discord server with
      a public channel + faction threads.
- [ ] Either way: `HybridFlow` combining game-platform transport with
      Telegram for operator coaching + review gate (already in PROJECT.md as
      design intent). With Phase 22, this lands as a new `Flow` driving one
      `Pipeline` per agent with two transports — additive, not a fork.

---

## 6. `[X][C]` Pricing & accounting audit (cross-provider)

**Scope:** Audit `toolkit.cost_accountant` pricing accuracy across all providers
and models we actually use. Tally observed spend vs predicted spend across
the Run 1–10 archive to find drift.

**Known gaps:**
- Gemini 2.5 thinking-token billing not modeled (becomes relevant when we promote flash/pro)
- Anthropic cache-hit / cache-write pricing not modeled
- Per-call vs per-session vs per-round budget reconciliation has been fragile (multiple Phase 18 fixes)
- Dated-suffix normalization shipped Phase 19; further drift may exist for non-OpenAI/non-Anthropic providers

**Approach (rough):**
1. Pull `data/cost_ledger.jsonl` + `data/selfplay_cost_ledger.jsonl` across all runs
2. Cross-reference against the provider dashboards (OpenAI, Anthropic, Google billing) for the same date ranges
3. Identify drift > 20% per model/provider
4. Update `toolkit/cost_accountant/types.py` pricing table:
   - Add Gemini 2.5 thinking-token line items
   - Add Anthropic cache pricing if we start using it
5. Re-validate against a fresh self-play run

**Why not now:** Not blocking tuning work; cost is small enough at flash-lite scale
that 2× drift on $0.005/game is invisible. Best done in a dedicated session
when we want clean accounting for a budget claim.

---

## 7. `[B]` Per-role model strategy (cross-provider, with guardrails experiments)

**Scope:** Systematically decide which model goes in which module slot
(Generator / Primary Analyst / Secondary Analyst / Adversarial / Extractor /
Reconciliation) across providers. Not Google-specific.

**Operator hypothesis:** *Strong guardrails could let us use lighter models in some slots.* If the structured_call retry loop is robust and the schema validation catches drift, a cheap model that occasionally produces bad JSON but always recovers might be functionally equivalent to an expensive model that produces good JSON first try — at 1/10th the cost.

**Hypothesis to test:** Replacing the Extractor (currently the most
schema-disciplined slot) with `gpt-4.1-mini` or `gemini-2.5-flash-lite` (vs
the full-strength `gpt-5.5` or `claude-sonnet`) produces no measurable
decrease in promise/coalition tracking accuracy.

**Approach (rough):**
1. Define per-slot "minimum viable" quality criteria. For extraction: % of
   clearly-tracked promises captured. For analyst: presence of leverage
   points, threat-level accuracy. For adversarial: actionable critiques.
2. Run the same scenario (e.g. Water Rights or Trade Summit) with full-strength
   models for all slots as baseline.
3. Substitute one slot at a time with a lighter model; compare to baseline.
4. Build a per-slot recommendation table (lives in TUNING.md §1 once concluded).
5. Investigate whether `structured_call`'s retry-on-validation-failure loop
   is robust enough that schema enforcement actually catches lighter-model drift.

**Specific open question carried from Google work:** Should Generator use
`gemini-2.5-flash` or `pro` for stronger reasoning while Extraction /
Analyst / Adversarial stay on `flash-lite`? Same question applies cross-provider.

**Update 2026-06-01 (Run 10):** A new dimension has emerged that wasn't in the
original framing — *cross-round consistency*. Run 10 B' showed Anthropic
claude-haiku-4-5 honoring an R3 contingent commitment that OpenAI gpt-4.1-mini
defected from in Run 9 α-squeezed (and again in Run 10 C' on a different
faction). For multi-round negotiations, the per-slot decision now has two axes:
(a) **per-round quality** — fluency, schema discipline, reasoning depth — and
(b) **across-round consistency** — does the model honor its own prior
commitments when the contingency is met? Run 10 suggests consistency is at
least as important as quality for Generator seats on multi-round games.

The §7 experimental program should now factor consistency as a primary axis,
not just cost-vs-quality. See §1.7 / §1.8 for the cross-scenario tests that
would generalize the Run 10 finding.

**Why not now:** Best done after pricing audit (§6) so cost savings can be
quantified precisely. Cross-provider consistency tests (§1.7.a all-Anthropic
baseline, §1.8 cross-scenario) are higher-leverage and cheaper to run first.

---

## 8. `[C]` Reverse scenario builder — evolution (Phase 37 / 41 / 42)

**Status (2026-06-11).** Phase 35 shipped the tool; Phase 36 added soft-weighted fitness + simulated annealing + biased init; **Phase 37 complete** (`pareto_outcome_diversity` metric); **Phase 38 closed** (pressure mechanisms, see §2), Phase 41 (scale-matrix verification), Phase 42 (algorithm fixes from Phase 41 findings) are the queued continuation. Canonical implementation: `src/scenario_authoring/scenario_builder.py`, `src/scenario_authoring/scenario_spec.py`, `src/scenario_authoring/scenario_fitness.py`. CLI flags: `CLI_REFERENCE.md` `scenario_authoring.scenario_builder`. Conceptual overview: `ASSESSMENT.md` §4.5. First operator spec: `scenarios/joint_space_mission_v1/spec.json` (converges in ~4 seconds, produces 3 distinct Pareto deals + 2 logrolling-quality deals).

### Phase 37 — `pareto_outcome_diversity` (in progress)

Closes the metric-semantics gap surfaced during Phase 36.5 validation. The existing `pareto_distribution_spread` measures per-faction frontier-range stdev (uniformity), not "Pareto deals favor different factions" as the spec author intended. Phase 37 adds the latter as a separate target. Both metrics stay; CLI docs gain explicit "this measures X, not Y" guidance to prevent future misreads. Plan in `DEVPLAN.md` Phase 37.

### Phase 41 — scale-matrix verification (queued, cheap instrumentation)

Validated at 3×3×3 (27-deal space). 4+ factions / 4+ issues / 4+ outcomes-per-issue may need search-algorithm work — currently unmeasured. Phase 41 writes a `tools/scenario_builder_scale_probe.py` (or pytest parametrize) that runs the builder against a fixed simple spec at each shape (3×3×3, 3×3×4, 3×4×4, 4×3×3, 4×4×4, 5×3×3, etc.) and reports convergence rate + wall-clock + per-target distance breakdown when it fails. ~4-5 steps; no algorithmic changes. Reveals which shapes are feasible empirically.

Combinatorial reference (per `ASSESSMENT.md` §4.5 + the operator-side discussion 2026-06-11):

| Shape | Deals | Cells | Current-algo est. time per restart |
|---|---|---|---|
| 3×3×3 | 27 | 27 | ~0.2s (validated) |
| 4×4×4 | 256 | 64 | ~6-10s (predicted) |
| 5×5×5 | 3125 | 125 | minutes (likely untenable) |

### Phase 42 — algorithm fixes for shapes Phase 41 reveals as broken (queued, conditional)

Scope determined by Phase 41 findings. Likely candidates:

| Symptom | Probable fix |
|---|---|
| Fitness eval too slow at 4×4×4+ | Cached per-cell fitness deltas (only recompute changed sub-trees) |
| Hill-climb stuck in local minima | Multi-cell flips, larger neighborhood per move |
| Annealing schedule miscalibrated | Adaptive temperature based on observed acceptance rate |
| Random init too far from feasible at larger scale | LLM-guided proposal (`structured_call` from spec text; deferred from Phase 36) |
| Spec genuinely hard at scale | Operator-side: loosen targets or accept range knobs for more fields |

### Strategic value of Phase 41/42

Note 1 (`RESEARCH_NOTES.md`) predicts harness contribution grows with scenario complexity along five axes — *context exhaustion* (more issues) and *relationship complexity* (more factions) are exactly what Phase 41/42 unlocks. Validating the builder at larger scales is the prerequisite for the next round of bare-vs-full ablation experiments (the Run 14 successor that tests Note 1's thesis with richer scenarios).

### Out of scope for this section

- **Pressure mechanisms** — see §2 (Phase 38 closed / Phase 39 deferred / Phase 40 deferred).
- **LLM narrative wrap** — closed 2026-06-11: use `scenario_authoring.scenario_compiler --fill-narrative-only <analysis.json>` over the builder's emitted scoring tables to fill `logrolling` + `deception_tactics`; hand-author also works.
- **Cascade scoring** — needs cross-game state (Phase 40, indefinitely deferred).

---

## 10. `[A][X]` Ablation: bare-prompt vs full-harness

**Origin.** Operator question 2026-06-07: "How much of the good decision-making is the provider/model, and how much is the harness? Can weak models with strong harness outperform strong models without one?" Frames the foundational design-bet question for Diplomat: 33 phases of harness work assume the harness is load-bearing. If a bare-prompt agent (Persona + raw transcript + Generation only) performs comparably, the design bet hasn't paid off and the project should pivot.

**Build status.** Phase 34 closed 2026-06-08. Bare-mode plumbing shipped (commits `ca7e3bb` through `63d04cd`): `bare_module_overrides()` helper in `tests/self_play/bare_mode.py` produces no-op stand-ins for Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching; `DefaultContextAssembler.assemble(bare_mode=True)` strips intelligence/divergences/coaching from the assembled context; `run_simulation.py --bare-prompt` wires the flag end-to-end. Smoke (Step 34.4): bare live run cost ~$0.02 vs $1 projected (12 GEN-only calls; no EXT/ANALYST/ADV/RECON). 414 tests passing. Production live-game path untouched. Ready for Run 14a-14f.

**Experimental matrix (locked 2026-06-08 — 18 runs, single scenario):**

| Model tier | Model | $/MTok in/out | Full harness | Bare prompt |
|---|---|---|---|---|
| Weak | `gpt-4.1-nano` | $0.10 / $0.40 | 3 runs | 3 runs |
| Mid | `gpt-5.4-mini` | $0.75 / $4.50 | 3 runs | 3 runs |
| Strong | `claude-sonnet-4-6` | $3 / $15 | 3 runs | 3 runs |

3 tiers × 2 modes × **1 scenario** (Water Rights β-squeezed) × 3 runs = **18 runs**. Total cost estimate: **~$20-40**, dominated entirely by claude-sonnet-4-6 full-mode (cells 14e). All bare cells together < $1.

**Why this design (locked 2026-06-08):**
- **3 tiers** spread across providers (OpenAI weak + mid, Anthropic strong) provides real tier separation needed for the "harness substitutes for model tier" test. Pinned models confirmed: `gpt-5.4-mini` matches the worker-loop's codex pin; `claude-sonnet-4-6` is the production-target quality tier (true strong, not the haiku self-play default which would be tier-equivalent to mid).
- **Single scenario: Water Rights β-squeezed.** Historical 2-of-2 Pareto-deal rate (Run 9 β-squeezed all-OpenAI; Run 10 B' α-squeezed+Anthropic-on-β) — the right "leeway" zone where skill / harness can plausibly affect outcomes. Symmetric / α-squeezed / dual-squeeze all sit at no-deal floor; γ-squeezed is untested at scale. β-squeezed gives signal-to-noise. Trade Summit was originally on the matrix but the scenario file isn't in the repo (only the run5 results JSON exists). Scenario breadth deferred to v1.5 if first results are interesting.
- **3 runs/cell** for noise margin given Diplomat's observed run-to-run variance.
- **All-bare game vs all-full game** (not per-faction mixed) — three bare agents play three bare agents on the same scenario; three full play three full. Isolates the harness effect with no confound from "bare faction competing against full opponents who have analyst intelligence about it."
- **Metric:** `negotiated_surplus_share` (per ASSESSMENT.md §3.2). Range `[0, 1.0]`: 0.0 = no-deal floor, 1.0 = deterministic Pareto optimum. Already implemented and stored per-run. Cross-validate with `skill_premium_vs_batna` (§3.3) and the §3.4 process signatures.

**Run sequencing (cheap cells first, sonnet-full last):**

| Order | Run | Cell | Cost | Status |
|---|---|---|---|---|
| 1 | 14a | gpt-5.4-mini, full (3) | ~$3-4 actual | ✓ **Done.** 2/3 deals, mean δ +12.7, identical Pareto when closing. |
| 2 | 14b | gpt-5.4-mini, bare (3) | ~$0.50 actual | ✓ **Done.** 1/3 deals, same Pareto when closing. |
| 3 | 14c | gpt-4.1-nano, full + bare (3+3) | ~$0.30 actual | ✓ **Done.** Full 2/3, bare 0/3. Strongest harness lift in the campaign so far. |
| 4 | 14d | claude-sonnet-4-6, bare (3) | ~$0.50 actual | ✓ **Done 2026-06-11.** **0/3 deals — every run at BATNA floor.** Hits the "≤1/3 → fire 14e" conditional row exactly. Strong-model-bare is no better than weak-bare; model strength does NOT substitute for harness here. Strong support for Note 1 thesis. |
| 5 | 14e | claude-sonnet-4-6, full (3) | ~$2 actual | ✓ **Done 2026-06-11.** **0/3 deals — every run at BATNA floor.** Sonnet+full = sonnet+bare. The surprise finding: sonnet+full is *worse* than nano+full and mid+full (both 2/3). Harness composes well with OpenAI Generators but not with Anthropic's sonnet on this scenario — fail mode is non-convergence at the final round (vs silence in bare). Cost much lower than initial $15-30 estimate because only Generator was sonnet; harness modules defaulted to openai-mini commodity tier. |

**Cross-cell read (post-14e — campaign complete; canonical narrative in `TUNING_LOG.md` Run 14 campaign entry):**

| Tier | Model | Full close | Bare close | Δ |
|---|---|---|---|---|
| Weak | `gpt-4.1-nano` | 2/3 | 0/3 | +67% |
| Mid | `gpt-5.4-mini` | 2/3 | 1/3 | +33% |
| **Strong** | **`claude-sonnet-4-6`** | **0/3** | **0/3** | **0%** |

**Headline findings (post-14e — finding #3 added; all still caveated by `RESEARCH_NOTES.md` Note 1 scale-1 limitation):**

1. **Harness contribution is in close-rate, not deal quality.** Every closing run found the *identical* Pareto-optimal deal (alpha 16 / beta 18 / gamma 20, deltas `[+7, +3, +9]`). Scenario has one right answer; harness affects whether the model gets to it. (Unchanged.)
2. **Model strength does NOT substitute for harness on this scenario.** Bare close-rate is non-monotonic in model tier: weak 0/3, mid 1/3, strong 0/3. Sonnet-bare fails as completely as nano-bare.
3. **The harness has a model-class fit problem.** Sonnet+full = 0/3 — *worse* than weak+full and mid+full (both 2/3). The harness configuration works for OpenAI Generators but doesn't rescue Anthropic's sonnet, even with substantive engagement (27 promises tracked in 14e-1). Fail mode is non-convergence at the final round, not silence: agents stay anchored to their priority positions through R4.

Run-by-run sequencing per `RUN_PROTOCOL.md`: define inputs → verify scenario → probe providers → dry-run plumbing → live → verify output → document.

**Analysis tooling (new — small, written after the runs land):**

`tools/ablation_summary.py` — reads the 36+ run JSONs by `bare_mode` + `model` + `scenario` metadata fields and produces a comparison table: per-cell mean / std of `negotiated_surplus_share`, plus pairwise full-vs-bare deltas per (model, scenario). ~50 lines; no LLM cost.

**What the results imply for the project:**

| Pattern | Implication |
|---|---|
| Bare always loses to full at every tier | Harness load-bearing. Design bet validated. Keep building. |
| Bare ≈ full at strong-model tier; full > bare at weak/mid | Harness substitutes for model tier. Diplomat positions as "make cheap models good enough." |
| Bare ≈ full at all tiers | **Harness is theater.** Investment hasn't paid off. Pivot: drop the harness, or ablate per-module to find the *one* piece that helps. |
| Strong-bare > weak-full | "Pay for model, not infra" — same message as the row above, sharper. |
| Mixed by scenario | Follow-up phase to ablate per-module on the scenarios where harness wins, find which pieces are load-bearing. |

The third / fourth row is the uncomfortable outcome. **Better to learn it now than after Phase 50.**

### TODOs

- [x] **Phase 34 build** — Closed 2026-06-08. 6 steps: bare module set helper, bare context-assembler path, `--bare-prompt` flag, smoke validation (live cost ~$0.02 vs ~$1 projected — bare mode is ~10-20× cheaper), integration tests (414 passing), documentation. `tests/self_play/bare_mode.py` + `--bare-prompt` flag in `run_simulation.py`.
- [x] **Runs 14a-14e** — Closed 2026-06-11. WR-β only (scenario expansion folded into Run 16 below). 18 runs, ~$10 actual. Canonical narrative in `TUNING_LOG.md` Run 14 entry; cross-cell read above.
- [x] **Run 16** — Closed 2026-06-12. jsm1 ablation matrix: nano full + nano bare + mid bare + sonnet bare = 12 runs, ~$1.50 actual. Canonical narrative in `TUNING_LOG.md` Run 16 entry. See "Run 16 — jsm1 ablation matrix" subsection below.
- [ ] **`tools/ablation_summary.py`** — write after the run data accumulates (don't pre-build; the right shape will be obvious once we see real numbers). Now that 30 runs across 2 scenarios are landed, this is closer to "shape obvious enough" than when first noted; small future cleanup.
- [x] **Decision: project direction.** Reviewed 2026-06-12 after Run 16 close. **Result: harness load-bearing on cooperative-single-Pareto scenarios for weak/mid OpenAI Generators; harness redundant for sonnet on multi-Pareto.** Neither "always load-bearing" nor "theater" — scenario × tier dependent. **Project direction: continue building harness, but stop assuming uniform harness value across scenario shapes.** Specifically: (a) Phase 38 pressure mechanisms are now the highest-leverage Block C investment (per re-framed Note 1, pressure is the un-tried scenario-design lever); (b) per-module ablation (Phase 35 candidate) demoted — Run 16 shows sonnet's harness contribution is 0 on jsm1, so per-module decomposition wouldn't find a load-bearing piece; (c) richer-scenario validation (per `RESEARCH_NOTES.md` Note 1 amendment) requires Phase 41/42 first to enable 4+ faction / 4+ issue scenarios.

### Run 16 — jsm1 ablation matrix (2026-06-12)

Filled in the cells Run 14 had skipped (jsm1 wasn't on Run 14's matrix; Run 15 calibration covered mid+strong full only). Final jsm1 cells: nano full × 3, nano bare × 3, mid bare × 3, sonnet bare × 3. Cost ~$1.50, wall clock ~48 min.

**Cross-scenario synthesis (Runs 14 + 16 combined):**

| Tier | Model | WR-β full | WR-β bare | jsm1 full | jsm1 bare |
|---|---|---|---|---|---|
| Weak | gpt-4.1-nano | 2/3 | 0/3 | 1/3 (new) | 0/3 (new) |
| Mid | gpt-5.4-mini | 2/3 | 1/3 | 0/3 | 0/3 (new) |
| **Strong** | **claude-sonnet-4-6** | **0/3** | **0/3** | **3/3** | **3/3 (new)** |
| Strong | gpt-5.5 (OpenAI, temp=1) | — | **3/3 (Run 18)** | — | **3/3 (Run 18)** |

> **Run 18 (2026-06-22) — provider confound broken.** gpt-5.5 (strong, OpenAI) closes WR-β bare 3/3 where sonnet (strong, Anthropic) floors 0/3 → the WR-β strong-tier failure was *sonnet-specific*, not a strong-tier property. gpt-5.5 full not run (bare ceilings 3/3 on both → no harness-lift headroom). Temp caveat: gpt-5.5 forced temp=1 vs matrix 0.7 (judged immaterial). See `TUNING_LOG.md` Run 18.

**Four findings (post-Run-16):**

1. **Sonnet's harness contribution is zero on jsm1.** sonnet-bare = sonnet-full = 3/3, identical deal every run, zero variance across all 6 sonnet jsm1 runs combined. **Partially refutes Note 1's "richness produces harness lift" thesis.** Re-stated thesis in `RESEARCH_NOTES.md` amendment: harness contribution = f(scenario shape, what model already does well).
2. **jsm1's balanced-consensus deal is a strong scenario attractor, not a harness anchoring effect.** Sonnet picks the same Pareto deal in both modes (6/6 identical). Hypothesis "the harness anchors sonnet on balanced-consensus" refuted.
3. **Mid-tier failure on jsm1 is harness-immune.** mid-bare = mid-full = 0/3. The "stuck-but-engaged" pattern (substantive 2/3-issue convergence, can't bridge the last issue) persists under bare mode — harness intel doesn't unstick mid. This sharpens the case for Phase 38 pressure as the next lever to try.
4. **Weak-tier harness lift is scenario-dependent.** +67% on WR-β vs +33% on jsm1. When nano closes on jsm1, it finds the identical balanced-consensus deal sonnet finds (same scores). Harness still load-bearing for weak tier; yield depends on scenario fit.

**Project-direction implications (folded into the decision row above):**

- Production-default recommendation now **scenario-dependent**, not uniform. WR-β shape → cheap+harness (nano-full ~$0.05/run, 2/3 close). jsm1 shape → strong+bare (sonnet-bare ~$0.30/run, 3/3 close).
- Per-module ablation demoted — sonnet-bare jsm1 = 3/3 with full module suite disabled, so no module is load-bearing for sonnet on jsm1; per-module decomposition would still only find weak/mid-tier-specific lifts.
- N4 (mid+Phase-38-pressure on jsm1) is now the sharpest residual experiment. Promoted to Tier 1 row above + carry-forward list below.

### Follow-up flavors (deferred — only if Run 14 + 16 results warrant)

- **Scale-up scenarios per `RESEARCH_NOTES.md` Note 1.** Build §8 reverse builder, then compile complexity-axis scenarios (Nash≠Pareto, multiple Pareto, long-horizon Water Rights, wide-Water-Rights, repeated-game, §2-pressured) and re-run the 18-run matrix on each. Tests whether harness contribution grows with scenario complexity as the thesis predicts. ~$50-150 + Phase-35-sized build for §8.
- **Add second scenario** (Three-Party Coalition compile, OR new Trade Summit compile): doubles runs to 36. Justified if Water Rights β-squeezed v1 result is scenario-suspect.
- **Thorough flavor** (~$150-250, 81 runs): adds a "medium harness" mode (full minus adversarial + minus reconciliation) and a third scenario. Use only if v1 + scenario-add results are interesting AND we want to find the harness elbow.
- **Per-module ablation** (Phase 35 candidate): full minus extraction, full minus analyst, full minus reconciliation, etc. Use only if v1 shows mixed results that justify finding which pieces help.
- **Per-faction mixed-mode games**: one bare faction vs two full opponents (adversarial bare). Different question — measures "does harness help when other agents have it" rather than "does harness help in symmetric games." Deferred.

---

## 11. `[C][A]` Competitive scoring — making mixed-model runs produce winners

**Status:** Diagnosed 2026-06-12 mid-Run-17. Full discussion: `RESEARCH_NOTES.md` Note 2.

**The problem.** Current scoring + unanimity model rewards agreeableness, not adversarial-negotiation skill. When two good models negotiate alongside one bad model, the bad model's "block" punishes everyone equally (all fall to BATNA) rather than the two good models forming a coalition and beating the bad one. The "X model wins, Y model loses" outcome that mixed-model testing wants is structurally suppressed by:

1. **Unanimity requirement** — `score_game()` needs all factions to agree on every issue; any holdout kills the deal.
2. **BATNA-floor scoring** — discrete WIN/LOSE on BATNA-clear; "barely beat" and "extracted max" both register as WIN.
3. **Pareto-efficiency as group-level metric** — `negotiated_surplus_share` measures *whether the team* found joint value, not *who outperformed whom*.

All four ASSESSMENT §3 lenses compound this. Mixed-model populations (already supported via `--per-faction-providers` — every Run 14, 15, 16, 17 cell has used homogeneous populations by convention, not by harness limitation) would produce real signal only after one of three paths below lands.

**Three paths forward** (full detail in Note 2):

- **Path A — Run mixed-model on existing scenario, accept the unanimity limit.** Behavioral signal via transcripts (which model pairs recognize each other as competent partners; differential R4 positions). Real but weaker than "X wins, Y loses." Cheapest test (Three-Party Coalition compile + mixed + position rotation, ~$3-5).
- **Path B — Engineer coalition-exclusion scoring in the harness.** Extend `scenario_analysis.json` with `coalition_values: {AB: 118, AC: 84, ...}`; modify `score_game()` to detect partial-agreement coalitions and assign coalition value to the agreeing subset; assign BATNA to excluded faction. 1-2 day build. Unblocks proper competitive testing on coalition-coercive scenarios (Susskind-style). Promote to a real phase number when ready.
- **Path C — New scenario class that doesn't need harness changes.** Distributive bargaining (divide fixed pie), asymmetric-BATNA-with-walkaway, hidden-value bluff scenarios. Skill = "outperform on absolute score within unanimous deal" or "extract max surplus before walkaway." Designed with existing Phase 35-37 reverse builder + Phase 38 pressure mechanisms.

**Cheapest immediate test (when ready to act).** Path A, n=1 calibration first. Compile `three_party_coalition.md` (no `scenario_analysis.json` exists yet — Run 6/7 used live-compile, didn't commit) via `scenario_authoring.scenario_compiler --scenario three_party_coalition.md --output-dir scenarios/three_party_coalition_v1/` (~$0.01). Then run 9 cells (3 model permutations × 3 rotated positions × n=1) with `--per-faction-providers` set to a mixed population. ~$1-2 calibration, ~$3-5 if expanded to n=3.

**Open questions before committing to Path B or C** (per Note 2 "What would refute"):

1. Does Path A produce transcript differentiation rich enough that the rank-based scoring lens (Option B from Note 2 — ~50 LOC) is sufficient without coalition-exclusion scoring?
2. Does the compiler's mapping of Susskind narrative → standard issue/outcome schema preserve the coalition-coercive structure, or does it soften it into cooperative-flavored issues?
3. Does Path C scenario design produce rank-discriminating outcomes on the existing harness, making Path B optional?

**Two product directions this surfaces** (also detailed in Note 2):

- **Diplomat as operator coaching tool** (current PROJECT.md vision). Audience: human operator. Cooperative scoring is *correct* — real diplomacy rewards joint value.
- **Diplomat as model-evaluation harness.** Audience: researchers comparing models. Competitive scoring is *required* — rank-based outcomes on coalition-coercive / zero-sum scenarios.

Not mutually exclusive. Same infra, different scoring conventions, different scenario design priorities. Worth an explicit decision in `DECISIONS.md` before building Path B/C infra.

### TODOs (post-D-56 status — see closure tags)

- [x] **11.a Compile Three-Party Coalition once + commit.** **DONE 2026-06-12.** `scenario_authoring.scenario_compiler` produced `scenarios/three_party_coalition_v1/scenario_analysis.json` + per-faction personas. **Hand-patched 2026-06-12** to restore Susskind coalition-coercive structure (BATNAs `5/5/4`→`0/0/0`; excluded-faction scores `1/2/1`→`0`; ABC scores `8/7/8`→`7/7/7` for `sum=21` knife-edge above AB `sum=19`; pressure stripped for clean baseline). Verified via `verify_scenario_optimum.py`. Patch rationale documented in `scenarios/three_party_coalition_v1/NOTES.md`. **First consumer = Path B build (§3.6 coalition-value scoring engine).**
- [ ] **11.b Path A calibration — mixed-model Three-Party Coalition × position rotation × n=1.** Tier 1 under D-56. 3 model permutations (suggested post-Run-17: sonnet / gpt-5.4-mini / deepseek-v3) × 3 position rotations × n=1 = 9 cells. ~$1-2, ~30 min. **Gated on:** mixed-model dispatcher extension to `tools/ablation_multi.sh` (~1 hour build). Reads transcript differentiation in addition to scoring outcomes — under D-56 useful even without Path B since rank-based scoring (§3.5) gives meaningful results once it ships.
- [x] **11.c Decision: which path (B or C) to invest in.** **CLOSED by D-56 (2026-06-16).** D-56 chose **both** rather than picking one: Path B (coalition-exclusion scoring engine, §3.6) is a Tier 1 build; Path C (adversarial-scoring scenario class — distributive / asymmetric-BATNA / hidden-value) is a Tier 1 scenario-authoring track. Original framing assumed parallel pursuit was wasteful; benchmark-direction reframe makes both load-bearing for different scenario classes.
- [x] **11.d Promote chosen path to a phase.** **DONE via D-56.** Path B is queued as a Tier 1 build (no phase number assigned yet — next phase number is the natural slot). Path C is queued as scenario-authoring work (not a single phase — runs as operator-driven authoring per scenario class). Phase assignment per ASSESSMENT §5 Block C active items + NEXT_STEPS Tier 1 entries.
- [x] **11.e Rank-based scoring lens (Option B from Note 2).** **PROMOTED to ASSESSMENT §3.5 as a queued lens; Tier 1 build under D-56.** ~50 LOC scope unchanged. Implementation specifics live in ASSESSMENT §3.5 + Tier 1 row.
- [ ] **11.f Tournament harness (Option D from Note 2).** Still deferred under D-56. Tied to Phase 40 (cascade scoring, indefinitely deferred). Promote when (a) Path B + §3.5 lens both ship + (b) a benchmark campaign explicitly needs multi-game round-robin with cross-game state. Per ASSESSMENT §5 Block C "tournament-style benchmark cells are demanded" trigger.

### Connection to other sections

- **§5 game-platform exploration** — competitive scoring is orthogonal to platform choice. Clankmates/Discord transport carries whatever scoring convention we pick.
- **§7 per-role model strategy** — mixed-model runs *are* the natural per-role experimental setup. Section §7's question ("which model per slot?") gains a competitive-tournament answer mode once §11 lands.
- **§10 ablation** — bare-mode + mixed-model + competitive scoring would produce a 3-axis matrix; potentially the most informative single campaign Diplomat could run. Not prioritized until at least Path A signal is in hand.
- **`ASSESSMENT.md` §3 scoring lenses** — Path B / Option B add §3.5 (rank-based) and §3.6 (coalition-value) lenses. Worth updating §3.5 cross-reference table when those land.

---

## Backlog — still-open items

### `coalition_formation` synthetic issue redundancy (Phase 2b candidate)

After Phase 2a landed `coalition_values` as a first-class field on
`scenario_analysis.json`, the synthetic `coalition_formation` issue in
`scenarios/three_party_coalition_v1/` (with outcomes a_b, a_c, b_c, a_b_c
and per-faction scoring tables encoding the same payoffs that
`coalition_values` now expresses) is **partially redundant** but NOT cleanly
removable. The issue is still what agents negotiate over (the schema
requires `issues` non-empty; the outcomes give agents a vocabulary).

- [ ] **Rationalize coalition-coercive scenario representation.** When
      Phase 2b reworks the agents-vs-engine semantics for partial-coalition
      detection, decide whether the synthetic issue stays as-is (current
      shape, slightly redundant), simplifies (only ABC outcome scored
      explicitly; partial coalitions purely via `coalition_values`), or is
      replaced by a different agent-facing surface entirely. Out of scope
      for Phase 3 cleanup pass — this is a real design decision, not a
      mechanical refactor.

### Surplus distribution favors the un-pressured neutral-on-bottleneck faction

In both deal-reaching runs to date — Run 9 β-squeezed (deltas [+6, +3, +11])
and Run 10 B' (deltas [0, +10, +11]) — gamma extracted 52-55% of negotiated
surplus. Both times gamma was the faction with neutral position on the
bottleneck issue (Payment) and a moderate (un-squeezed) BATNA. Whether this
is a Water-Rights-specific characteristic or a general property of asymmetric
3-party negotiations is open.

- [ ] **Investigate surplus-distribution asymmetry.** Likely game-theoretic
      explanation: the neutral-on-bottleneck faction has credible "I'll go
      either way" leverage so extracts more in any deal that closes. If
      generally true, it's a scenario-design lever: route the faction you want
      to favor toward a neutral position on the bottleneck issue. Confirm via
      §1.7.a all-Anthropic baseline (does gamma still take 52-55% across BATNA
      variants?) and via Three-Party Coalition / Trade Summit scoring data.
- [ ] **Cross-scenario surplus-distribution data.** Currently 2-of-2 in Water
      Rights. Need at least one Pareto-reaching deal in Three-Party Coalition
      or Trade Summit to test generality.

### Why no agent proposed the Pareto-optimal deal (Run 8) — partially answered

Run 8's Pareto-optimal deals were on the Heavy-Downstream frontier (sum=54,
alpha=16/beta=18/gamma=20) and the Shared frontier (sum=51,
alpha=13/beta=17/gamma=21). No agent proposed either; everyone stayed at
extremes on Payment.

Runs 9-10 partially closed this:
- **Asymmetric BATNA squeeze on the right faction (β-squeezed)** produced the
  Heavy-Downstream Pareto deal in Run 9 — the "don't accept the first
  reasonable framework" persona rule is not the binding constraint when the
  squeezed faction can't afford to defect to BATNA.
- **Provider consistency on Anthropic (Run 10 B')** produced the same Pareto
  deal under unfavorable BATNAs — the OpenAI gpt-4.1-mini R3→R4 defection
  pattern was breaking commitment-following, not the persona rule.

Still open as a controlled A/B (lower priority post-Runs 9-10):

- [ ] **A/B test softened "don't accept first framework" rule.** Variant A:
      current persona. Variant B: "actively look for compromises that beat all
      BATNAs; propose at least one Pareto-improving alternative per round."
      Run on the symmetric (un-squeezed) configuration to isolate the persona
      variable. ~$0.60.
- [ ] **Pareto-frontier annotation in analyst output** (carried to §2 TODOs).
      Adds a "compromise opportunities" field that enumerates BATNA-clearing
      deals. May reduce the persona-rule load by surfacing the answer in the
      intelligence report.

### Reconciliation: live validation in real scenarios

Phase 20 added Layer 3 fake-LLM tests for all four reconciler paths (dedup,
fulfillment, inconsistency, missed-proposal). Status-transition (`pending →
kept/broken`) and inconsistency-flagging still need **live** validation in
a real self-play scenario, not just deterministic fixtures.

- [ ] **Status transitions live** — Run 10 B' reached a Pareto deal with
      reconciler logs showing position shifts (e.g. "Merged beta's promises on
      volume, payment, and infrastructure into beta-alpha-volume-payment-…").
      Worth inspecting whether any `pending → kept` transitions fired when the
      R4 deal closed. If not, the reconciler still doesn't detect fulfillment.
- [ ] **Inconsistency detection on Run 9 α-squeezed / Run 10 C' defections** —
      both are clean R3→R4 contradictions (beta R3 "Heavy-Downstream" → R4
      "Shared"; gamma R3 "Heavy-Downstream" → R4 "Shared"). Reconciler likely
      did not flag these. Worth a focused look at those run logs; if zero
      flags despite obvious contradictions, the reconciler prompt needs the
      strengthening called out in earlier sweeps (round-by-round position
      tracking, specific quantitative-claim watching).
- [ ] **Status transitions live (older)** — needs a scenario where at least one
      promise resolves mid-game (one-shot favor in early rounds that the
      receiving faction acknowledges). A staged scenario from §2 (divorce)
      is the natural venue if Run 10 inspection above doesn't suffice.

### Telegram-platform finding (worth knowing)

Telegram does **not** deliver bot-sent messages to other bots in groups
regardless of privacy mode. This is a hard-coded platform restriction.
If any future Telegram-side test needs simulated faction traffic, options
are (a) a second human Telegram account on another device, or (b) a temporary
de-op cycle (remove operator's user ID from `DIPLOMAT_OPERATOR_USER_IDS`,
restart, send game messages from operator's own account, then re-op). Not a
blocker for production since the game-traffic surface is Clankmates (§5),
not Telegram.

### Remaining decisions for production deployment

- [ ] Decide whether to flip `pipeline.yaml` `review_gate` to
      `TelegramReviewGate` as the new default, or keep `AutoApproveReviewGate`
      as the safe default with per-deploy override. The smoke ran on
      `pipeline_smoke.yaml` which already has `TelegramReviewGate`; production
      `pipeline.yaml` flip is a separate decision.

---

## Carry-Forward Items (from DEVPLAN + TUNING_LOG)

Tracked here for visibility; canonical sources remain authoritative.
Closed items have been moved to **Appendix A**.

- [ ] **Run 11 candidate — all-Anthropic baseline across 3 BATNA variants**
      (§1.7.a). Generalizes Run 10 B'. ~$3-4 spend.
- [ ] **Run 11 alternate / Run 12 — OpenAI defection cross-scenario test**
      (§1.8). Cheap (~$0.30). Tells us whether the gpt-4.1-mini R3→R4
      defection is Water-Rights-specific or general.
- [ ] **Run 13b — coached game exercising `/revise:` and `/edits-summary`**
      (§4 Original TODOs). Phase 33 closed 2026-06-07 — queued for operator-driven
      execution. Water Rights symmetric matches Run 13 baseline so edit signal
      isn't confounded; expected cost ~$0.50-1.00 + ~$0.05 classification.
      Produces the first non-trivial edit log with `revise_directives` populated
      and `edit_classifications` populated. (Renumbered from "Run 14"
      2026-06-07 to free that number for the ablation series in §10.)
- [x] **Runs 14a-14e — bare-prompt vs full-harness ablation matrix on Water Rights β-squeezed**
      (§10). Closed 2026-06-11. 18 runs, ~$10. Canonical narrative in
      `TUNING_LOG.md` Run 14 entry.
- [x] **Run 16 — bare-vs-full ablation matrix on jsm1**
      (§10). Closed 2026-06-12. 12 runs, ~$1.50. Note 1 partially refuted;
      revised harness-contribution framing in `RESEARCH_NOTES.md` amendment.
      Canonical narrative in `TUNING_LOG.md` Run 16 entry.
- [ ] **Run 17 candidate — N4 mid-tier + Phase 38 pressure × 3 on jsm1**
      (§10 / §2). Cleanest residual experiment after Run 16. Mid-tier is
      0/3 in both modes on jsm1 with substantive 2/3-issue convergence;
      Phase 38 round-cost decay is the un-tried lever. ~$1.50 + ~36 min.
      Tests "harness via scenario design" — if pressure unsticks mid-tier
      on jsm1, that's a clean win for Phase 38; if not, the mid-tier-stuck
      pattern is robust and Phase 38 has lower leverage than hoped.
- [ ] **Run 17 candidate (alternate) — N4b sonnet + Phase 38 pressure × 3 on WR-β**
      (§10). Carried from Run 14e follow-up. Tests strategic-refusal mechanism:
      if pressure converts sonnet 0/3 → 2-3/3 on WR-β, "BATNA-survivable
      coalition" mechanism wins; if no change, persona-rule weighting more
      likely. ~$2 + ~50 min.
- [ ] **Persona payment rigidity** — recurring across Runs 7-10. Run 9
      post-mortem partially deflated this: under squeeze, the rule isn't
      binding. Still worth an A/B in a future run (Tier 3 `[B]`).
- [ ] **Persona drift over 8+ rounds** — all runs were 4 rounds; longer
      games may show drift.
- [ ] **Provider-native structured output** — OpenAI `response_format:
      json_schema` would give token-level schema compliance. Requires toolkit
      `llm_client` parameter passthrough.
- [ ] **Persona endgame over-anchoring (Run 7)** — static `ENDGAME:`
      paragraph leaks into early rounds. Decide whether to soften, move to
      dynamic-only, or accept.

---

## Appendix A — Closed since 2026-05-30

Audit trail. Canonical detail in `DEVLOG.md` / `DEVLOG_archive.md` under the
corresponding phase or Phase 19 ad-hoc entries, and `TUNING_LOG.md` /
`TUNING_LOG_archive.md` for runs.

### Build phases (20-28)

| Item | Where | Status |
|---|---|---|
| Layer 3 integration tests for Phase 18 paths | Phase 20 | ✓ Closed 2026-05-31 |
| Reconciler dedup / fulfillment / inconsistency / missed-proposal (fake-LLM coverage) | Phase 20 | ✓ Closed 2026-05-31 |
| Module boundary cleanup — orchestration (public `advance_to_round`, `OrchestrationOptions`, `StubAnalyst` registry leak, logged reconciler exceptions) | Phase 21 | ✓ Closed 2026-05-31 |
| Module boundary cleanup — LLM adapter + config dedup (`_TaggedLLMClient` deleted, `attribution`/`purpose` kwargs threaded, `build_reconciler` + `subsystem_llm_config` factories, `DryRunLLMClient` `purpose`-kwarg classification) | Phase 21 | ✓ Closed 2026-05-31 |
| Pipeline / Flow split (`Pipeline`, `EventDrivenFlow`, `RoundSteppedFlow`; `Orchestrator` as compat factory; `ARCH_flow.md`) | Phase 22 | ✓ Closed 2026-05-31 |
| ASSESSMENT §3.2 Pareto efficiency scorer | Phase 23 | ✓ Closed 2026-05-31 |
| ASSESSMENT §3.4 process signatures (4 deterministic: broken-promise rate, coalition stability, time-to-deal, opening gap) | Phase 23 | ✓ Closed 2026-05-31 |
| Toolkit `OpenAIProvider.call` `max_completion_tokens` dispatch + unit tests + ARCH_llm_client + API.md | Phase 24.1 + operator-direct | ✓ Closed 2026-05-31 |
| Per-faction asymmetric `--batna-fractions` JSON flag | Phase 24.2 | ✓ Closed 2026-05-31 |
| `--force-batna-fraction` post-clamp option | Phase 24.3 | ✓ Closed 2026-05-31 |
| `--game-mode` runtime override flag | Phase 24.4 | ✓ Closed 2026-05-31 |
| Level 1 modularization — extraction examples → `config/examples/extraction_examples.json` | Phase 24.5 | ✓ Closed 2026-05-31 |
| Level 1 modularization — reconciliation + analysis derive entity types from `state_patch.json` schema | Phase 24.6 | ✓ Closed 2026-05-31 |
| Phase 24 doc updates (CLI_REFERENCE, TUNING, diplomat-testing-doc, ARCH_extraction, ARCH_reconciliation) | Phase 24.7 + operator-direct | ✓ Closed 2026-06-01 |
| `tools/service.sh` rewrite around `tmux new-window` | Phase 25 | ✓ Closed 2026-06-01 |
| Structured per-event logging in orchestrator + transport (`diplomat.*` namespace, `DIPLOMAT_LOG_LEVEL`, caplog tests) | Phase 26 | ✓ Closed 2026-06-01 |
| No-deal-aware scoring metrics (`negotiated_surplus_share`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, `faction_deltas`) + `tools/backfill_scoring_metrics.py` | Phase 27 | ✓ Closed 2026-06-01 |
| Coached self-play harness (`tests/self_play/coached_game.py` with `--coach-faction`, `--dry-run`, `DryRunTelegramReviewGate`, `module_overrides` injection) | Phase 28 | ✓ Closed 2026-06-02 |
| Near-miss + defection diagnostic (`compute_near_miss()` in `tests/self_play/analysis.py` — `near_miss`, `converging_factions`, `dissenting_faction`, `defection_event_log`) + fixture-backed tests on Run 9/10 scenarios | Phase 28 | ✓ Closed 2026-06-02 |

### Closed backlog items

| Item | Where | Status |
|---|---|---|
| ASSESSMENT §3.3 vs Naive baseline (equal-split scorer, BATNA-clearing, Nash bargaining) | Appendix A | ✓ Closed 2026-06-03 |

### Phase 19 ad-hoc (toolkit + tooling)

| Item | Where | Status |
|---|---|---|
| Toolkit `complete_with_retry` (exponential backoff on 429/5xx/empty) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Toolkit `normalize_model_name` + refreshed pricing (closed ~41× cost-ledger overestimate) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Scenario compiler BATNA fraction-of-max formula + `--batna-fraction` CLI + `validate_batna_pressure()` | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| LoggingLLMClient SCORE/RECON visibility | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Production reconciler wired in `src/main.py` (`_attach_reconciler`) | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| Optional `game.total_rounds` in `pipeline.yaml` | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `tools/inspect_ledger.py` rewritten with CLI args | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `CLI_REFERENCE.md` + `SMOKE_RUNBOOK.md` created | Phase 19 ad-hoc | ✓ Closed 2026-05-30 |
| `ASSESSMENT.md` created (skill framework + scoring lenses + workstream blocks) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |
| Live Telegram re-smoke (for coaching scope only — game-traffic is not a Telegram concern) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |
| WORKER_SPEC loop-discipline hardening (single-call contract, no self-judge budget) | Phase 19 ad-hoc | ✓ Closed 2026-05-31 |

### Experiments (TUNING_LOG)

| Item | Where | Status |
|---|---|---|
| Run 9 — Asymmetric BATNA pressure (Water Rights, 3 variants: symmetric / α-squeezed / β-squeezed). β-squeezed reached Pareto deal. `negotiated_surplus_share=1.05`. | TUNING_LOG Phase 8 | ✓ Closed 2026-06-01 |
| Run 10 — Asymmetric BATNA refinements (B' = α-squeezed + Anthropic on beta; C' = α+β dual-squeeze, all OpenAI). B' reached Pareto deal; C' did not. Confirmed OpenAI gpt-4.1-mini R3→R4 defection is provider-specific (2-of-2 instances). | TUNING_LOG Phase 9 | ✓ Closed 2026-06-01 |

### Re-scoped / rejected

| Item | Decision | Status |
|---|---|---|
| **Run 9 carry-forward** (original "rotated provider assignments") | Replanned 2026-06-01 to asymmetric BATNA pressure; partially absorbed into Run 10 B'. Full all-Anthropic rotation control still open as §1.7. | ✓ Closed (replanned) |
| **Partial-consensus scoring** (recurring Run 7/8/9 open item) | Rejected 2026-06-01. Operator: "no agreement = no agreement, doesn't matter if missed by an inch or a mile." Replaced by near-miss diagnostic in §1.9. | ✓ Closed (won't do) |
| **No-deal `pareto_efficiency` BATNA-height confound** | Closed by Phase 27. Metric `negotiated_surplus_share` reads 0.000 at floor regardless of BATNA height. | ✓ Closed (Phase 27) |
| **Scoring rule strictness — partial-deal scoring mode** | Closed 2026-06-01 alongside partial-consensus rejection. Replaced by near-miss diagnostic in §1.9. | ✓ Closed (won't do) |
| **Original Run 9 provider-rotation scope (residual)** | Run 10 B' addressed α-squeezed configuration with mixed providers. Full all-Anthropic rotation control re-opened as §1.7.a (Run 11 candidate). | ✓ Closed (re-tracked in §1.7) |

### Outstanding tooling debt (closed)

| Item | Where | Status |
|---|---|---|
| Rewrite `tools/service.sh` around `tmux new-window -t bot` | Phase 25 | ✓ Closed 2026-06-01 |
| Add structured per-event logging to orchestrator + transport | Phase 26 | ✓ Closed 2026-06-01 |

---

## Change History

| Date | What Changed | Why |
|------|--------------|-----|
| 2026-05-30 | Initial NEXT_STEPS.md created from operator/Devmate discussion | Capture six directions + Run 8 review TODOs in one place |
| 2026-05-30 | Section #1 (Google API) collapsed; canonical content moved to `TUNING.md`. | Operator: "prefer next steps file to shrink as we progress" |
| 2026-05-30 | Shipped `complete_with_retry` in `toolkit.llm_client`; wired through CostAccountant + ToolkitLLMAdapter. | Operator: "no reason to postpone" |
| 2026-05-30 | Re-sequenced toward cleanup before exploration. | Operator: "tooling debt, live TG resmoke, coaching test on pi, then the rest" |
| 2026-05-30 | Added §8 (Reverse scenario builder) and §9 (Voice/style templates). | Operator: "we should have a scenario builder that runs the analyzer in reverse... also tune voice from templates" |
| 2026-05-30 | Marked tooling-debt items (LoggingLLMClient SCORE/RECON, scenario compiler BATNA hardcode, dated OpenAI pricing) RESOLVED. | Operator: "don't forget to update the docs after a step is done" |
| 2026-05-30 | Added `SMOKE_RUNBOOK.md` at project root. | Operator: "Live Telegram re-smoke on Pi — verify deployment readiness" |
| 2026-05-31 | Live TG re-smoke **CLOSED for coaching scope** (reframed). Telegram is the operator coaching surface; production game traffic comes via Clankmates or equivalent. | Operator: "this is not how the game will work; we were looking into clankmates exactly for this reason" |
| 2026-05-31 | Added `ASSESSMENT.md` at project root — conceptual framework. Tagged every section heading + sequencing item with `[A]`/`[B]`/`[C]`/`[X]`. | Operator: "let's document this as rationale and potential avenues for exploration" |
| 2026-05-31 | Module boundary audit → §1.7 / §1.8 / §1.9 added. | Operator: "can we consider the broader code structure?" |
| 2026-05-31 | Loop-readiness classification (🔨 / 🔀 / 👁). Pure-build items batched into Phases 20–24. | Operator: "I'll run loops myself... pure build/mix/supervised" |
| 2026-05-31 | Added "Reference Docs to Keep in Sync" to CLAUDE.md + CODEX.md. Per-phase doc-update steps in DEVPLAN. | Operator: "we should include an explicit step to update this doc whenever cli gets touched" |
| 2026-06-01 | **Big cleanup pass.** All Phases 20–24 items collapsed to a single "Closed since 2026-05-30" table at top. Removed §1.5 / §1.7 / §1.8 / §1.9 detail sections (done; details in DEVLOG_archive Phase 20–22 entries). Removed Backlog → Tooling debt RESOLVED items and Open BATNA follow-ups (all done in Phase 24). Removed Live TG re-smoke CLOSED detail block (audit lives in DEVLOG_archive). Promoted `service.sh` rewrite + structured per-event logging from CLOSED tooling-debt narrative into a fresh "Outstanding tooling debt (🔨 PURE BUILD; not in any phase yet)" subsection so they're not lost. Carry-forward list trimmed to actually-still-open items. File shrunk 770 → ~470 lines. | Operator: "please review the closed items and clean up NEXT_STEPS with the items we just completed" |
| 2026-06-01 | `tools/service.sh` rewrite around tmux **queued as Phase 25 in `DEVPLAN.md`** (7 steps; auto-loop-ready). Outstanding tooling debt subsection trimmed accordingly; pure-build extensions table updated (per-event logging is now the only candidate alongside §1.6 / §3 / §3.3); classification row for service.sh now points at Phase 25. | Operator: "please write up the service.sh rewrite into devplan as next phase" |
| 2026-06-01 | Structured per-event logging **queued as Phase 26 in `DEVPLAN.md`** (8 steps; auto-loop-ready; independent of Phase 25). Classification row updated to point at Phase 26. Outstanding tooling debt subsection now shows both items closed-out into phases. Pure-build extensions table dropped the per-event-logging row (no longer a candidate — it's queued). | Operator: "can you line up Structured per-event logging in orchestrator + transport as the following phase into devplan as well?" |
| 2026-06-01 | **Phase 25 / 26 / 27 closed** (service.sh tmux rewrite, structured per-event logging, no-deal-aware scoring metrics). Added to Closed-since table. | Phases shipped. |
| 2026-06-01 | **Runs 9 + 10 closed.** Run 9 (3 asymmetric BATNA variants, single-provider): β-squeezed reached Pareto deal, others no-deal. Run 10 B' (α-squeezed + Anthropic on β): reached Pareto deal — same configuration that produced no-deal in Run 9 α-squeezed (all OpenAI). Run 10 C' (α+β dual-squeeze, all OpenAI): no-deal, γ defected R3→R4. **Provider consistency confirmed as dominant variable.** Added §1.7 / §1.8 / §1.9; updated §7 with consistency-as-axis note; carry-forward + backlog updated; loop-readiness table refreshed. | Operator: "Sync Run 10 findings into NEXT_STEPS.md (Open Items + provider consistency discovery)" |
| 2026-06-02 | **Tier-priority restructure.** Replaced "Suggested Sequencing" with "Open items by workstream tier" (A/X foundational → C game-design → B prompt-tuning) per operator: "these are tiers that support the next one so we should move in that sequence." Updated §1.6 (drop stale "Run 9" planning), §5 (expanded with Discord + fallback platforms — Clankmates blocked on partners, Discord as hedge). Backlog "Why no Pareto-optimal Shared deal (Run 8)" → marked partially answered by Runs 9-10. Closed items moved to Appendix A (organized: Build phases / Phase 19 ad-hoc / Experiments / Re-scoped / Tooling debt). Carry-forward + tooling-debt sections trimmed of closed items. Header dropped "post-Phase 24" framing; date bumped to 2026-06-02. | Operator: "review next_steps.md: check if there are stale/obsolete items and update; closed items should probably be moved to appendix... discuss open items in terms of workstream blocks... it's unclear if clankmates are happening, maybe we should also look into discord" |
| 2026-06-02 | **Phase 28 cleanup.** State summary updated (Phases 20–28 closed). Near-miss §1.9 marked closed in Tier 1 table (all TODOs done). Coached self-play harness + near-miss rows removed from pure-build extensions table (shipped). Sequencing list trimmed (near-miss removed; coaching test updated to reflect build-done status). Stage 2a → "Phase 29 candidate." §3 TODO removed stale "Phase 25 candidate" note. §6 audit scope updated to Runs 1–10. Appendix A expanded with Phase 28 items. | Sync with Phase 28 completion |
| 2026-06-02 | **Conversation model deprioritized.** Stage 2a removed from Tier 1 (sealed-bid rounds produce real dynamics; pressure mechanisms work with extra rounds). §3 rewritten as standalone deferred section with deprioritization rationale. §2 pressure mechanisms decoupled from §3 dependency ("Connects directly to §3" → uses existing `round_updates` mechanism). Conversation model moved to new "Deferred" tier below Tier 3. §2 Tier 2 row updated. Cross-tier deps trimmed. Pure-build table dropped Stage 2a row. Sequencing list shortened. | Operator: "unclear how this is different from having twice as many rounds... I don't see the value" |
| 2026-06-07 | **Coaching v2 → Phase 33.** §4e rewritten as a pointer to the queued phase plan (full design pinned in `DEVPLAN.md` Phase 33: `/revise:` directive mode + `LLMEditClassifier` + `tools/classify_edit_log.py` + `/edits-summary` command + storage schema). §4 status block updated to note Run 13 was approve-only and edit path remains untested in a live run. Original §4 TODOs split: "After UX fixes" item replaced with two explicit follow-ups (Run 14 + prompt-refinement step). §4f marked out-of-scope for Phase 33. Tier 1 table row "Coached game UX fixes" reclassified as **closed** (§4a-§4d shipped); residual coaching items now queued in Phase 33. "Coaching test loop on Pi" row updated with Run 13 status + gating on Phase 33. Carry-Forward Items table adds Run 14 as a queued experimental run with cost estimate. | Operator: "let's discuss and plan coaching v2; once done, let's write it into devplan and I'll run it, no point in moving it to next steps and back" |
| 2026-06-07 | **Bare-prompt ablation -> Phase 34 + section 10.** Added new section 10 "Ablation: bare-prompt vs full-harness" with the Run 14a-14f experimental matrix (3 model tiers x 2 modes x 2 scenarios x 3 runs = 36 runs, ~$60-100). Phase 34 (bare-mode plumbing) queued in `DEVPLAN.md`. Renamed the previous post-Phase-33 coached re-test from "Run 14" to **Run 13b** to free Run 14 for the ablation series - updated in section 4 Status block + section 4 Original TODOs + Carry-Forward + Tier 1 "Coaching test loop on Pi" row. New Tier 1 row "Bare-prompt ablation (does the harness contribute?)" added. State-as-of block updated. | Operator: "tbh I'd rather pursue this now. if we find that harness does nothing, there's no point in working on it any further... right?" |
| 2026-06-08 | **Cleanup pass.** Tier 1 Open Items table: removed closed rows (Coached game UX fixes, OpenRouter integration). Updated Bare-prompt ablation row to reflect Phase 34 close. Pure-build extensions table: removed closed rows (1.6 OpenRouter, ASSESSMENT 3.3 vs-Naive baseline). Sequencing list: dropped stale "Coached game UX fixes" entry; renumbered (now 1=Run 14a-14f ablation, 2=Pricing audit, 3=Game-platform). Deleted closed sections in their entirety: 1.6 (OpenRouter, closed Phase 30), 1.9 (Near-miss diagnostics, closed Phase 28), 9 (Voice templates, WON'T DO). Backlog: removed empty "Outstanding tooling debt (None)" subsection. 10 Build status updated from "prerequisite/queued" to "closed 2026-06-08". File shrunk ~80 lines. | Operator: "clean up the next_steps doc - remove closed items from Open Items table - if the info is in devlog, just delete, otherwise consider where it should go but don't keep them in the open table" |
| 2026-06-08 | **10 matrix locked.** Final design: 3 model tiers (gpt-4.1-nano weak / gpt-5.4-mini mid / claude-sonnet-4-6 strong) x 2 modes (full/bare) x 1 scenario (Water Rights beta-squeezed) x 3 runs = 18 runs, ~$20-40. Dropped second scenario (Trade Summit not in repo; Three-Party Coalition viable as v1.5 follow-up if results warrant). Mid bumped to gpt-5.4-mini per operator pin (was gpt-4.1-mini). Strong bumped to claude-sonnet-4-6 from haiku self-play default since haiku is tier-equivalent to mid - no real tier separation. BATNA fixed at beta-squeezed per operator (~50% historical deal rate gives leeway for harness/bare differentiation, vs symmetric where everyone sits at BATNA). Run order sequenced cheap-first: gpt-5.4-mini cells -> gpt-4.1-nano cells -> sonnet-bare -> sonnet-full last. | Operator: "let's bump mid-tier to 5.4, strong tier whatever is default, drop second scenario, use beta-squeezed - we want something that produces agreement ~half the time so models have some leeway" |
| 2026-06-08 | **Run 14 mid-campaign sync.** Cells 14a-14c complete (12 runs); 14d/14e pending. State-as-of bumped (Phase 34 closed, 14a-c done with cross-tier picture). 10 Run sequencing table got Status column with results + revised cost figures (sonnet-bare ~$0.50, sonnet-full conditional). New "Cross-cell read" subsection summarizing the three headline findings (harness contribution is close-rate-not-quality; harness substitutes for ~1+ model tier; bare degrades steeply with weaker models). All findings caveated by RESEARCH_NOTES.md Note 1 scale-1 scenario warning. Canonical narrative + per-cell detail moved to TUNING_LOG.md Run 14 campaign entry. | Operator wrap of work-session: "document our outcomes for completed runs + discuss implications + document 14d/14e as potential next runs and why + update next steps as per results" |
| 2026-06-12 | **Run 16 sync.** State-as-of refreshed to "Phases 20–38 closed + Runs 14 + 16 complete." Added cross-tier, cross-scenario findings paragraph capturing the Note 1 partial refutation (sonnet-bare = sonnet-full = 3/3 on jsm1; harness contribution scenario-dependent, not richness-dependent). Tier 1 "Bare-prompt ablation" row updated to reflect Run 14 + 16 close + Note 1 amendment. New Tier 1 row "Phase 38 pressure × mid-tier jsm1 (N4)" added as the sharpest residual experiment. §10 TODOs marked done for Runs 14 + 16; project-direction decision row populated with the post-Run-16 read (harness load-bearing on cooperative-single-Pareto for weak/mid OpenAI; harness redundant for sonnet on multi-Pareto; production default now scenario-dependent). §10 Run 16 sub-section added with cross-scenario matrix + four findings. Sequencing within Tier 1 list re-numbered: Run 17 (N4 pressure on jsm1 mid-tier) → pricing audit → game-platform. Carry-Forward: Run 14 + 16 marked done; Run 17 candidate added (N4 primary, N4b alternate). Companion edits in `TUNING_LOG.md` Run 16 entry + `RESEARCH_NOTES.md` Note 1 amendment. | Operator: "Sync NEXT_STEPS.md + ASSESSMENT.md with Run 16" |
| 2026-06-12 | **Competitive scoring documented (§11 + RESEARCH_NOTES Note 2).** Operator question mid-Run-17 surfaced the agreeableness-bias structural problem: current setup makes mixed-model runs produce deadlock-at-BATNA rather than "X model wins, Y loses." New §11 in NEXT_STEPS captures three paths forward (Path A: behavioral signal via existing scenarios + transcript analysis; Path B: engineer coalition-exclusion scoring in harness, 1-2 day build; Path C: new scenario class — distributive bargaining / asymmetric-BATNA / hidden-value — that produces rank-discriminating outcomes via scenario design alone). Tier 2 table gets new row pointing to §11. Full conceptual discussion (origin, diagnosis, four design options, harness-engineering gap, two product directions — cooperative coaching vs competitive benchmark) lifted to `RESEARCH_NOTES.md` Note 2 in the long-form thesis space. Cheapest immediate test (Path A on existing Three-Party Coalition compile, ~$1-2 calibration) queued as 11.a + 11.b TODOs; product-direction lift-to-`DECISIONS.md` flagged. No work shipped yet — this is queue + framing only. | Operator: "meanwhile can we document competitive scenarios as the next step forward?" |
| 2026-06-16 | **D-56 direction pivot — Diplomat is now an LLM negotiation benchmark.** Tier-priority restructure flipped: Tier 1 is now `[C]` benchmark direction (Path B coalition scoring engine, §3.5/3.6 lenses, mixed-model dispatcher, scenario-class authoring, Phase 41/42 scale verification, Run 17 follow-ups, N4 pressure on jsm1, per-run cost capture, pricing audit) — was previously Tier 2 under cooperative framing. Tier 2 is `[A]`/`[X]` infrastructure that serves the benchmark (provider-native structured output, TurnBasedFlow / position rotation, reconciliation live validation, identify-the-blocker). Deferred — coaching product (infrastructure preserved): Run 13b, §4 Pi coaching loop, §5 Clankmates/Discord exploration, TelegramReviewGate production default, strategy routing, per-role model strategy, provider consistency tests, persona tuning items. State-as-of bumped to 2026-06-16. Tier-priority rationale paragraph rewritten. Sequencing within Tier 1 rewritten to put Path B build first (load-bearing for benchmark v2 per `PROJECT.md` MVP table) → §3.5 lens → mixed-model dispatcher + §11.b → Path C scenario authoring → Run 17 follow-ups → N4 + Phase 41/42 → cost capture + pricing audit. Companion edits in `PROJECT.md` (Spark/scope/MVP reframe), `ASSESSMENT.md` (§3.5/3.6 lenses queued, workstream tier banners), `RESEARCH_NOTES.md` Note 2 (resolved), `DECISIONS.md` D-56 (canonical decision). Run 17 wrap entry + per-section detail (§1.7, §1.8, §2.5, §3, §4, §5, §7) preserved historically; D-56 deferral applies to which items are Tier 1, not whether they exist. | Operator: "I'd like to pursue the negotiation benchmark direction; please update our docs to reflect that, then we'll work on closing open threads and defining the next steps that serve the benchmark" |

# Diplomat Self-Play Tuning Log

A record of the iterative tuning process for the Diplomat AI negotiation agent,
conducted via multi-agent self-play simulations.

> **Before any live run, follow `RUN_PROTOCOL.md`** — the canonical pre-flight
> sequence (define inputs → verify scenario → probe providers → dry-run plumbing
> → run live → verify output → document). Skipping the protocol burned ~14
> Gemini calls in Run 8 before the bugs surfaced.

---


## At-a-glance — current state

**Recent results tally:**

| Scenario | Tier | Model | Mode | n | Close rate | Notes |
|---|---|---|---|---|---|---|
| Water Rights β-squeezed | weak | gpt-4.1-nano | full | 3 | 2/3 | identical Pareto when closing |
| Water Rights β-squeezed | weak | gpt-4.1-nano | bare | 3 | 0/3 | bare collapses at weak tier |
| Water Rights β-squeezed | mid | gpt-5.4-mini | full | 3 | 2/3 | identical Pareto when closing |
| Water Rights β-squeezed | mid | gpt-5.4-mini | bare | 3 | 1/3 | one closing run |
| Water Rights β-squeezed | strong | claude-sonnet-4-6 | full | 3 | **0/3** | strategic refusal (beta+gamma coalition rejects asymmetric concession) |
| Water Rights β-squeezed | strong | claude-sonnet-4-6 | bare | 3 | 0/3 | |
| Water Rights β-squeezed | strong | gpt-5.5 (OpenAI) | bare | 3 | **3/3** | temp=1 (forced); closes the asymmetric deal sonnet refused — provider confound is real (Run 18) |
| Joint Space Mission v1 | weak | gpt-4.1-nano | full | 3 | **1/3** | finds balanced-consensus when closing; identical to sonnet's deal |
| Joint Space Mission v1 | weak | gpt-4.1-nano | bare | 3 | 0/3 | |
| Joint Space Mission v1 | mid | gpt-5.4-mini | full | 3 | **0/3** | converges on 2 of 3 issues every run; stuck on mission_objective |
| Joint Space Mission v1 | mid | gpt-5.4-mini | bare | 3 | **0/3** | harness-immune failure; bare reproduces "stuck-but-engaged" |
| Joint Space Mission v1 | strong | claude-sonnet-4-6 | full | 3 | **3/3** | finds balanced-consensus Pareto every run (alpha 19 / beta 18 / gamma 22) |
| Joint Space Mission v1 | strong | claude-sonnet-4-6 | bare | 3 | **3/3** | identical Pareto every run; harness contribution = 0 at strong tier |
| Joint Space Mission v1 | strong | gpt-5.5 (OpenAI) | bare | 3 | **3/3** | temp=1; balanced-consensus deal; ceilings like sonnet (Run 18) |
| Joint Space Mission v1 | mid-Google | gemini-2.5-flash-lite | full | 1 | 0/1 | low-tier quality failure (identity confusion + R3→R4 drift) |
| Water Rights β-squeezed | mid+ (Chinese) | deepseek/deepseek-chat (V3) | full | 1 | **0/1** | strategic refusal at BATNA (sonnet-like) |
| Water Rights β-squeezed | mid+ (Chinese) | deepseek/deepseek-chat (V3) | bare | 3 | **0/3** | strategic refusal in both modes (sonnet-like) |
| Joint Space Mission v1 | mid+ (Chinese) | deepseek/deepseek-chat (V3) | full | 1 | **1/1** | finds identical balanced-consensus deal sonnet finds (`{α:8, β:9, γ:10}`) |
| Joint Space Mission v1 | mid+ (Chinese) | deepseek/deepseek-chat (V3) | bare | 3 | **1/3** | harness lift visible — same deal when closing, but flaky without intel |
| Water Rights β-squeezed | mid (open-weight) | meta-llama/llama-3.3-70b-instruct | full | 1 | 0/1 | capability-floor candidate (n=1; needs expansion to confirm) |
| Joint Space Mission v1 | mid (open-weight) | meta-llama/llama-3.3-70b-instruct | full | 1 | 0/1 | capability-floor candidate (n=1; needs expansion to confirm) |
| Joint Space Mission v1 | reasoning (Chinese) | deepseek/deepseek-r1 | full | 1 | **1/1** | identical balanced-consensus deal (`{α:8, β:9, γ:10}`) — 4th provider family converging on same Pareto; remaining 5 R1 cells queued (Tier 1) |
| Water Rights β-squeezed | reasoning | deepseek/deepseek-r1 | full | — | QUEUED | toolkit `606e309` unblocked R1; cell pending |

**Most recent finding (Run 17, 2026-06-12):** Multi-provider calibration via OpenRouter (first time non-OpenAI/non-Anthropic models hit the matrix). DeepSeek V3 inserts cleanly into a "mid+" tier between gpt-mini and sonnet, but with a *hybrid* behavior shape: sonnet-like on WR-β (strategic refusal both modes, 0/4 deals total) but mid-tier-like on jsm1 (1/1 full, 1/3 bare — harness lift returns at this tier where sonnet had zero). **V3 has enough strategic capability for refusal but not enough for proactive coordination.** Llama 3.3 70B looks below capability floor on n=1 (0/2). DeepSeek R1 deferred due to OpenRouter empty-content wiring gap (5 reasoning models tested across 3 backends all exhibit it for non-OpenAI routes); toolkit patch shipped as `606e309` so R1 is unblocked for future runs. Cost-economics revision: V3 is the **new production-default candidate for WR-β-shape scenarios** (~$0.10/run vs sonnet's ~$2 with same behavior); jsm1-shape still wants sonnet.

**Most recent finding (Run 20, 2026-06-22):** succ-v2 (`succ2`) - distributive scenario with HARD priority collision (alpha & beta both top-priority on industrial_heartland), built to fix Run 19's focal-point convergence. Same lineup (sonnet / gpt-5.4-mini / deepseek-v3), seat-rotated, 6 bare games. **Result: the collision removed the focal point but overshot into DEADLOCK - 5 of 6 games reached no deal** (all factions at BATNA 9/9/9); the lone 'deal' was a degenerate partial agreement (defense only, leaving alpha/beta below BATNA). So succ2 also fails to discriminate, for the OPPOSITE reason to v1: v1 converged on one focal deal (no diversity), v2 deadlocks (no deal). The alpha-vs-beta heartland fight is too hard to broker in 4 bare rounds with a thin compromise margin (the loser gets 10 vs BATNA 9). **Lesson:** a discriminating distributive scenario needs a sweet spot - a contest resolvable WITHOUT an obvious focal point, so skill shows in WHO wins the contested asset, not in WHETHER anyone closes. Two scoring bugs surfaced and were fixed (deal_reached left True on a partial-coalition no-deal, commit cdff1cf; below-BATNA 'deal' accepted, commit 3fa0f75), and the rank_aggregator no-deal filter (32372b6) correctly excluded all 5 deadlocks. Next: tune succ2 (lower BATNAs / wider loser compensation) toward the sweet spot. Evidence: `tests/self_play/results/run17_bare_mix-*_succ2_*.json`.

**Most recent finding (Run 19, 2026-06-22):** First mixed-model rank-lens experiment - exercised the full section 3.5 pipeline (ablation_multi.sh runrotate -> faction_models -> faction_ranks -> rank_aggregator) end-to-end on the new `succ` distributive scenario. Lineup: sonnet (Anthropic) / gpt-5.4-mini (OpenAI) / deepseek-v3 (OpenRouter), seat-rotated (3 cyclic rotations x 2 = 6 bare games, ~$1-3). **Tooling works end-to-end; the scenario does not yet discriminate.** All 6 games converged on the identical deal (Alpha-Administered / Beta-Custody / Gamma-Command = 13/11/12), so rank was determined by *seat* (alpha->1, gamma->2, beta->3 every game), NOT by model skill. The mean_rank spread (gpt-mini 1.83 vs sonnet/deepseek 2.00) is an artifact of seat rotation plus one anomalous game (`succ_1` scored at BATNA despite deal_reached=True, deltas 0/0/0). **Lesson:** constant-sum removes the mathematical dominant attractor but not a *salience* focal point - "everyone takes their own priority asset" is a Schelling point all models coordinate on; `succ` needs priority collision (a contested asset) to produce outcome diversity. The section 3.5 tooling is validated and ready - the scenario is the gap. Evidence: `tests/self_play/results/run17_bare_mix-*_succ_*.json`.

**Most recent finding (Run 18, 2026-06-22):** Strong-OpenAI tier added to the §10 ladder to break the tier/provider confound — `gpt-5.5` (strong, OpenAI) run bare on both scenarios. **Result: 3/3 on both WR-β and jsm1.** This is the decisive disentangling datum: on WR-β, sonnet (strong, Anthropic) floors 0/3 via strategic refusal, but gpt-5.5 (strong, OpenAI) closes 3/3 — its factions accept the asymmetric Heavy-Downstream concession sonnet's beta+gamma reject (deltas {α:7, β:3, γ:9}). **So the WR-β "strong-tier" failure was sonnet-specific (a model/provider behavior), not a property of strong models** — the provider confound (caveat below) is real and material. Temperature caveat: gpt-5.5 only accepts `temperature=1` (the toolkit now omits the param for gpt-5.x/o-series), so this cell ran at temp=1 vs the rest of the matrix at 0.7; a 0.7→1.0 shift flipping 0/3→3/3 is implausible, so the uniform-temp confirmation was deliberately skipped as low-value. gpt-5.5 **full was not run**: bare already ceilings 3/3 on both, leaving no headroom to measure harness lift (the same saturation that makes sonnet's cells lift-uninformative). Cost ~$2.40 (6 bare games).

**Open questions / proposed next tests:**

| Test | Cost | Wall | Isolates |
|---|---|---|---|
| **succ2 full-mode** (harness on a hard distributive contest) | ~$6-15 (n=1 = 3 games) | ~30-50 min | Does the FULL harness break succ2's bare deadlock? If full closes where bare deadlocked -> clean harness-contribution result on distributive bargaining (Q2). Calibrate cost with 1 game first. |
| **succ-v3 sweet-spot scenario** (model-comparison) | design + ~$1-3 bare | ~25 min | Tune succ (lower BATNAs / wider loser compensation) so the contested asset resolves WITHOUT a focal point - deals close AND vary by who wins (Q1 rank lens). |
| **V3 full n=3 expansion** on both scenarios | ~$0.15 | ~12 min | Solidify V3 baseline — n=1 full samples are the weakest cells in the matrix; n=3 confirms whether 1/1 jsm1 + 0/1 wrbeta is robust or noise. |
| **R1 cells (toolkit-unblocked)** × 3 on both scenarios | ~$2-4 | ~30-60 min | First reasoning-model data point. Does R1 exhibit V3's hybrid pattern or sonnet's strong pattern? Generation latency on R1 is high (~16-20 min/cell). |
| **N4** gpt-mini + Phase 38 pressure × 3 on jsm1 | ~$1.50 | ~36 min | Does pressure unstick the mid-tier convergence floor on jsm1? Cleanest Phase 38 value test now that bare-mode confirms harness doesn't help here. |
| **N1+** claude-haiku-4-5 × 3 on jsm1 (full + bare) | ~$0.30-1 | ~8-25 min | Sonnet-specific vs Anthropic-in-general; with bare/full both included, isolates whether haiku also exhibits harness-zero behavior. |
| **N2** gemini-2.5-flash × 1-3 on jsm1 (full + bare) | ~$1-2 | ~12-25 min | Fair Google data point + does the harness-zero pattern show for a stronger Gemini. |
| **Llama n=3 expansion** on both scenarios | ~$1 | ~30 min | Confirms capability-floor read vs n=1 noise. Lower priority given the 0/2 start. |
| **Same-provider tier ladder** (OpenAI nano→gpt-5.4-mini→gpt-5.5, and/or Anthropic haiku→sonnet→opus) | ~$3-6 | varies | **PARTIALLY DONE (Run 18, 2026-06-22, bare only):** `gpt-5.5` (strong, OpenAI) closes WR-β bare 3/3 vs sonnet's 0/3 → confound confirmed real; the WR-β strong-tier failure is sonnet-specific. Remaining for a complete fix: the same-provider ladder across full mode + uniform temperature (low priority — bare already settles the load-bearing question; strong cells ceiling so full adds no lift signal). |
| **N5** jsm-v2 with multiple **equal-/near-equal-sum** Pareto deals, each favoring a *different* faction (no dominant attractor; avoid an equal-split Schelling point) | $0 design + ~$5 test | ~70 min | jsm1's balanced-consensus deal is both highest-sum *and* most balanced, so it dominates and every model converges there (zero outcome diversity). Equal-sum-but-differently-distributed Pareto deals turn "which deal" into a genuine distributive contest — the precondition for the §3.5 rank lens and `pareto_outcome_diversity` to produce signal. NB: among such deals the choice is effectively zero-sum, so this tests *claiming* skill, not value-creation. |
| Scale-axis scenarios (4+ factions, long-horizon, deception) per `RESEARCH_NOTES.md` Note 1 | requires Phase 41/42 | varies | The remaining axes Note 1 names — context, relationships, deception, horizon — were NOT tested by Run 16/17 (jsm1 only varies multi-Pareto from WR-β). Validating Note 1's thesis fully requires those scenario shapes. |
| **§11.b mixed-model Three-Party Coalition** (Path A) | ~$1-2 | ~30 min | Path A test of competitive scoring per NEXT_STEPS §11; patched scenario JSON ready. With V3 now an established cost-tier intermediate, suggested lineup is sonnet + gpt-mini + V3. |

**Operational invariants (cross-run facts to trust):**

- Every closing run on Water Rights β-squeezed found the **identical Pareto deal**: alpha 16 / beta 18 / gamma 20.
- Sonnet finds the **identical Pareto deal 3/3 on jsm1** in *both* full and bare modes: alpha 19 / beta 18 / gamma 22 (the balanced-consensus point, every faction ≥86% of max). Zero within-cell variance across all 6 sonnet jsm1 runs.
- **Nano-full on jsm1 also finds the identical balanced-consensus deal** when it closes (1/3). When weak-tier models close on jsm1, they converge on the same answer sonnet does.
- **DeepSeek V3 finds the identical balanced-consensus deal on jsm1** when it closes (1/1 full + 1/3 bare = 2/4 same deal). Cross-provider convergence on the same Pareto point reinforces that the attractor lives in the scenario topology, not in any single model's training distribution.
- Mid-tier OpenAI fails on jsm1 with **substantive 2/3-issue convergence**, in both full and bare modes (NOT a harness gap — capability gap).
- Gemini-flash-lite exhibits **identity confusion + R3→R4 position drift** on jsm1 (low-tier quality failure, distinct from gpt-mini's substantive-but-stuck pattern).
- **Bare mode is load-bearing for OpenAI Generators on Water Rights** (full > bare at weak and mid tiers); **sonnet's jsm1 cells show no full-vs-bare difference, but this is a ceiling effect** (both 3/3 — no headroom above 3/3 to reveal a harness lift), not a measured-zero contribution; **bare mode IS load-bearing for V3 on jsm1** (1/1 full > 1/3 bare, n caveats).
- **Two structural caveats on the whole ablation matrix (added 2026-06-16; (a) partially resolved 2026-06-22):** (a) *tier was confounded with provider* — weak/mid are OpenAI, strong is Anthropic. **Run 18 broke this on the bare axis:** `gpt-5.5` (strong, OpenAI) closes WR-β bare 3/3 where sonnet (strong, Anthropic) floors 0/3, so the WR-β strong-tier failure is sonnet-specific, not a "strong-tier" effect. (A same-provider ladder across full mode + uniform temperature is still the complete fix, but the load-bearing confound is now demonstrated real; gpt-5.5 ran at temp=1 vs the matrix's 0.7 — see Run 18 caveat.) (b) *both sonnet cells are saturated* — WR-β at the floor (0/3 = 0/3, strategic refusal) and jsm1 at the ceiling (3/3 = 3/3) — so sonnet contributes **no usable harness-*lift* evidence**; gpt-5.5 likewise ceilings both bare cells (3/3), so it too is lift-uninformative. Only the weak/mid cells have headroom to measure lift. Read earlier "sonnet's harness contribution = 0" framings as "unmeasurable on sonnet," not "measured zero."
- **"Cheap+harness is the production default"** holds on cooperative-single-Pareto scenarios (WR-β) — and `cheap` now includes DeepSeek V3 (~$0.10/run, sonnet-like refusal behavior). On multi-Pareto scenarios (jsm1) the production default is **strong+bare** — sonnet-bare at ~$0.30/run closes 3/3; V3 cells underperform sonnet here.
- **Multi-Pareto scenario design does NOT automatically produce outcome diversity** — sonnet picks the same Pareto every run on jsm1 in both modes (6/6 identical deals); strong attractor is a scenario property, not a harness anchoring effect.
- **OpenRouter reasoning models** (DeepSeek R1, R1-distill, Qwen3) routed to non-OpenAI backends (Azure, Novita, DeepInfra) return their answer in `reasoning`/`reasoning_content` field with `content` empty. Toolkit `OpenRouterProvider` now falls back to those fields (toolkit `606e309`). Only `openai/o4-mini` returns standard content because OpenRouter's OpenAI-passthrough route preserves the OpenAI-side server-side merge.


## Archived runs

Full per-run write-ups for Runs 1-13 + Phases 7-9 live in
`TUNING_LOG_archive.md` (archived in two passes, 2026-06-02 and 2026-06-11).
The headline takeaways below are preserved in this file.

| Run(s) | Scenario(s) | Headline |
|---|---|---|
| 1 | Territory (regex extractor) | Zero promises tracked → switched to LLM extraction |
| 2 | Territory (LLM extractor) | Zero promises tracked → debounce bug found and fixed |
| 3 | Territory (fixed debounce) | Extraction works; schema-validation errors → built `structured_call` |
| 4 | Water Rights (hand-tuned) | 21 promises tracked; personality-style personas insufficient |
| 5 | Trade Summit (dirty bargaining) | Point tables + named tactics + BATNA produce deception-then-reveal arc |
| 6 | Three-Party Coalition (auto-compiled) | Scenario compiler works; extraction prompt too narrow for coalition language |
| 7 | Three-Party Coalition (scored) | Endgame markers + finite-horizon signaling + dry-run validation; faction B closed in R4 |
| 8 | Water Rights (3-provider) | Cross-provider JSON formatting matters; `probe_providers` + `--per-faction-providers` added |
| 9 | Water Rights (3 BATNA variants) | β-squeezed reaches Pareto-optimal deal; α-squeezed shows R3→R4 defection (gpt-4.1-mini) |
| 10 | Water Rights (B′ + C′) | Provider consistency dominates BATNA: Anthropic-on-β closes with raw BATNAs; OpenAI-on-γ defects again |
| 11 | Water Rights (all-Anthropic) | Anthropic closes across all 3 BATNA variants |
| 12, 12b | Water Rights (all-Gemini variants) | Gemini-flash baseline (12b complete; 12 partial due to budget timeouts) |
| 13 | Water Rights symmetric (coached) | First coached game with OperatorReviewGate; new gate validated end-to-end |

Architectural decisions and infrastructure built across these runs are
summarized below in "Summary of All Changes" and live canonically in
`ASSESSMENT.md` (workstream blocks) and the per-module `ARCH_*.md` docs.

## Summary of All Changes

### Infrastructure
| Change | Files | Why |
|--------|-------|-----|
| Per-event extraction (debounce fix) | `src/orchestrator.py` | Messages were being silently dropped |
| `structured_call()` | `toolkit/structured_llm/core.py` | Reusable prompt+schema+examples+retry |
| Cost accountant wiring | `src/adapters.py`, `src/main.py` | Budget enforcement was a no-op |
| OpenAI pricing | `toolkit/cost_accountant/types.py` | Only Anthropic models were priced |
| Scenario compiler | `src/scenario_authoring/scenario_compiler.py` | Auto-generate scored personas from narratives |
| Post-game scorer | `tests/self_play/game_environment.py` | Determine winners/losers objectively |
| LoggingLLMClient | `tests/self_play/game_environment.py` | Full prompt/response/timing capture for analysis |
| Self-play round-boundary mirror | `tests/self_play/game_environment.py` | Self-play harness now sets `current_round`, `total_rounds`, and calls `_reset_round_budget()` per round; production orchestrator's `handle_round_boundary` only fires on `^ROUND N` signals the harness never sends |
| Orchestrator auto-trigger gate | `src/orchestrator.py` (`auto_response_enabled`) | Self-play sets this `False` so each agent generates exactly once per round instead of racing against its own auto-responses on every inbound message (see `ARCH_conversation_model.md` Stage 1) |
| Dry-run self-play | `tests/self_play/fake_llm_client.py`, `tests/self_play/verify_dryrun.py`, `--dry-run` flag on runner | Cost-free end-to-end plumbing validation; caught all 4 Run-7-prep bugs without spending money |

### Prompts
| Prompt | Key Changes |
|--------|-------------|
| `generation.txt` | Reference intelligence, hold factions accountable, cite specifics, adapt to pressure |
| `state_updater.txt` | Field allowlists, few-shot examples, promise state transitions, dedup rules, proposals as promises |
| `analyst.txt` | Use transcript alongside state tables, note contradictions |
| `adversarial.txt` | Removed redundant schema instructions (structured_call handles it) |

### Metrics Across Runs

| Run | Scenario | Promises | Coalitions | Cost | Key Finding |
|-----|----------|----------|------------|------|-------------|
| 1 | Territory (regex) | 0 | 0 | $0.09 | Regex extraction misses everything |
| 2 | Territory (LLM) | 0 | 0 | ~$0.09 | Debounce drops all messages |
| 3 | Territory (fixed) | 7 | 8 | $0.53 | Extraction works, schema validation errors |
| 4 | Water Rights | 21 | 0 | ~$0.55 | Rich negotiation, convergence, duplicates |
| 5 | Trade Summit | 8 | 0 | ~$0.55 | Deception tactics work with point tables |
| 6 | Coalition (auto) | 1 | 3 | ~$0.60 | Scenario compiler works, extraction too strict |
| 7 | Coalition (endgame, scored) | a=4, b=3, c=2 | 0 | ~$1-2 | **Endgame works:** B explicitly concedes majority-share in R4 (FINAL ROUND); reconciliation merges duplicate promises; no deal because A+B align but C dissents (game-theoretically reasonable for coalition exclusion). Four self-play infra bugs surfaced and fixed; dry-run capability added. |
| 8 | Water Rights (3-provider) | a=8, b=15, c=5 | 0 | ~$1 | **Provider differentiation visible qualitatively** but raw scores deadlock at BATNA. Volume and Infrastructure converge cleanly; Payment deadlocks (Alpha=Heavy-Downstream vs Beta+Gamma=Token). Pareto-optimal Shared compromise existed but no agent proposed it. Two silent-failure infra bugs surfaced and fixed (`.env` not loaded; toolkit `parse_json_response` didn't strip Markdown fences from Anthropic/Google JSON). New CLI flags: `--per-faction-providers`, `--analysis-json`, `--expect-providers`. New verifier: `verify_scenario_optimum.py`. Retro-pareto (2026-06-01): **efficiency = 0.537** (29/54). |
| 9 | Water Rights (3 asymmetric BATNA variants) | sym=29 / α-sq=22 / β-sq=13 | 0 | ~$1.20 | **Complete 2026-06-01.** Single-provider gpt-4.1-mini. β-squeezed variant **reached Pareto deal**: alpha=15 (+6), beta=18 (+3), gamma=22 (+11), pareto_efficiency=1.02. Symmetric (0.593) and α-squeezed (0.630) reproduced no-deal deadlock. Asymmetric pressure on the deadlock-holder unlocks the optimum; on the wrong faction it entrenches them. `time_to_deal=4` registered for first time. |
| 10 | Water Rights (B' Anthropic-on-beta + C' dual-squeeze) | B'=39 / C'=24 | 0 | ~$0.85 | **Complete 2026-06-01.** B' (alpha-squeezed BATNAs, beta on Anthropic claude-haiku-4-5, alpha+gamma OpenAI gpt-4.1-mini): **reached Pareto deal** alpha=15 (+0), beta=18 (+10), gamma=22 (+11), `negotiated_surplus_share=1.050`. Same configuration that produced no-deal in Run 9 α-squeezed (all OpenAI). Confirms OpenAI gpt-4.1-mini R3→R4 defection is provider-specific. C' (alpha+beta dual-squeeze, all OpenAI): no-deal — gamma defected from R3 Heavy-Downstream commitment to R4 Shared (same defection pattern as Run 9 α-squeezed beta, different faction, same model). |
| 13 | Water Rights symmetric (β coached, new gate, all Gemini flash) | sum=32 | 0 | ~$0.05–0.15 | **Complete 2026-06-04.** First coached game with the Phase 31 `OperatorReviewGate`. All factions at BATNA — γ defected R3→R4 from Heavy-Downstream to Shared (first observed Gemini R3→R4 defection on Water Rights). Contradicts Run 12b's uncoached deal-reaching result on same model + same BATNAs. Phase 31 gate validated end-to-end: chunking surface present, lazy `/reasoning` + `/adversarial` work, `/state`/`/status`/`/divergences`/`/ledger` work during pending review. Two gaps surfaced: R1 startup auto-resolved by stale `/approve` from previously-killed Phase-31-bug session (Phase 31b candidate — drain TG queue on listener startup), and `/intel` silent during pending review (separate latent bug). Also surfaced 31a hotfix: `RoundSteppedFlow` needs its own operator-input bridge since `OperatorReviewGate` no longer self-polls. |

**Total spend across completed runs (1-13): ~$7-8**
**Pre-flight already incurred: $0 (dry-runs free, OpenAI probe ~$0.001)**

---

## Key Insights

1. **LLMs default to cooperative.** Without explicit competitive instructions, agents converge on reasonable deals too quickly. Strategic play requires named tactics, point tables, and BATNA thresholds.

2. **Structured output enforcement matters.** Narrative prompts ("conform to schema") fail ~30% of the time. Few-shot examples + schema injection + retry reduces failures to near zero.

3. **Extraction definition determines tracking quality.** "Promise = binding commitment" misses most negotiation language. "Promise = any concrete proposal with specific terms" captures the actual game state.

4. **Asymmetric scenarios produce richer behavior.** Generic "3 factions fight over a zone" produces abstract percentage splits. Specific positions (dam/farms/money, or private scoring tables) produce concrete, trackable proposals.

5. **The scenario compiler closes the loop.** Narrative description -> LLM analysis -> scored personas -> self-play -> post-game scoring. The operator can iterate on scenario descriptions without touching code.

6. **Infrastructure bugs hide behind prompt problems.** The debounce bug (Run 2) looked like an extraction quality issue but was a pipeline race condition. Always verify the data pipeline before tuning prompts.

7. **Self-play harness must mirror what production round-boundary handling does** (Run 7). The production orchestrator's `handle_round_boundary()` does several things at once — increment round counter, reset per-round budget, run analysts — all gated on detecting a `^ROUND N` signal that the self-play moderator never sends. Skipping any of those mirrored side-effects in the harness produces silent failure modes (round never advances, budget never resets, endgame markers never fire). Encode the mirror explicitly.

8. **Finite-horizon agents need explicit endgame signaling to close** (Run 7). Telling an agent "round N of M" plus a dynamic FINAL ROUND marker in round N produces visible late-round closing behavior (faction B in Run 7 explicitly conceded majority-share in R4 after refusing for R1-R3). Without the signal, the agent has no reason to ever stop hedging.

9. **Validate plumbing for free before spending money** (Run 7). The dry-run capability (`DryRunLLMClient` + `verify_dryrun`) caught all four Run-7-prep bugs without a single live LLM call. Use it on every future structural change.

10. **Cross-provider JSON formatting differs even with identical prompts** (Run 8). Anthropic and Google wrap JSON output in `` ```json ... ``` `` Markdown fences regardless of explicit "return raw JSON" instructions. OpenAI returns raw JSON. Any structured-output layer must strip fences before parsing, or risk silent retry-then-give-up failure modes that look like "the model returned nothing."

11. **Silent failures hide behind "success."** (Run 8). Two of Run 8's bugs (missing `.env` load + missing fence-strip) produced "successful" LLM calls that returned strings the downstream parser couldn't read. The structured_call retry loop happily burned all retries on the same parse failure and reported no error. Active assertion of *expected* behavior (`--expect-providers` in verify_dryrun, expected message counts in verify_dryrun) is the cheapest way to catch these.

12. **Per-faction provider routing belongs in the runner, not the env** (Run 8). The original env-var-based config (`DIPLOMAT_PRIMARY_PROVIDER`) was global across factions. A CLI JSON flag (`--per-faction-providers`) is much cleaner: it's explicit, validates early, and the verifier can assert each faction got the assigned provider.

13. **Compiler defaults aren't always what you want** (Run 8). The scenario compiler's hardcoded BATNA range ("typically 4-8 total") produced too-soft pressure for our experiment regardless of narrative cues. A pre-compiled-analysis loader (`--analysis-json`) is the right escape hatch — it lets you hand-edit the compiler's output and reuse it across runs.

14. **Dry runs and live probes catch different failure modes** (Run 8 post-mortem). Dry-run validates *plumbing* (round counter, message routing, budget reset) because it controls the LLM responses. It cannot catch *provider integration* bugs (auth, JSON parsing, model name typos) because it replaces the LLM client entirely. The fix: a separate `probe_providers.py` that makes 1 real call per provider with a trivial prompt. ~$0.003 total. Run BOTH before any live multi-provider game.

---

## Phase 34: Bare-Prompt Ablation Infrastructure

### Run 14-smoke — Bare-Prompt Mode Validation (Water Rights γ-squeezed, all-gpt-4.1-mini) — COMPLETE

**Date:** 2026-06-08.
**Hypothesis:** `--bare-prompt` flag routes correctly end-to-end: no exceptions, valid run JSON with `bare_mode=true`, scoring metrics populated, coherent faction messages. This is a plumbing smoke, not an experimental comparison.

**Variables:** `--bare-prompt` flag (Phase 34 build). Scenario: Water Rights γ-squeezed. Provider: gpt-4.1-mini for all three factions. Rounds: 4.

**Pre-flight:**
- Probe: 3/3 passed (openai/gpt-4.1-mini, all factions).
- Dry-run: completed cleanly, 4 rounds, 21 transcript entries, `bare_mode=true` in JSON, scores populated. `verify_dryrun` invariant failures are all expected (no round-context in bare assembler → no `Round: X of Y` in user prompt → round hints absent; no adversarial calls by design). These are intentional bare-mode omissions, not bugs.
- Live run: ran without exception.

**Results:**
- Game completed 4 rounds, 21 messages, no deal (all factions at BATNA: α=11, β=10, γ=15).
- `bare_mode=true` in results JSON. Scoring fields populated.
- LLM call log: 12 GEN calls + 1 SCORE call (13 total). No EXT/ANALYST/ADV/RECON calls — bare modules correctly suppressed.
- Faction messages coherent: each faction articulated clear positions and proposals with issue-specific reasoning.

**Cost observation:** The live run was extremely cheap — 12 GEN calls with short bare context (persona + accumulating transcript only). Estimated ~$0.02 vs the projected ~$1. Bare mode removes the dominant cost drivers (Analyst × 2 + Adversarial per round). This makes the Run 14a-14f series (~$60-100 projected in full mode) likely achievable for ~$1-3 per bare game, or roughly 10-20× cheaper per bare run than full.

**Learnings:**
- Bare-mode plumbing is confirmed working end-to-end.
- No deal reached — consistent with removing the Analyst intelligence that helps agents identify Pareto trades. This is the expected signal for the ablation hypothesis.
- `verify_dryrun --adversarial` flag should NOT be passed for bare-mode runs. The script does not know about bare mode; its round-tracking and adversarial invariants don't apply.

**Decisions:**
- None. Smoke run confirmed; move to Step 34.5 (integration tests).

**Results file:** `tests/self_play/results/run14_smoke_bare_prompt.json`

---

## Phase 34 follow-on: Bare-vs-Full Ablation Campaign (Run 14a–e)

**Campaign goal.** Test the harness contribution thesis directly:
does Diplomat's harness measurably help over a bare-prompt baseline,
and does the harness's contribution scale with model strength?

**Design (locked 2026-06-08).** Three model tiers × 2 modes (full /
bare) × 1 scenario (Water Rights β-squeezed) × 3 runs/cell = 18 runs
total. β-squeezed picked for historical 2-of-2 deal rate — the
right "leeway zone" where harness/model effects can plausibly differ.
Single scenario; scenario breadth deferred to v1.5. See `NEXT_STEPS.md`
§10 for the full matrix and `RESEARCH_NOTES.md` Note 1 for the
scaling thesis the experiment tests.

**Scenario sanity.** Water Rights β-squeezed has **27 possible deals,
12 distinct achievable sums, 7 voluntarily acceptable, exactly 1
Pareto-maximal** (`{High volume, Heavy-Downstream, Joint Desalination}`
→ alpha 16 / beta 18 / gamma 20, sum 54, deltas `[+7, +3, +9]`). All
or nothing — no middle ground between sum 35 (BATNA floor) and the
single unique optimum. Per `tools/enumerate_outcomes.py`.

**Scorer fix shipped mid-campaign.** Original LLM scorer was doing
two jobs: (1) parse text → agreed_outcomes, (2) compute faction points
by summing scoring-table values. The arithmetic step was unreliable —
gpt-5.4-mini emitted `"points": 3 + 10 + 3` as JSON (invalid; arithmetic
in JSON values, run 14a-2), and separately over-counted gamma by +2
points (14b-2). Architectural fix (`c76b3da`): LLM extracts outcomes
only; `faction_score()` does the math deterministically. All 14a-14c
results below are post-rescore via `tools/rescore_run.py`. The LLM's
arithmetic errors were small enough to mostly not flip deal/no-deal
classifications, but two runs' faction scores shifted (14a-3 alpha
+1, 14b-2 gamma -2).

### Run 14a — gpt-5.4-mini (mid tier), full harness — COMPLETE

**Date:** 2026-06-08.
**Configuration:** all three factions on `gpt-5.4-mini`. Full harness
(Extraction, Analyst×2, Divergence, Reconciliation, Adversarial,
Coaching parser all active). Water Rights β-squeezed, 4 rounds, 3 runs.
**Cost:** ~$3-4 total (3 games at ~$1-1.50 each).

**Results:**

| Run | Deal? | δ sum | Faction deltas | `negotiated_surplus_share` |
|---|---|---|---|---|
| 14a-1 | No | 0 | `[0, 0, 0]` | 0.00 |
| 14a-2 | Yes | +19 | `[+7, +3, +9]` | 1.00 |
| 14a-3 | Yes | +19 | `[+7, +3, +9]` | 1.00 |
| **Cell** | **2/3** | mean +12.7 | identical Pareto when closing | mean 0.67 |

**Read:** mid tier with full harness reliably finds the unique Pareto
optimum (2 of 3 runs converged on identical scores; the no-deal was
variance). Matches historical Run 9 β-squeezed baseline (deltas
[+6, +3, +11] with gpt-4.1-mini, similar shape).

### Run 14b — gpt-5.4-mini (mid tier), bare prompt — COMPLETE

**Date:** 2026-06-08.
**Configuration:** same as 14a except `--bare-prompt` flag. All
of Extraction / Analyst / Divergence / Reconciliation / Adversarial /
Coaching disabled via `bare_module_overrides()` no-op stand-ins.
DefaultContextAssembler produces persona + raw transcript only.
**Cost:** ~$0.50 total (~50× cheaper per game than full mode).

**Results:**

| Run | Deal? | δ sum | Faction deltas |
|---|---|---|---|
| 14b-1 | No | 0 | `[0, 0, 0]` |
| 14b-2 | Yes | +19 | `[+7, +3, +9]` — **identical to 14a Pareto deal** |
| 14b-3 | No | 0 | `[0, 0, 0]` |
| **Cell** | **1/3** | mean +6.3 | same Pareto when closing |

**Read:** mid tier in bare mode closes ~half as often as full mode
(1/3 vs 2/3) but **finds the exact same Pareto solution** when it
does close. Harness contribution shows up in *close-rate*, not in
*deal quality*.

**Failure-mode note (14b-1):** the model conducted substantive
negotiation but defected at the bottleneck. Beta + alpha proposed
Heavy-Downstream payment; gamma swerved to Token payment in R4
("Gamma is prepared to lean toward Token rather than forcing a heavy
financial burden onto the downstream side"). Transcript shows agents
converged on 2-of-3 issues (volume + infrastructure) — a near-miss
that full mode probably would have closed via the Analyst's Pareto-trade
intel.

**Failure-mode note (14b-3):** also near-miss; agents discussed terms
substantively but didn't converge on all three issues by R4. Bare
mode lacks the Reconciler ratifying earlier commitments, so each
round drifts somewhat.

### Run 14c — gpt-4.1-nano (weak tier), full + bare — COMPLETE

**Date:** 2026-06-08.
**Configuration:** same scenario as 14a/14b; provider switched to
`gpt-4.1-nano` (cheapest OpenAI tier, $0.10/$0.40 per MTok). 3 runs
full + 3 runs bare.
**Cost:** ~$0.30 total across all 6 runs.

**Pre-flight note:** the first attempt at the 6 runs crashed in the
post-game display formatter (line 550 of `game_environment.py`) —
the deterministic scorer (`c76b3da`) returns `float` for points, but
the formatter used `:+d` integer format for `vs_batna`. Crash happened
inside `run_game()` before `_write_results()`, so JSONs weren't
written. Fixed (`4a1bb46`) and re-fired; all 6 runs landed clean.

**Results:**

| Run | Mode | Deal? | δ sum | Faction deltas |
|---|---|---|---|---|
| 14c-1 | full | Yes | +19 | `[+7, +3, +9]` |
| 14c-2 | full | No | 0 | `[0, 0, 0]` |
| 14c-3 | full | Yes | +19 | `[+7, +3, +9]` |
| 14c-bare-1 | bare | No | 0 | `[0, 0, 0]` |
| 14c-bare-2 | bare | No | 0 | `[0, 0, 0]` |
| 14c-bare-3 | bare | No | 0 | `[0, 0, 0]` |
| **nano-full** | | **2/3** | mean +12.7 | identical Pareto when closing |
| **nano-bare** | | **0/3** | 0 | always BATNA floor |

**Read:** weak tier with full harness **matches mid tier's close-rate
(2/3 = 2/3)** and finds the identical Pareto solution. Weak tier
without harness **never closes**. The harness fully compensates for
the model being ~10× cheaper.

This is the strongest single-cell signal in the campaign so far.

### Run 14d — claude-sonnet-4-6 (strong tier), bare — COMPLETE

Fired 2026-06-11 over ~25 minutes wall clock total. **0/3 deals — every run ended at the BATNA floor.**

| Run | Outcome | alpha | beta | gamma | `surplus_share` | `pareto_eff` |
|---|---|---|---|---|---|---|
| 14d-1 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |
| 14d-2 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |
| 14d-3 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |

**Headline implication.** Hits the "0/3 (like nano-bare)" row of the conditional table verbatim. **Strong-model-bare is no better than weak-model-bare.** Model strength does NOT substitute for harness on this scenario; bare mode is bottlenecked by the absence of structural reasoning support (analyst intel, state manager, reconciliation), not by raw model capability. Per the next-runs table below, this is strong support for "harness load-bearing here" and the §10 conditional logic now fires 14e as the next critical run (was conditional on 14d showing ≤1/3 close-rate).

Cost: ~$0.50 total (12 GEN-only calls per game × 3 games × sonnet pricing). Wall clock: ~8 min per run (sonnet's slower response time vs gpt-mini, but with no harness LLM calls the count stays low).

### Run 14e — claude-sonnet-4-6 (strong tier), full — COMPLETE

Fired 2026-06-11 over ~50 minutes wall clock total (3 runs sequentially, ~16-17 min/run). **0/3 deals — every run ended at the BATNA floor.** Identical to 14d (sonnet-bare).

| Run | Outcome | alpha | beta | gamma | `surplus_share` | `pareto_eff` |
|---|---|---|---|---|---|---|
| 14e-1 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |
| 14e-2 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |
| 14e-3 | NO DEAL | 9 (BATNA) | 15 (BATNA) | 11 (BATNA) | 0.000 | 0.648 |

But unlike 14d (sonnet-bare), substantive engagement DID happen — promises tracked: 14e-1 (9/9/9), 14e-2 (?/?/?), 14e-3 (3/8/6). Transcripts show all three agents proposing concrete deals through the final round. The fail mode is **non-convergence at the final round**, not silence.

Example from 14e-3 final round (scorer reasoning): "Alpha proposes Low volume...with Heavy-Downstream payment...Gamma supports Token payment. Since no unanimous agreement exists on water_release_volume and payment_structure, no deal is reached." Alpha pushes their priority (Heavy-Downstream payment); gamma pushes theirs (Token); neither concedes; converging deal never materializes.

Wall clock per run: ~16-17 min. Estimated cost per run: ~$0.60-0.75 (sonnet Generator + openai-mini harness modules). Run 14e total: ~$2 across 3 runs. **6-15× cheaper than the original $15-30 estimate** because only the Generator was sonnet — extraction/analyst/adversarial/reconciliation/scorer all defaulted to openai-mini commodity tier.

Cost-instrumentation gap noted: per-run cost is NOT captured in the result JSON (`metadata.cost_usd: None`), nor in the selfplay ledger (`data/selfplay_cost_ledger.jsonl` is stale). Estimate above is back-of-envelope from token counts and pricing. Worth a small utility phase to fix (Phase 38.5 / Phase 39 candidate).

### Run 14e transcript inspection (2026-06-11) — strategic refusal, not harness failure

**Method.** Extracted R3 + R4 `round_responses` for each faction from all 3 sonnet-full result JSONs. Pattern-matched final-position-of-record per faction per issue.

**Headline.** All 3 runs fail on `payment_structure` only — `water_release_volume` and `long_term_infrastructure` converge to High + JFD across the board. Per-run R4 final positions:

| Run | alpha (R4) | beta (R4) | gamma (R4) |
|---|---|---|---|
| 14e-1 | **Low** + Heavy-Downstream | High + **Token** | High + **Token** |
| 14e-2 | High + Heavy-Downstream | High + **Token** | High + **Shared** |
| 14e-3 | High + Heavy-Downstream | High + **Token** | High + **Token** (truncated R4) |

Alpha holds Heavy-Downstream (their #1 payment preference, scoring 10). Beta+gamma refuse it and hold Token/Shared (their #1 preferences, scoring 7 and 5). 14e-1 escalates further: alpha reverts to Low water when gamma refuses Heavy-Downstream, producing the worst no-deal of the three.

**The transcripts show explicit coalition formation, not anchoring failure.** Selected verbatim quotes:

- **Beta, 14e-3 R3:** "If we cannot reach this framework in the next round, Beta will need to reassess whether any deal beats our BATNA. Federal drought aid and crop insurance are available. **I would rather have a deal — but not at any price.**"
- **Gamma, 14e-3 R3:** "Beta, you've been consistent and credible throughout. I'm aligned with you on Volume and Infrastructure. **I'm asking you to hold firm on those two issues while I bridge the payment gap.**"
- **Alpha, 14e-1 R4:** "If Heavy-Downstream payment is confirmed by all parties, Alpha will commit to releasing High volume. If it is not confirmed, Alpha's proposal stands as Low volume with Heavy-Downstream payment — which reflects Alpha's actual economic position and BATNA."

**Re-framing.** Sonnet agents are **negotiating strategically** — beta+gamma form a credible coalition against alpha's Heavy-Downstream demand, both factions treat their BATNAs as survivable, and alpha holds firm too. The Pareto-optimal deal (alpha 16 / beta 18 / gamma 20) requires beta+gamma to accept their #2 payment choice (Heavy-Downstream) in exchange for #1 outcomes on water + infrastructure. **Sonnet refuses that trade 3/3 of the time. gpt-mini accepted it 2/3 of the time.**

**Why sonnet refuses where gpt-mini accepts** — three candidate mechanisms (not mutually exclusive):

1. **Sonnet weighs persona principles more heavily.** Beta's "not at any price," gamma's "bridge the payment gap" coalition appeal — normative framings. Sonnet may operationalize the persona's "honor your faction's priorities" rule more strictly.
2. **Sonnet is better at coalition reasoning.** Gamma explicitly identifies beta as a co-aligned faction and recruits them. Stronger long-context modeling makes this kind of strategic move more accessible.
3. **Sonnet treats BATNA as more credible.** Beta's "federal drought aid and crop insurance are available" line shows sonnet beta reasoning about fallback as a real option rather than a worst case to be avoided.

All three mechanisms point to **higher negotiation skill**, not lower. The scenario design rewards cooperative concession; sonnet's strategic capability is misaligned with that incentive structure on this specific scenario.

**What this changes about earlier conclusions:**

- **Earlier framing "the harness has a model-class fit problem"** (Finding #3 in the Cross-cell synthesis below) is **incorrect on the mechanism, correct on the outcome**. The harness fires for sonnet, intel is produced, reconciliation works — sonnet's failure to converge is not because the harness fails to reach it. It's because sonnet's strategic reasoning *uses* the harness intel to make a sound but uncooperative decision. Finding #3 retained for outcome accuracy; mechanism revised here.
- **Per-module ablation (Project-direction option 2) is now lower priority.** No single module is the bottleneck.
- **Phase 38 pressure mechanisms gain the strongest motivation yet.** Round-cost decay would make beta+gamma's coalition costly to maintain — every round at BATNA subtracts points, eventually flipping the math so accepting Heavy-Downstream beats holding out. Asymmetric clocks would force one faction to commit earlier. Both should drive sonnet toward convergence by *changing the strategic landscape*, not by suppressing strategic behavior.
- **The cost-economics recommendation "cheap+harness is the production default" needs the qualifier "on scenarios with a unique cooperative-Pareto."** For multi-Pareto or richer scenarios, sonnet's strategic capability likely flips from liability to asset.

**Highest-information cheap follow-up:** Re-run sonnet+full on a pressure-augmented Water Rights β-squeezed variant (now feasible — Phase 38 just landed pressure schema). ~$2 for 3 runs. Expected outcome if hypothesis is right: pressure-induced BATNA decay drives beta+gamma to accept Heavy-Downstream as their best remaining option; close rate climbs from 0/3 to 2-3/3. If pressure does not change the outcome, the strategic-refusal pattern is robust to the small-bundle pressure mechanisms and Phase 39 (exogenous events) becomes more relevant.

### Cross-cell synthesis (post-14e — campaign complete)

| Tier | Model | Full close-rate | Bare close-rate | Δ (full − bare) |
|---|---|---|---|---|
| Weak | `gpt-4.1-nano` | 2/3 | 0/3 | **+67%** |
| Mid | `gpt-5.4-mini` | 2/3 | 1/3 | +33% |
| **Strong** | **`claude-sonnet-4-6`** | **0/3** | **0/3** | **0%** |

**Four findings (campaign complete, 18 runs landed):**

1. **Harness contribution is in close-rate, not deal quality.** Every closing run (across both tiers, both modes) found the **identical Pareto-optimal deal**: alpha 16 / beta 18 / gamma 20, deltas `[+7, +3, +9]`. The scenario has one right answer; the model either finds it or fails entirely. (Unchanged from pre-14e.)

2. **Model strength does NOT substitute for harness on this scenario.** Bare close-rate is non-monotonic in model tier: weak 0/3, mid 1/3, strong 0/3. Mid-bare's 1/3 is the one outlier; both weak-bare and strong-bare are floored. (Unchanged from post-14d.)

3. **The harness has a model-class fit problem** — *retained for outcome accuracy; the MECHANISM is revised by the post-14e transcript inspection above*. Sonnet-full = 0/3 — *worse* than weak-full and mid-full, both at 2/3. What the transcripts actually show: sonnet's harness fires fully (intel produced, reconciliation works, 27 promises tracked in 14e-1); sonnet then *uses* that intel to make a strategically sound but uncooperative decision (beta+gamma form a credible coalition against alpha's Heavy-Downstream demand and prefer their BATNAs to conceding). Sonnet's higher capability produces strategic refusal where gpt-mini's lower capability produces reflexive cooperation. The harness is not failing to reach sonnet — sonnet is succeeding at a different objective than the scenario rewards. See the transcript-inspection subsection above for verbatim quotes and three candidate mechanisms.

4. **Bare mode is bottlenecked by the absence of structural reasoning** for OpenAI Generators (`14b` vs `14a`, `14c-bare` vs `14c-full`). For Anthropic-Generator runs the harness-vs-bare distinction collapses on outcome (sonnet-full = sonnet-bare = 0/3) — but only because sonnet's strategic-refusal behavior produces the same no-deal outcome whether it has harness intel or not. The harness IS reaching sonnet in full mode; sonnet just doesn't *use* the intel toward closing the deal.

**Caveat (per `RESEARCH_NOTES.md` Note 1):** all findings are on a **scale-1 scenario**. At richer scenarios (more factions, more issues, longer horizons, deception), the picture may shift dramatically. The sonnet-full=0/3 result specifically may invert at scale — sonnet's longer-context handling might help where nano/mid would fail. Cannot extrapolate from this campaign alone; needs Phase 41/42 (scale-matrix verification) + a follow-up ablation campaign on richer scenarios.

### Plain-language progress matrix (post-14e)

Final cell-by-cell view for non-technical / first-time readers. The detail tables above remain canonical.

**Per-cell — what each run measured:**

| Cell | What we ran | What it tests (plain language) | Outcome | Cost | Wall |
|---|---|---|---|---|---|
| 14a | Mid OpenAI + full harness | Baseline — can mid tier with full scaffolding close the deal? | **2/3** deals (66%) | ~$3-4 | ~12 min/run |
| 14b | Mid OpenAI, raw model only | Does removing the harness hurt at mid tier? | **1/3** (33%) | ~$0.50 | ~6 min/run |
| 14c-full | Cheap OpenAI + full harness | Can scaffolding lift a 10× cheaper model to mid-tier performance? | **2/3** (66%) | ~$0.15 | ~10 min/run |
| 14c-bare | Cheap OpenAI, raw model only | What does the cheapest model achieve alone? | **0/3** (0%) | ~$0.15 | ~4 min/run |
| 14d | Strong Anthropic, raw model only | Does raw model strength substitute for the harness? | **0/3** (0%) | ~$0.50 | ~8 min/run |
| 14e | Strong Anthropic + full harness | Does the harness rescue sonnet, or does the scenario have a 2/3 ceiling? | **0/3** (0%) | ~$2.00 | ~16-17 min/run |

When closing, **every** run found the *identical* Pareto-optimal deal (alpha 16 / beta 18 / gamma 20). Cells differ only in close rate, never in deal quality.

**Pairwise — what the comparisons tell us:**

| Comparison | What we learn | Result | Implication |
|---|---|---|---|
| Harness lift per tier (X-full vs X-bare) | How much does scaffolding help at this model tier? | weak +67%, mid +33%, **strong 0%** | Harness lifts OpenAI tiers materially; for sonnet, the lift collapses to zero. |
| Cheap+full vs mid+full (14c-full vs 14a) | Does harness erase a 10× model-cost gap? | Both 2/3 | **Yes** — harness lets a cheap OpenAI model match a mid OpenAI model. |
| Cheap+full vs mid+bare (14c-full vs 14b) | Is "cheap model + scaffolding" better than "mid model alone"? | 2/3 vs 1/3 | **Yes** — supports "make cheap models good enough" positioning, for OpenAI. |
| Strong-full vs cheap+full / mid+full (14e vs 14c-full / 14a) | Does the most expensive model + harness outperform cheaper alternatives? | 0/3 vs 2/3 / 2/3 | **NO — inverted.** Sonnet+full is *worse* than nano+full and mid+full. Harness doesn't compose with sonnet on this scenario. |
| Strong-full vs strong-bare (14e vs 14d) | Does the harness add anything for sonnet? | 0/3 vs 0/3 | **No measurable lift** at the strong tier. Sonnet stays at BATNA floor with or without the harness. |
| Bare-mode tier ladder | Does close rate scale with model strength when there's no harness? | weak 0/3, mid 1/3, strong 0/3 | **Non-monotonic.** Mid-bare's 1/3 likely noise; strong-bare back at zero. |

**Implied unit economics (final):**

| Configuration | $/deal-attempt | $/closed-deal at observed close rate |
|---|---|---|
| cheap + full (14c-full) | ~$0.05 | ~$0.075 (2/3 close rate) |
| mid + full (14a) | ~$1.20 | ~$1.80 (2/3 close rate) |
| strong + full (14e) | ~$0.65 | **∞ (0 deals closed)** |
| strong + bare (14d) | ~$0.17 | **∞ (0 deals closed)** |

For this scenario configuration, the recommendation is unambiguous: **cheap + harness is the production default.** Strong models with our current harness configuration are strictly worse — same zero deals, ~13× the cost.

### Follow-up questions in priority order (post-14e)

1. **Why does sonnet+full fail when nano+full and mid+full succeed?** **Answered (2026-06-11) by transcript inspection** — sonnet exhibits strategic refusal: beta+gamma form a credible coalition against alpha's Heavy-Downstream demand and prefer BATNAs to conceding their #1 payment choice. Three candidate mechanisms (persona-rule weighting, coalition reasoning, BATNA credibility) all point to higher capability, not lower. See the Run 14e transcript inspection subsection above.
2. **Does the load-bearing-harness finding generalize beyond this scenario?** Per `RESEARCH_NOTES.md` Note 1 — needs Phase 41/42 + new richer scenarios + re-ablation. The 14e=0/3 result makes this MORE important, not less: if richer scenarios show sonnet+full succeeding where simpler scenarios show it failing, that's a different story than "sonnet has a harness-fit problem."
3. **Which harness modules are doing the work?** Per-module ablation (Phase 35 candidate) to identify whether intel quality, state tracking, or reconciliation is the load-bearing piece. Pairs well with hypothesis (a) above — testing module-by-module with sonnet might localize the failure.
4. **Will Phase 38 pressure mechanisms change the picture?** Round-cost decay + asymmetric clocks + penalty floor create concession pressure independent of model. If sonnet+full+pressure reaches a deal where sonnet+full alone doesn't, that's a clean win for the pressure thesis and gives operators a knob to make scenarios more sonnet-friendly. **Test:** re-run 14e with the Phase 38 schema after authoring a pressure-augmented variant of Water Rights β-squeezed.
5. **Does the cost-economics conclusion (cheap+harness is the production default) hold beyond Water Rights?** Same Phase 41/42 + richer-scenario question, with cost-per-deal as the metric.

### Project-direction decision (post-14e — NOW LIVE)

All four options from the original Phase 34 close are now informed:

| Option | Status post-14e |
|---|---|
| 1. Continue building harness features (Tier 2/3) | **Partially supported.** Harness adds clear value for OpenAI tiers; sonnet result complicates the "always invest in harness" framing. |
| 2. Per-module ablation (Phase 35 candidate) | **Demoted (2026-06-11).** Transcript inspection ruled out harness-module failure as the mechanism. Per-module ablation would still test scale-N harness contribution per Note 1, but is no longer the leading hypothesis for the 14e=0/3 result. |
| 3. Pivot to "Diplomat-lite" minimal-harness | **Refuted.** Bare-mode close rates (0/3, 1/3, 0/3) are catastrophic vs full-mode (2/3, 2/3, 0/3). Harness IS load-bearing for OpenAI. Sonnet failing both ways doesn't refute that. |
| 4. Validate scaling thesis first (Phase 41/42 + new scenarios) | **Strongly promoted.** Scale-1 scenario showed a counter-intuitive result; richer scenarios are necessary to know whether the pattern persists, inverts, or compounds. |

**Recommended next-phase ordering (post-transcript-inspection):**
- **Sonnet+full+pressure re-test** is now the single highest-leverage next experiment (~$2 for 3 runs). Phase 38 just landed pressure schema. Author a pressure-augmented Water Rights β-squeezed variant; re-run cells 14e-1/2/3 with `round_cost` decay enabled. Expected outcome if the strategic-refusal interpretation is correct: BATNA erodes round-over-round, beta+gamma's coalition becomes uneconomic, close rate climbs from 0/3 toward 2-3/3. If pressure doesn't help, the mechanism is something else and Phase 39 (exogenous events) gains weight.
- **Hypothesis (c) further transcript inspection** — also zero-cost. Compare 14e R3→R4 transitions against Run 10's gpt-4.1-mini R3→R4 defection pattern. Different shape (refusal vs defection) but worth pattern-matching.
- **Phase 41 (scale-matrix verification)** is independent and still enables the richer-scenario ablation needed to test whether sonnet's strategic capability flips from liability to asset at scale.

**Results files (Run 14e):**
- `tests/self_play/results/run14_full_claudesonnet46_beta_squeezed_{1,2,3}.json`

**Results files (full campaign):**
- `tests/self_play/results/run14_full_gpt54mini_beta_squeezed_{1,2,3}.json`
- `tests/self_play/results/run14_bare_gpt54mini_beta_squeezed_{1,2,3}.json`
- `tests/self_play/results/run14_full_gpt41nano_beta_squeezed_{1,2,3}.json`
- `tests/self_play/results/run14_bare_gpt41nano_beta_squeezed_{1,2,3}.json`
- `tests/self_play/results/run14_bare_claudesonnet46_beta_squeezed_{1,2,3}.json`
- `tests/self_play/results/run14_full_claudesonnet46_beta_squeezed_{1,2,3}.json`

---

## Run 15 - Joint Space Mission (calibration) - COMPLETE

Fired 2026-06-11 to test the Note 1 thesis prediction emerging from Run 14e transcript inspection: **"sonnet may be the right model for richer scenarios; sonnet's failure on Water Rights beta-squeezed may invert on multi-Pareto scenarios."** Two single-cell calibration runs on `joint_space_mission_v1` (3 distinct Pareto deals, pareto_outcome_diversity=0.66, symmetric BATNAs).

### Calibration cells (initial n=1, 2026-06-11)

| Cell | Model | Outcome | Surplus | Deal |
|---|---|---|---|---|
| 15-calib-mid | gpt-5.4-mini full | **NO-DEAL** (all at BATNA) | 0.000 | none |
| 15-calib-sonnet | claude-sonnet-4-6 full | **PARETO DEAL** | 1.000 | Exploration-Priority + Joint-Build + Equal-Thirds |

Sonnet's deal: alpha=19 (+8 vs BATNA), beta=18 (+9), gamma=22 (+10). The "balanced consensus" Pareto point — every faction at >=86% of max, highest-logrolling-quality deal on the frontier.

### Run 15 expansion (n=3 + gemini probe, 2026-06-11)

| Cell | Model | n | Close rate | Cost | Wall (per run) |
|---|---|---|---|---|---|
| 15-mid | gpt-5.4-mini full | 3 | **0/3** | ~$1.50 | ~12 min |
| 15-sonnet | claude-sonnet-4-6 full | 3 | **3/3** | ~$6 | ~16-17 min |
| 15-gemini | gemini-2.5-flash-lite full | 1 | **0/1** | ~$0.05 | ~5 min |

**Zero variance within each cell.** Every sonnet run found the *identical* Pareto deal (Exploration-Priority / Joint-Build / Equal-Thirds, same scores 19/18/22). Every gpt-mini run failed identically (alpha=11/beta=9/gamma=12 at BATNA, same pareto_efficiency 0.542). This is itself a notable data point — either temp=0 determinism, strong attractors per model class, or coincidence at small n.

**Sonnet found the SAME Pareto deal 3/3 times** — not different deals across runs. The multi-Pareto landscape (3 distinct Pareto deals available) didn't produce skill-discrimination via *outcome diversity* — sonnet converged on the balanced-consensus point every time. The original goal of "different agents pick different deals" did NOT materialize from a multi-Pareto scenario alone.

### Transcript inspection (post-expansion, 2026-06-11)

Inspected R3 + R4 messages from all 4 gpt-mini runs (1 calibration + 3 expansion) and the 1 gemini run to identify failure modes. Findings sharpened the earlier framing significantly.

**gemini-2.5-flash-lite failure mode (n=1):**

1. **Identity-tracking failure.** Gamma's final R4 sentence: *"We urge both Beta and Gamma to accept this proposal..."* — Gamma asking itself to accept its own proposal. The model lost faction identity across the 4-round context.
2. **R3→R4 position defection** (same pattern as gpt-4.1-mini Run 10). Near-convergence opportunity at R3 (alpha conceded Gamma-Lead on hardware, all three trending toward Equal-Thirds funding) was killed at R4 when alpha simultaneously pulled back on hardware AND abandoned Equal-Thirds for Government-Heavy.
3. **Zero promises post-reconciliation.** `final_state.promises` shows 0/0/0 — the reconciler merged everything as "duplicate / superseded" because positions kept shifting. Promise count was 2/6/2 mid-game per the run summary; reconciliation collapsed it.
4. **Short messages.** R1 messages ~620 chars (alpha+beta), ~120 chars (gamma) — much shorter than gpt-mini or sonnet runs. Under-engagement contributed to the failure.

**gpt-5.4-mini failure mode (n=3):**

| Run | hardware R4 | funding R4 | mission R4 | Concession trajectory |
|---|---|---|---|---|
| mid-1 | **Joint-Build** unanimous | alpha:Government-Heavy / beta+gamma:Equal-Thirds | alpha+gamma:Exploration / beta:Science | gamma made Commercial→Exploration big concession in R3→R4 |
| mid-2 | **Joint-Build** unanimous | **Equal-Thirds** unanimous | alpha:Exploration / beta+gamma:Science | gamma made Commercial→Science big concession |
| mid-3 | **Joint-Build** unanimous | **Equal-Thirds** unanimous | alpha:Exploration / gamma:Commercial / beta:"Science OR Commercial" (hedged) | alpha made Government-Heavy→Equal-Thirds concession |

1. **Identity tracking: CLEAN.** No self-referential urging across any of the 3 runs. Mid-tier OpenAI keeps faction identity across the context window.
2. **Convergence on 2 of 3 issues every run.** `hardware_lead = Joint-Build` is unanimous in all 3 runs. `funding_split = Equal-Thirds` is unanimous in 2 of 3.
3. **Convergence failure is `mission_objective` only** — parallel to Water Rights' payment_structure failure mode.
4. **Substantive R3→R4 concessions in the RIGHT direction.** Gamma conceded Commercial→Exploration (toward alpha) in run 1, Commercial→Science (toward beta) in run 2; alpha conceded Government-Heavy→Equal-Thirds in run 3. These are real strategic moves, not gemini-style position drift.
5. **No R3→R4 defection pattern.** Positions move toward convergence or hold; they don't bounce around.
6. **Run mid-3 beta hedged with "Science-Priority OR Commercial-Tech-Demo"** in the final-round binding statement — a failure to commit (one instance across the 3 runs).

**The two failure modes are categorically different:**

| Model | Failure mode |
|---|---|
| gemini-flash-lite | **Low-tier quality failure** — identity confusion + R3→R4 position drift + 0 promises post-reconciliation. The model isn't capable enough to play coherently. |
| gpt-5.4-mini | **Substantive negotiation failure** — converges on 2/3 issues, makes correct-direction concessions, can't close the last 1-issue gap. Mid-tier "stuck-but-engaged" pattern, structurally similar to sonnet-on-Water-Rights. |
| claude-sonnet-4-6 | **Success** — converges on all 3 issues. Found a balanced deal where beta+gamma both accept alpha's preferred mission in exchange for Joint-Build + Equal-Thirds going their way. |

### Headline observation — revised post-inspection

The naive matrix reading was "the pattern from Run 14 inverts": gpt-mini wins Water Rights, sonnet wins jsm1. **Transcript inspection makes the picture more nuanced:**

- **Both gpt-mini and sonnet do substantive negotiation on jsm1**, converging on 2 of 3 issues. The 0/3 vs 3/3 close-rate gap between mid and sonnet on jsm1 came down to sonnet's ability to **coordinate beta+gamma's move toward alpha's preferred mission** in exchange for the other 2 issues going their way. Mid-tier OpenAI got most of the way there but couldn't make that final coordination move.
- **Same model, opposite outcomes across scenarios** (sonnet 0/3 Water Rights vs 3/3 jsm1) is now interpretable: sonnet's capability **lets it optimize its strategy for whatever the scenario rewards**. On Water Rights (single Pareto, requires asymmetric concession), sonnet's strategic reasoning rejected the trade. On jsm1 (multi-Pareto, multiple acceptable options), sonnet found a Pareto deal where everyone gets something they want.
- **Gemini-flash-lite's 0/1 doesn't fit the same comparison frame.** Its failure is a quality-floor problem, not a strategy / model-class issue. To get a fair Google data point we need a more capable Gemini.

The earlier "inversion of the Run 14 pattern" framing was directionally right but the mechanism is more specific than "sonnet handles complexity better." The right framing is closer to "**sonnet's capability lets it find scenario-appropriate strategies; mid-tier and weaker models lock into one mode of negotiation that succeeds or fails depending on whether it fits the scenario.**"

### Implications — revised post-inspection

1. **Model-class fit depends on scenario rewards, not just model capability or scenario complexity.** Sonnet's strategic capability is an asset on multi-Pareto scenarios (where coordinated trades pay off) and a liability on single-Pareto cooperative scenarios (where reflexive concession is needed). This is *consistent with* the RESEARCH_NOTES.md Note 1 thesis (harness contribution grows with complexity) but more specific.

2. **Mid-tier OpenAI lands close-but-not-quite on jsm1.** Converges on 2/3 issues; can't get the third. With slight scenario tuning (lower coordination cost on the mission issue?) or with pressure mechanisms (Phase 38) that force concession, mid-tier could plausibly close. Worth testing.

3. **Gemini-flash-lite is below the capability floor for this scenario.** Single run shows identity confusion + position drift — basic generation-quality issues. The flash-lite result doesn't tell us about Google-vs-OpenAI/Anthropic; it tells us flash-lite isn't capable enough to be in this comparison.

4. **The "multi-Pareto produces outcome diversity" hypothesis didn't pan out.** Sonnet found the SAME Pareto deal 3/3 runs — the balanced-consensus point with highest logrolling quality. The scenario has multiple Pareto deals available but agents (at least sonnet) converge on one strong attractor. The original "different agents pick different deals" goal needs different scenario design — maybe scenarios where the consensus deal is *not* dramatically better than the alternatives.

5. **The scenario+persona pipeline works end-to-end.** Reverse builder (Phase 35-37) → LLM-fill narrative → personas → self-play with no manual intervention. Phase 39 queued to promote the one-off fill script.

### Proposed next tests (post-inspection)

| Test | Cost | Wall | Isolates |
|---|---|---|---|
| **N1** claude-haiku-4-5 full × 1 | ~$0.30 | ~8 min | Does another Anthropic model close jsm1, or is it sonnet-specific? Cheapest single-experiment distinguisher. |
| **N2** gemini-2.5-flash full × 1 | ~$1 | ~12-15 min | Does more-capable Gemini reach gpt-mini's "stuck-but-engaged" level, sonnet's "close it" level, or stay at flash-lite's quality floor? Fair Google data point. |
| **N3** gpt-4.1-nano full × 1 | ~$0.15 | ~5 min | Does weak-tier OpenAI fail like flash-lite (low quality) or like gpt-mini (substantive-but-stuck)? Tells us where the OpenAI capability floor for this scenario sits. |
| **N4** Re-test 15-mid × 3 with `pressure_profile` engaged (Phase 38 mechanisms) | ~$1.50 | ~36 min | Does adding round-cost decay push mid-tier OpenAI over the convergence threshold on the one stuck issue? Cleanest test of Phase 38's value on a scenario where mid is *almost* closing. |
| **N5** Author jsm1-v2 with smaller logrolling-quality spread between Pareto deals | $0 build + ~$5 test | ~70 min | Probe whether the "sonnet picks same Pareto every time" result is a property of THIS spec (balanced-consensus point is too attractive) or a general property of sonnet. |

Ranking by information-per-dollar: **N1 → N2 → N3 → N4 → N5**. N1 isolates Anthropic-vs-others; N2 fixes the unfair Google comparison; N4 directly tests Phase 38's value with the cleanest available signal (mid is *almost* closing on jsm1, pressure may finish the job).

### Process notes

- **The scenario+persona pipeline works end-to-end:** reverse builder produces scoring tables + stubs (Phase 35-37) → LLM-fill produces logrolling + deception_tactics (one-off `tools/_temp_fill_narrative.py` script; Phase 39 promotes this to a `scenario_authoring.scenario_compiler --fill-narrative` mode) → personas re-rendered automatically → `run_simulation --analysis-json --scenario <md>` consumes the result with no other changes.
- **The scenario .md file** (`scenarios/joint_space_mission.md`) is the moderator's seed message at game start; required by `run_simulation`. Authored by operator with NASA-style/ESA-style/commercial framing matching the LLM-fill domain context.
- **`tools/_temp_run_jsm1_calib.sh`** is the working dispatcher script for Run 15 cells. Equivalent of `tools/ablation.sh` but for `joint_space_mission_v1`. Should be folded into a generalized `ablation.sh --scenario <dir>` mode as a small future cleanup.

### Results files (Run 15, full set)

- `tests/self_play/results/run15_calib_gpt54mini_jsm1_{1,2,3}.json`
- `tests/self_play/results/run15_calib_claudesonnet46_jsm1_{1,2,3}.json`
- `tests/self_play/results/run15_calib_gemini25flashlite_jsm1_1.json`

---

## Run 16 — Joint Space Mission ablation matrix — COMPLETE

Fired 2026-06-12 over ~48 minutes wall clock. Goal: fill in the bare-mode cells on jsm1 + add weak-full to produce a parallel matrix to Run 14's Water Rights β-squeezed campaign. Direct test of `RESEARCH_NOTES.md` Note 1 thesis on a scenario richer than scale-1 along the multi-Pareto axis.

### Hypothesis

Note 1 predicts that harness contribution should grow with scenario complexity. jsm1 is richer than Water Rights β-squeezed on the multi-Pareto axis (3 distinct Pareto deals vs 1 unique Pareto). The sharpest single-cell test is **sonnet-bare on jsm1**: if Note 1 is right, sonnet-bare should drop relative to sonnet-full (harness becomes load-bearing on richer scenarios). If sonnet-bare = sonnet-full, the "scale-N harness becomes load-bearing for sonnet" story is at least partially wrong for this axis at this scale.

### Configuration

- Scenario: `joint_space_mission_v1` (3 distinct Pareto deals, `pareto_outcome_diversity=0.66`, symmetric BATNAs).
- Cells (cheap-first ordering per RUN_PROTOCOL): nano full × 3 → nano bare × 3 → gpt-mini bare × 3 → sonnet bare × 3. 12 runs total.
- Dispatcher: `tools/ablation_jsm1.sh` (parallel to `tools/ablation.sh`, fixed to jsm1 scenario). Driver: `tools/_run_jsm1_matrix.sh`.
- Pre-flight: probes (3/3 passed for each of nano, gpt-5.4-mini, sonnet); dry-run on nano-bare jsm1 (first-ever bare+jsm1 combination) confirmed `bare_mode=True` in metadata + 21 transcript entries + 4 rounds.
- Cost: ~$1.50 total (vs $20-40 for Run 14). Wall clock: 48 min (vs ~50 min estimated; nano cells were ~3 min each, sonnet-bare cells ~6 min each).

### Cell results

| Cell | Model | Mode | Deal? (n=3) | When closing |
|---|---|---|---|---|
| 16-nano-full | gpt-4.1-nano | full | **1/3** | identical balanced-consensus `{α:8, β:9, γ:10}` |
| 16-nano-bare | gpt-4.1-nano | bare | **0/3** | — (all at BATNA floor) |
| 16-mid-bare | gpt-5.4-mini | bare | **0/3** | — (all at BATNA floor) |
| 16-sonnet-bare | claude-sonnet-4-6 | bare | **3/3** | identical balanced-consensus `{α:8, β:9, γ:10}`, zero variance |

All three sonnet-bare runs found `{funding_split: Equal-Thirds, hardware_lead: Joint-Build, mission_objective: Exploration-Priority}` → alpha 19 / beta 18 / gamma 22. Identical to Run 15 sonnet-full results — same agreed_outcomes dict, same scores, same `negotiated_surplus_share=1.000`.

### Cross-scenario synthesis (Water Rights β-squeezed + jsm1)

Full matrix with both campaigns combined:

| Tier | Model | WR-β full | WR-β bare | jsm1 full | jsm1 bare |
|---|---|---|---|---|---|
| Weak | gpt-4.1-nano | 2/3 | 0/3 | 1/3 | 0/3 |
| Mid | gpt-5.4-mini | 2/3 | 1/3 | 0/3 | 0/3 |
| **Strong** | **claude-sonnet-4-6** | **0/3** | **0/3** | **3/3** | **3/3** |

Harness lift per cell (full − bare close rate):

| Tier | WR-β lift | jsm1 lift |
|---|---|---|
| Weak | +67% (2/3 vs 0/3) | +33% (1/3 vs 0/3) |
| Mid | +33% (2/3 vs 1/3) | 0% (0/3 vs 0/3) |
| Strong | 0% (0/3 vs 0/3) | 0% (3/3 vs 3/3) |

### Four findings

1. **Sonnet does not need the harness on jsm1.** sonnet-bare = sonnet-full = 3/3, identical deal every run, zero variance across all six sonnet runs combined. **This is the load-bearing finding.** It partially refutes Note 1's thesis as written: jsm1 is richer than WR-β on the multi-Pareto axis, yet sonnet's harness contribution went from 0 (WR-β) to 0 (jsm1) — not from "small on simple scenario" to "large on rich scenario" as the thesis predicted. See Note 1 amendment 2026-06-12. **Caveat (added 2026-06-16):** "0 → 0" overstates the cleanliness of this. Both sonnet cells are *saturated* — WR-β at the floor (full 0/3 = bare 0/3, via strategic refusal) and jsm1 at the ceiling (full 3/3 = bare 3/3) — so neither cell has headroom to reveal a harness *lift*. Sonnet therefore contributes no usable evidence on whether harness contribution grows with richness; the refutation actually rests on the weak/mid tiers (which do have headroom) plus the *absence* of a ceiling-breaking effect at strong tier. Separately, the strong tier is the only Anthropic cell, so "strong-tier" and "Anthropic" effects are entangled — a same-provider tier ladder is needed to separate them.

2. **Determinism question answered: scenario attractor, not harness anchoring.** Sonnet picked the same balanced-consensus point in all 3 bare runs *and* all 3 full runs from Run 15 — six identical deals across two modes. Hypothesis "the harness anchors sonnet on balanced-consensus" is refuted; the attractor lives in the scenario's scoring topology, not in any harness module.

3. **Mid-tier failure on jsm1 is harness-immune.** gpt-5.4-mini bare 0/3 + gpt-5.4-mini full 0/3 (from Run 15). The "stuck-but-engaged" pattern (substantive 2/3-issue convergence, can't bridge the last) is reproduced under bare mode. The harness is not what's keeping mid coherent — mid is coherent enough under bare mode to fail in the same shape. Mid simply can't close the last issue regardless of harness intel.

4. **Weak-tier harness lift is scenario-dependent.** Nano-full gives +67% lift over nano-bare on WR-β but only +33% on jsm1. When weak tier closes on jsm1 (1/3), it finds the identical balanced-consensus deal sonnet finds (scores match exactly). So weak tier *can* hit the answer with harness help on jsm1, just less reliably than on WR-β. The harness is still load-bearing for weak tier, but its yield depends on whether the scenario rewards the kind of reasoning the harness's analyst intel supports.

### Re-framing: "harness contribution" is a function, not a number

The pre-Run-16 framing assumed harness contribution had a single sign — positive (with magnitude varying by tier and scenario). Run 16 makes that wrong: at strong tier on jsm1, harness contribution is *exactly* zero. The cleanest re-statement is:

> **Harness contribution = f(scenario shape, what the model already does well).** When the scenario rewards reasoning the model finds naturally — sonnet on multi-Pareto coordination — the harness is redundant. When the scenario rewards reasoning the model needs scaffolding to surface — weak/mid OpenAI finding asymmetric concessions on WR-β — the harness is load-bearing. The Note 1 axes (context, relationships, deception, horizon, persona drift) are five dimensions of "scenario shape," but they predict harness lift only insofar as they pick out reasoning the model can't do unaided.

This is a strictly weaker thesis than "harness contribution grows with complexity," but it's the one supported by the data.

### Implications for project direction

- **Production-default recommendation now scenario-dependent.** On cooperative-single-Pareto (WR-β shape): **cheap+harness** (nano-full at ~$0.05/run, 2/3 close). On multi-Pareto (jsm1 shape): **strong+bare** (sonnet-bare at ~$0.30/run, 3/3 close). The earlier "cheap+harness is the production default" recommendation from the Run 14e wrap is correct in context but does not generalize.
- **Per-module ablation (Phase 35 candidate) further demoted.** Sonnet-bare = sonnet-full on jsm1 means no single harness module can be load-bearing for sonnet on jsm1 — removing the entire harness produces no behavior change. Per-module ablation would still test whether *any* module helps weak/mid tiers specifically, but its leverage drops sharply now that we have two-scenario evidence harness contribution can be zero at strong tier.
- **Phase 38 pressure mechanisms now the highest-leverage next experiment.** Mid-tier jsm1 is the sharpest residual mystery: 0/3 in both modes, but transcripts show substantive 2/3-issue convergence with concrete-direction concessions. The only remaining lever we haven't tried is *changing the strategic landscape* (round-cost decay, asymmetric clocks) to push mid past the last-issue gap. N4 below.
- **Note 1's other four axes (context, relationships, deception, horizon) remain untested.** Run 16 only varies multi-Pareto vs single-Pareto. The Note 1 amendment captures what jsm1 did and didn't validate.

### Proposed next tests (post-Run-16, priority order)

| Test | Cost | Wall | Why |
|---|---|---|---|
| **N4** gpt-mini full + Phase 38 pressure × 3 on jsm1 | ~$1.50 | ~36 min | Cleanest single experiment now. Mid is *almost* closing on jsm1; harness doesn't help; pressure is the un-tried lever. Phase 38 schema just landed and needs a real test. |
| **N4b** sonnet full + Phase 38 pressure × 3 on WR-β | ~$2 | ~50 min | Carried from Run 14e follow-up. Tests strategic-refusal mechanism: if pressure converts sonnet 0/3 → 2-3/3 on WR-β, the "BATNA-survivable coalition" mechanism wins; if no change, persona-rule weighting is more likely. |
| **N1+** claude-haiku-4-5 × 3 on jsm1 (full + bare) | ~$1 | ~25 min | Does the harness-zero behavior generalize across Anthropic models, or is it sonnet-specific? Combined with bare-mode, isolates Anthropic-default vs sonnet-default. |
| **N2** gemini-2.5-flash × 3 on jsm1 (full + bare) | ~$2 | ~50 min | Stronger Google data point. Does flash also exhibit harness-zero behavior, or does flash sit in the mid-tier "stuck-but-engaged" pattern? |
| **N5** jsm-v2 with smaller logrolling-quality spread | $0 + ~$5 test | ~70 min | Is the "sonnet picks same Pareto every run" pattern spec-specific or sonnet-general? Probe whether weakening the balanced-consensus attractor produces outcome diversity. |

### Process notes

- **`tools/ablation_jsm1.sh`** is the canonical jsm1 ablation dispatcher (mirror of `tools/ablation.sh` for jsm1, supports `full|bare`). Output naming: `run16_<mode>_<modeltag>_jsm1_<n>.json`.
- **`tools/_run_jsm1_matrix.sh`** is the matrix driver (probes + cheap-first cell ordering + summary). Reusable for future jsm1 ablation campaigns by editing the `cells` array.
- **Generalized ablation surface** (per Run 15 process notes) — both `ablation.sh` and `ablation_jsm1.sh` could fold into a single `ablation.sh --scenario <dir>` mode. Small future cleanup; both work as-is.
- **Dry-run bare-jsm1 was the first-ever combination** tested. Plumbing held (no jsm1-specific bare-mode bugs surfaced); validates that `bare_module_overrides()` is genuinely scenario-agnostic.
- **Cost-instrumentation gap noted in Run 14e persists.** Per-run cost still NOT captured in result JSONs. Phase 38.5 / 39 candidate worth promoting given Run 16's cell cost estimates are back-of-envelope.

### Results files (Run 16, full set)

- `tests/self_play/results/run16_full_gpt41nano_jsm1_{1,2,3}.json`
- `tests/self_play/results/run16_bare_gpt41nano_jsm1_{1,2,3}.json`
- `tests/self_play/results/run16_bare_gpt54mini_jsm1_{1,2,3}.json`
- `tests/self_play/results/run16_bare_claudesonnet46_jsm1_{1,2,3}.json`
- Driver logfile: `/tmp/jsm1_matrix_20260612_002502.log` on Pi (retained until container restart).

---

## Run 17 — Multi-provider calibration (DeepSeek V3 + Llama 3.3; R1 deferred) — COMPLETE (with scope changes)

Fired 2026-06-12 as the first multi-provider campaign — extends the matrix to OpenRouter-routed models (DeepSeek V3, DeepSeek R1, Llama 3.3 70B). Two intertwined goals: (a) test whether the Run 14/16 patterns generalize beyond US frontier labs (OpenAI, Anthropic), and (b) de-facto pilot the toolkit's OpenRouter integration in self-play, which had not been exercised before. The campaign's scope changed mid-flight when R1 surfaced a toolkit-side wiring gap.

### Initial plan (locked 2026-06-12 ~04:17 UTC)

3 models × 2 scenarios × n=1 full mode = 6 cells, ~$2 estimated, ~60 min. Models: `deepseek/deepseek-chat` (V3, strong non-reasoning), `deepseek/deepseek-r1` (reasoning), `meta-llama/llama-3.3-70b-instruct` (open-weight). Scenarios: jsm1 + Water Rights β-squeezed.

Pre-flight: 9/9 probes passed (3 models × 3 factions). All three models confirmed reachable via OpenRouter with paid credits.

### What actually happened

- **Cells 1-2 (DeepSeek V3, both scenarios):** completed cleanly. V3 jsm1 full closed the balanced-consensus deal (identical to sonnet's `{α:8, β:9, γ:10}`); V3 wrbeta full hit BATNA.
- **Cell 3 (DeepSeek R1 jsm1):** ran 70 minutes with only 7 seconds of CPU time and zero active network sockets before being killed. Process diagnostics revealed a stuck retry loop — direct OpenRouter probing then surfaced the underlying wiring gap (see "Toolkit wiring discovery" below).
- **Cells 3-4 (R1 jsm1 + wrbeta):** deferred. Sequential driver killed; R1 cells skipped to unblock the rest of the campaign.
- **Cells 5-6 (Llama 3.3 70B, both scenarios):** completed (~12 min each, Parasail backend; significantly slower than V3 cells). Both hit BATNA at n=1.
- **Mid-flight expansion:** with R1 cells killed and the campaign budget unused, expanded DeepSeek V3 to bare mode n=3 on both scenarios (6 extra cells). Cheap (~$0.30) and produces enough samples for a proper cross-mode read on V3.

### Final cells (10 total landed; 2 deferred)

| Cell | Model | Scenario | Mode | n | Outcome | Cost (rough) |
|---|---|---|---|---|---|---|
| 17.1 | deepseek/deepseek-chat | jsm1 | full | 1 | **DEAL** `{α:8, β:9, γ:10}`, surplus=1.0 | ~$0.10 |
| 17.2 | deepseek/deepseek-chat | wrbeta | full | 1 | No deal (BATNA) | ~$0.10 |
| 17.3 | deepseek/deepseek-r1 | jsm1 | full | — | **KILLED** (toolkit wiring gap; see below) | $0 (no output) |
| 17.4 | deepseek/deepseek-r1 | wrbeta | full | — | **SKIPPED** | $0 |
| 17.5 | meta-llama/llama-3.3-70b-instruct | jsm1 | full | 1 | No deal | ~$0.10 |
| 17.6 | meta-llama/llama-3.3-70b-instruct | wrbeta | full | 1 | No deal | ~$0.10 |
| 17.7 | deepseek/deepseek-chat | jsm1 | bare | 1 | **DEAL** `{α:8, β:9, γ:10}`, surplus=1.0 | ~$0.05 |
| 17.8 | deepseek/deepseek-chat | jsm1 | bare | 2 | No deal | ~$0.05 |
| 17.9 | deepseek/deepseek-chat | jsm1 | bare | 3 | No deal | ~$0.05 |
| 17.10 | deepseek/deepseek-chat | wrbeta | bare | 1 | No deal | ~$0.05 |
| 17.11 | deepseek/deepseek-chat | wrbeta | bare | 2 | No deal | ~$0.05 |
| 17.12 | deepseek/deepseek-chat | wrbeta | bare | 3 | No deal | ~$0.05 |
| 17.13 | deepseek/deepseek-r1 | jsm1 | full | 1 | **DEAL** `{α:8, β:9, γ:10}`, surplus=1.0 (post-toolkit-fix, watchdog-capped) | ~$0.05 |

**Per-cell summary:**

| Model | Scenario | full close | bare close | Δ (full − bare) |
|---|---|---|---|---|
| deepseek-chat (V3) | jsm1 | 1/1 | 1/3 | +66% (n caveats) |
| deepseek-chat (V3) | wrbeta | 0/1 | 0/3 | 0% (both floored) |
| llama-3.3-70b | jsm1 | 0/1 | — | — |
| llama-3.3-70b | wrbeta | 0/1 | — | — |
| deepseek-r1 | (both) | DEFERRED | DEFERRED | — |

### Toolkit wiring discovery (sub-deliverable, shipped as toolkit `606e309`)

The R1 hang led to direct probes of how OpenRouter routes each model and what response shape each backend returns:

| Model | Backend (observed) | `content` populated? | `reasoning` populated? |
|---|---|---|---|
| `deepseek/deepseek-chat` | StreamLake | ✓ | N/A |
| `deepseek/deepseek-r1` | Azure | **✗ (None)** | ✓ |
| `deepseek/deepseek-r1-distill-llama-70b` | Novita | **✗ (None)** | ✓ |
| `qwen/qwen3-32b` | DeepInfra | **✗ (None)** | ✓ |
| `meta-llama/llama-3.3-70b-instruct` | Parasail | ✓ | N/A |
| `openai/o4-mini` | OpenAI | ✓ | (merged server-side) |

**Pattern:** every reasoning model routed to a non-OpenAI backend on OpenRouter returns its answer in `choice.message.reasoning` (or `reasoning_content`) with the standard `content` field empty or `None`. OpenAI's own o-series via OpenRouter's OpenAI passthrough merges thinking into content server-side, hiding the issue. Toolkit's `OpenRouterProvider.call()` only checked `content`, raised `LLMResponseError("Empty content")`, and `complete_with_retry(retry_on_empty=True)` silently retried indefinitely — producing the R1 hang.

**Fix:** patched `OpenRouterProvider.call()` to fall back to `reasoning` / `reasoning_content` when `content` is empty, before raising. Committed as toolkit `606e309` (pushed to `origin/master` 2026-06-12). Three new unit tests in `TestOpenRouterProvider`; all 64/64 `llm_client` tests pass. Documented in toolkit `VALIDATION_NOTES.md` + `ARCH_llm_client.md`. R1 cell #1 (17.13, jsm1) re-launched + landed before watchdog cap — see "Run 17 closure" subsection below. Remaining 5 R1 cells queued as Tier 1 follow-up per `NEXT_STEPS.md`.

### Cross-scenario × cross-mode picture (Runs 14 + 16 + 17 combined)

| Tier | Model | WR-β full | WR-β bare | jsm1 full | jsm1 bare | jsm1 harness lift |
|---|---|---|---|---|---|---|
| Weak | gpt-4.1-nano | 2/3 | 0/3 | 1/3 | 0/3 | +33% |
| Mid | gpt-5.4-mini | 2/3 | 1/3 | 0/3 | 0/3 | 0% |
| **Mid+ (Chinese)** | **deepseek-v3** | **0/1** | **0/3** | **1/1** | **1/3** | **+66% (n caveats)** |
| Strong | claude-sonnet-4-6 | 0/3 | 0/3 | 3/3 | 3/3 | 0% |
| Floor (open-weight, n=1) | llama-3.3-70b | 0/1 | — | 0/1 | — | — |

V3 inserts cleanly into a new "mid+" tier between gpt-mini and sonnet — *better than mid OpenAI on jsm1* (1/3 vs 0/3 bare; 1/1 vs 0/3 full) but *worse than sonnet on jsm1* (1/3 vs 3/3 bare). Different behavior shape on wrbeta though — V3 patterns with **strong tier** (refusal in both modes, 0/4), not with mid tier (cooperation in 2/3 + 1/3 cases).

### Four findings

1. **DeepSeek V3 is hybrid: sonnet-like on wrbeta, mid+-tier on jsm1.** This is the load-bearing finding from Run 17. V3 has enough strategic capability to *refuse* asymmetric concession on wrbeta (matches sonnet's pattern) but not enough to proactively *coordinate* on balanced consensus on jsm1 without harness intel (where sonnet is 3/3 bare). The pattern *strengthens* the `RESEARCH_NOTES.md` Note 2 framing — model behavior depends on what cognitive function the scenario rewards, and these can dissociate within the same model.

2. **Cross-provider Pareto convergence.** When V3 closed on jsm1 (full 1/1 + bare 1/3), it found the *identical* `{α:8, β:9, γ:10}` deal sonnet finds. Combined with nano-full's 1/3 on the same deal, **three different providers (Anthropic, OpenAI, Chinese) all converge on the same Pareto point when they close on jsm1.** The scenario attractor is genuinely model-independent.

3. **Llama 3.3 70B looks below capability floor** at n=1 (0/2). Pattern matches gemini-flash-lite's 0/1 (low-tier quality failure). Could be n=1 noise — needs n=3 expansion to confirm. Worth a transcript inspection before promoting to n=3.

4. **Reasoning-model wiring on OpenRouter is systemic.** R1 hang was not R1-specific; same empty-content behavior on R1-distill (Novita), Qwen3 (DeepInfra). Only OpenAI-routed reasoning models (`openai/o4-mini`) return standard content. Implication: any future reasoning-model work via OpenRouter needs the toolkit `606e309` fallback OR per-model `include_reasoning: True` plumbing — both work; fallback is the more general fix.

### Cost-economics revision (sharpens post-Run-16 production-default recommendation)

Earlier post-Run-16 read: *"cheap+harness is the production default on cooperative-single-Pareto, strong+bare on multi-Pareto."*

Post-Run-17 refinement:

| Scenario shape | Production default | Why |
|---|---|---|
| Single-Pareto requiring asymmetric concession (WR-β) | **deepseek-v3** at ~$0.10/run | Same refusal behavior as sonnet at ~10× lower cost. Sonnet's strategic capability is not adding anything sonnet-specific here — V3 captures it. |
| Multi-Pareto with balanced-consensus attractor (jsm1) | **claude-sonnet-4-6 bare** at ~$0.30/run | Still sonnet-only at this scenario shape — V3 jsm1 bare is 1/3, sonnet bare is 3/3. The harness doesn't close the gap for V3 either (V3 jsm1 full only 1/1 at n=1; likely the gap holds at n=3). |
| Mid-OpenAI's "stuck-but-engaged" pattern (jsm1) | unresolved | Phase 38 pressure (N4) is the untested lever. |

The cost-economics implications scale with how many of each scenario shape Diplomat actually faces in production. If most real-world scenarios are wrbeta-shape (asymmetric distributive), V3 wins decisively. If most are jsm1-shape (multi-Pareto coordination), sonnet wins by close-rate.

### Implications for project direction

- **V3 is the new candidate provider** for the per-role model strategy (NEXT_STEPS §7) — fills the "cost-tier between gpt-mini and sonnet" slot that previously didn't exist with the OpenAI/Anthropic-only matrix.
- **Mixed-model populations now have a viable cost-tier intermediate.** NEXT_STEPS §11.b's proposed Three-Party Coalition lineup (sonnet + gpt-mini + ?) now has a natural ? — **DeepSeek V3** — that gives three distinct provider/training-distribution classes (Anthropic, OpenAI, Chinese) at three different cost points.
- **R1 cells worth running once reasoning-model signal is the goal.** Toolkit unblocked. ~$2-4 for n=3 on both scenarios at ~16-20 min/cell. Open question: does R1 exhibit V3's hybrid pattern, sonnet's strong pattern, or something new (reasoning-specific behavior like longer concession sequences)?
- **OpenRouter integration is now battle-tested** for non-reasoning models. The wiring discovery → fix loop validated the toolkit's extensibility for new provider routes. Future model additions are now "just add to the probe-matrix" rather than "discover a new toolkit gap each time."
- **Llama needs follow-up** before being written off — n=1 is noise. Either expand to n=3 (~$1, ~30 min) or transcript-inspect the existing 2 cells to check whether it's quality-floor or scenario-fit.

### Process notes

- **`tools/ablation_multi.sh` shipped** as the generalized dispatcher: takes any provider/model × any scenario (wrbeta | wrsym | wralpha | jsm1) × full|bare × run_n. Replaces ad-hoc per-scenario scripts (`ablation.sh` for WR-β only, `ablation_jsm1.sh` for jsm1 only). Both narrower scripts remain in `tools/` for now but `ablation_multi.sh` is the canonical entry point going forward.
- **OpenRouter routing visible via response metadata.** `response.model` is the served route (sometimes more specific than the requested model, e.g., `deepseek/deepseek-chat-v3` for `deepseek/deepseek-chat`); `response.provider` is the backend. Worth capturing these in the run JSON's `llm_call_log` for future debugging — currently not captured (Phase 38.5/39 candidate alongside the per-run cost capture gap).
- **Llama 3.3 70B over OpenRouter is paid (Parasail) but slow** — ~12 min per game vs V3's ~3 min. Future Llama work might benefit from setting a `provider: {order: ['Groq', 'DeepInfra']}` preference for faster routes; toolkit currently doesn't expose this knob.
- **`toolkit/cost_accountant/types.py`** has `meta-llama/llama-3.3-70b-instruct: ModelPricing(0.0, 0.0)` flagged as "free tier" — misleading per the routing data (Parasail charges). Cost ledger underreports Llama spend until this entry is updated.

### Project-direction decision (informed by Run 17)

Three options from the Run 16 wrap remain open. Run 17 nudges each:

| Option | Status post-Run-17 |
|---|---|
| 1. Continue building harness features | **Strengthened.** V3 jsm1 lift (+66% with caveats) shows harness still works for mid+-tier models on coordination tasks. Sonnet's harness-zero was tier-specific, not universal. |
| 2. Per-module ablation (Phase 35 candidate) | **Lower priority confirmed.** V3 jsm1 picture is "needs full harness, not specific module" — per-module ablation wouldn't isolate anything. |
| 3. Validate scaling thesis (Phase 41/42 + new scenarios) | **Still highest-leverage.** Run 17 adds DeepSeek V3 to the matrix but doesn't broaden scenario shape. Note 1's untested axes (context, relationships, deception, horizon) remain the validation gap. |
| 4. NEW: V3 + competitive scenario investigation | Now feasible. NEXT_STEPS §11.b mixed-model probe gains V3 as a natural cost-tier intermediate. |

### Results files (Run 17, full set)

- `tests/self_play/results/run17_full_deepseekchat_jsm1_1.json`
- `tests/self_play/results/run17_full_deepseekchat_wrbeta_1.json`
- `tests/self_play/results/run17_bare_deepseekchat_jsm1_{1,2,3}.json`
- `tests/self_play/results/run17_bare_deepseekchat_wrbeta_{1,2,3}.json`
- `tests/self_play/results/run17_full_llama3370binstruct_jsm1_1.json`
- `tests/self_play/results/run17_full_llama3370binstruct_wrbeta_1.json`
- `tests/self_play/results/run17_full_deepseekr1_jsm1_1.json` (post-toolkit-fix; watchdog-capped before cell #2)
- Driver logfiles: `/tmp/run17_calib_20260612_041757.log` (initial matrix, partial), `/tmp/run17_llama_*.log` (Llama recovery), `/tmp/run17_v3bare_*.log` (V3 bare expansion), `/tmp/run17_r1_*.log` (R1 cell #1 + watchdog log `/tmp/r1_cap_watchdog.log`). Retained until container restart.
- Toolkit commit unblocking R1: `606e309` in toolkit repo (pushed to `origin/master` 2026-06-12).

### Run 17 closure (2026-06-16, under D-56)

Run 17 closed 2026-06-16 alongside the `DECISIONS.md` D-56 direction pivot. Summary of the closure:

- **Cells landed: 11** (10 from the original matrix + bare-V3 expansion + 1 R1 cell post-toolkit-fix).
- **Cells deferred: 5** (R1 cells #2-#6: wrbeta n=1, jsm1 n=2, jsm1 n=3, wrbeta n=2, wrbeta n=3 — collectively `Run 17 R1 follow-up` queued as Tier 1 in `NEXT_STEPS.md`).
- **V3 full n=3 expansion: queued** as Tier 1 follow-up — V3 full n=1 cells were the weakest data points in the matrix; expansion is ~$0.15 / ~12 min and confirms the hybrid pattern at credible n.
- **Toolkit sub-deliverable shipped:** `606e309` (OpenRouterProvider reasoning fallback) — unblocks all OpenRouter reasoning-model routes (R1, R1-distill, Qwen3, etc.) for future runs. Pushed to `origin/master`; documented in toolkit `VALIDATION_NOTES.md` + `ARCH_llm_client.md`. **Cross-project benefit:** any future toolkit consumer hitting OpenRouter reasoning models gets the fallback for free.
- **Reframing per D-56:** what was "multi-provider calibration" is now "multi-provider benchmark coverage" — a deliberate axis of the benchmark direction rather than ad-hoc model exploration. The hybrid V3 finding (sonnet-like on WR-β, mid+-tier on jsm1) becomes a benchmark insight ("training-distribution × scenario-shape interaction effects exist") rather than a coaching-direction "which model to deploy."

**What Run 17 settled** (no further action under D-56):
- Toolkit OpenRouter wiring works end-to-end for non-reasoning + reasoning models.
- DeepSeek V3 occupies a real intermediate tier between gpt-mini and sonnet, with the hybrid scenario × tier behavior.
- Cross-provider Pareto convergence on jsm1 holds across 4 provider families (Anthropic / OpenAI / DeepSeek non-reasoning / DeepSeek reasoning), all converging on `{α:8, β:9, γ:10}` when they close.
- Llama 3.3 70B looks below capability floor on n=1 (0/2) — n=3 expansion still wanted but not urgent.

**What Run 17 surfaced for future work** (now Tier 1 under D-56):
- R1 cells 17.14-17.18 (5 remaining cells) — ~$2-4, ~30-90 min.
- V3 full n=3 expansion.
- Llama n=3 expansion if benchmark capability-floor coverage matters.
- Reasoning-model coverage broadens to additional models (Qwen3-32B, o4-mini reasoning) — natural extension of the R1 unblock.

See `DECISIONS.md` D-56 for the project-direction call this Run informed.

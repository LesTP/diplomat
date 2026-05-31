# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

## Phase 19 — production reconciler + endgame-marker wiring

### 2026-05-30 — Close the two SMOKE_RUNBOOK gaps before the live smoke

**Action:** Wired two pieces that had been documented as known gaps in `SMOKE_RUNBOOK.md`. Done before the actual smoke run on the Pi (operator: "let's have the tests as realistic as we can").

**Gap 1: Reconciler not wired in production.**
`src/main.py` now calls a new `_attach_reconciler(orchestrator, llm_adapter, config_path)` helper after orchestrator construction. The helper:
- Reads `llm_providers.primary` from `pipeline.yaml`
- Builds a recon-specific config dict (provider + models + api_key from env)
- Instantiates `StateReconciler` with the production llm_adapter, recon config, and tier="commodity"
- Attaches as `orchestrator.reconciler`

If `llm_providers.primary` is missing, skip silently (orchestrator's `_reconcile_state` handles missing reconciler gracefully). To disable reconciliation in production, comment out the `_attach_reconciler(...)` call. No new feature flag — keeping the production wiring lean.

Self-play harness keeps its own per-faction reconciler wiring (using `_TaggedLLMClient` for SCORE/RECON visibility); the harness's last write wins, so the production wiring doesn't interfere with self-play tests.

**Gap 2: Endgame markers don't fire in production.**
`Orchestrator.__init__` now reads optional `game.total_rounds` from `pipeline.yaml`:
- When set to a positive int, `self.total_rounds = N` so `build_round_context` renders "Round K of N" headers and adds `### PENULTIMATE ROUND` / `### FINAL ROUND` blocks in the last two rounds.
- When unset, missing, zero, negative, or non-int: `self.total_rounds = None` (current production default — unchanged behavior for games where the round count is unknown).
- Self-play harness continues to set `total_rounds` via direct attribute assignment, overriding any config value.

Added commented example to `config/pipeline.yaml`:
```yaml
# game:
#   total_rounds: 6
```

**Tests:** 8 new in `tests/test_orchestrator.py` + `tests/test_main.py`:
- `test_total_rounds_unset_defaults_to_none` — production default
- `test_total_rounds_set_from_config` — explicit positive int wires through
- `test_total_rounds_zero_or_negative_ignored` — defensive (no crash on typo)
- `test_total_rounds_non_int_ignored` — defensive (string value rejected)
- `TestAttachReconciler::test_attaches_when_primary_provider_present` — happy path
- `TestAttachReconciler::test_no_primary_means_no_attach` — skip silently
- `TestAttachReconciler::test_missing_api_key_env_handled` — partial config
- `TestAttachReconciler::test_unset_api_key_env_produces_empty_string` — env var absent

`tests/test_main.py` is new — first unit-level coverage for production entry point wiring.

**Verification:**
- Full diplomat suite: 280 passed + 4 pre-existing Windows/network-share flakes (unchanged from baseline + the timing-race flake that sometimes appears as 3, sometimes 4).
- `tests/test_main.py`: 4 passed.
- `tests/test_orchestrator.py::test_total_rounds_*`: 4 passed.
- `tests/test_orchestrator.py::test_successful_instantiation_with_fakes`: still passes (existing test using `_copy_project_config` works with the new optional config section).

**SMOKE_RUNBOOK updates:**
- §4.1 (reconciler) → ~~FIXED~~ + cross-reference to new §3.8 verification step
- §4.2 (endgame markers) → ~~CONFIGURABLE~~ + cross-reference to new §3.9 verification step
- §3.8 added: trigger duplicate promises, ROUND signal, verify dedup in `/state` + RECON call in ledger
- §3.9 added: enable `game.total_rounds: 4`, `/preview` across rounds, verify PENULTIMATE/FINAL ROUND blocks appear in draft

**Files modified:**
- `src/orchestrator.py` (total_rounds read from config)
- `src/main.py` (`_attach_reconciler` helper + call after orchestrator construction)
- `config/pipeline.yaml` (commented `game:` example)
- `tests/test_orchestrator.py` (4 new total_rounds tests)
- `tests/test_main.py` (NEW — 4 reconciler-wiring tests)
- `SMOKE_RUNBOOK.md` (§4 gaps removed/marked fixed, §3.8 + §3.9 verification steps added)
- `NEXT_STEPS.md` (closure refs updated)
- `DEVLOG.md` (this entry)

**Next:** Live smoke on Pi per the updated runbook.

---

## Phase 19 — tooling debt: dated OpenAI model pricing

### 2026-05-30 — normalize_model_name + updated gpt-5.x prices + Gemini 2.5 family

**Action:** Closed the third tooling-debt item from `NEXT_STEPS.md` sequencing position #1. Cost accountant now resolves dated provider model IDs (e.g. `gpt-4.1-mini-2025-04-14`) back to their pricing-table aliases. Refreshed gpt-5.x prices from the operator-provided pricing page. Added Gemini 2.5 family explicitly. Retroactive audit of the self-play cost ledger: **41.6× overall overestimate** corrected ($24.38 reported → $0.59 real).

**Toolkit changes (`p:\shared\toolkit`):**

- `src/toolkit/cost_accountant/core.py` — new `normalize_model_name()` strips OpenAI `-YYYY-MM-DD` and Anthropic packed `-YYYYMMDD` date suffixes. Used by `estimate_cost()` as a fallback when the exact ID isn't in the pricing table (original ID is preserved in the returned estimate's `model` field for ledger fidelity).
- `src/toolkit/cost_accountant/types.py` — updated `DEFAULT_PRICING` for gpt-5.5 ($2/$8 → $5/$30), gpt-5.4 ($2/$8 → $2.50/$15), gpt-5.4-mini ($0.40/$1.60 → $0.75/$4.50) per operator's confirmed pricing page. Added Gemini 2.5 family: flash-lite ($0.10/$0.40), flash ($0.30/$2.50), pro ($1.25/$10) — the tuning default `gemini-2.5-flash-lite` previously had no entry.
- `src/toolkit/cost_accountant/__init__.py` — exported `normalize_model_name` for callers who need it directly.
- `tests/cost_accountant/test_core.py` — 13 new tests across `TestNormalizeModelName` (6 — strips OpenAI dated, strips Anthropic packed, no-op on undated, no-op on Gemini -001/-002 suffix, only trailing date stripped), `TestDatedModelLookup` (4 — gpt-4.1-mini dated resolves, model field preserves original, dated Anthropic resolves, exact dated Anthropic still works via direct lookup), `TestUpdatedPricing` (4 — gpt-5.5/5.4/5.4-mini new prices, Gemini 2.5 family added with strict cost ordering).

**Retroactive audit on actual self-play cost ledger** (434 successful entries across all Run 1-8 simulations):

| Model | Old reported | Real (post-fix) | Ratio |
|---|---|---|---|
| `gpt-4.1-mini-2025-04-14` | $19.7347 | $0.4931 | **40.0×** (normalized → in-table) |
| `claude-haiku-4-5-20251001` | $2.9857 | $0.0498 | **60.0×** (normalized → in-table) |
| `gemini-2.5-flash` | $1.6590 | $0.0426 | **38.9×** (was missing from table, now added) |
| **Total** | **$24.3794** | **$0.5855** | **41.6×** |

The overestimate was entirely driven by the conservative `$15/$75` per-Mtok fallback being hit on every successful call.

**Implications for past run reports:**
- TUNING_LOG.md Run 1-8 cost figures ("~$5-6 total spend across 8 runs") were ledger-derived, so they were ~6-40× overstated. Real cumulative spend across all self-play runs was closer to ~$0.10-0.15.
- This doesn't change any experimental conclusion — the relative cost of different models / scenarios / providers was still directionally right.
- New runs starting now will produce accurate ledger entries.

**What this is NOT:**
- Not a full pricing audit (NEXT_STEPS §6) — still need to verify Anthropic cache pricing, Gemini thinking-token billing, and review reasoning-model prices (o3, o4-mini). Tracked separately.
- Not a re-statement of Run 1-8 cost figures in TUNING_LOG. The ledger files themselves still contain the old values; only future entries are accurate. Could re-tally with a one-time script if a clean cost claim is needed for a stakeholder report.

**Verification:**
- Full toolkit suite: 230 passed (was 217 + 13 new).
- Full diplomat suite: 273 passed + 3 pre-existing Windows/network-share flakes (unchanged from baseline).
- Retroactive audit script on real cost ledger: 41.6× overestimate confirmed.

**Files modified:**
- `p:\shared\toolkit\src\toolkit\cost_accountant\core.py` (normalize_model_name + estimate_cost lookup)
- `p:\shared\toolkit\src\toolkit\cost_accountant\types.py` (gpt-5.x prices + Gemini 2.5 family)
- `p:\shared\toolkit\src\toolkit\cost_accountant\__init__.py` (export normalize_model_name)
- `p:\shared\toolkit\tests\cost_accountant\test_core.py` (13 new tests)

**Next:** Tooling debt is closed (all 3 items). Next sequencing position is #2: live Telegram re-smoke on the Pi.

---

## Phase 19 — tooling debt: scenario compiler BATNA hardcode

### 2026-05-30 — Replace "4-8 total" hardcode with fraction-of-max formula; add validator

**Action:** Closed the second tooling-debt item from `NEXT_STEPS.md` sequencing position #1. The scenario compiler's BATNA range guidance is no longer hardcoded to "typically 4-8 total" regardless of narrative — it's now a fraction of each faction's maximum possible score, configurable per run, with a post-hoc validator that flags under-pressure.

**Three changes in `src/tools/scenario_compiler.py`:**

1. **Prompt template parameterized by BATNA fraction.** Replaced `COMPILER_SYSTEM_PROMPT` constant with `COMPILER_SYSTEM_PROMPT_TEMPLATE` + `build_compiler_system_prompt(batna_fraction)` function. The "4-8 total" range guidance is replaced with: *"each faction's BATNA should be approximately {N}% of their MAXIMUM possible score across all issues."* This scales naturally to scenario size and lets the operator tune pressure per scenario.

2. **New `analyze_scenario(..., batna_fraction=0.50)` parameter.** Default 0.50 calibrated from Run 8's hand-patch values (alpha/beta/gamma landed in 0.40-0.61). Tradeoff: 0.50 produces real pressure (Pareto deals clearly beat BATNA) without being so high that no deal is possible.

3. **New `validate_batna_pressure()` function.** Post-hoc check that compares each faction's BATNA against `target_fraction * max_score` with configurable tolerance. Returns per-faction warnings. Also exports `max_possible_score()` helper for inspection.

**Wired through to two CLIs:**
- `src/tools/scenario_compiler.py` — `--batna-fraction` flag (default 0.50). Prints the target at compile time + warnings after analysis.
- `tests/self_play/run_simulation.py` — `--batna-fraction` flag passes through to `_compile_scenario` → `analyze_scenario`. Ignored when `--analysis-json` is used (pre-compiled analysis is already final). Prints BATNA pressure warnings after compilation.

**Retroactive validation.** Loaded Run 8's Water Rights analysis and ran `validate_batna_pressure(target_fraction=0.50)`:
- Pre-patch compiler output (alpha=7.5, beta=4, gamma=6): 3 warnings, BATNAs at 19-34% of max. Exactly the under-pressure problem we hit in Run 8.
- Hand-patched values (alpha=11, beta=8, gamma=10): 1 warning. Beta still borderline at 38% of max — even the hand-patch was suboptimal. The validator surfaces this.

**Tests:** 13 new in `tests/test_scenario_compiler.py`:
- `TestBuildCompilerSystemPrompt` × 6: default/custom fraction renders, lower/higher fractions, invalid (0, 1, negative) raise ValueError
- `TestMaxPossibleScore` × 3: sums max-outcome per issue across issues, beta-specific check, unknown faction returns 0
- `TestValidateBatnaPressure` × 4: passes when at target, warns when below, warns only low factions, default constant in valid range

**Verification:**
- Full diplomat suite: 273 passed + 3 pre-existing Windows/network-share flakes (unchanged from baseline).
- Both CLI `--help` outputs show the new flag with description and default.
- Compiler dry-path validation (loading existing analysis): wiring works end-to-end.

**Files modified:**
- `src/tools/scenario_compiler.py` (prompt template + 3 new functions: build_compiler_system_prompt, max_possible_score, validate_batna_pressure; CLI flag + warning printer in `_run`)
- `tests/self_play/run_simulation.py` (CLI flag + threading through `_compile_scenario` + warning printer)
- `tests/test_scenario_compiler.py` (13 new tests; updated imports)

**Note on workflow.** This doesn't deprecate the `--analysis-json` hand-patch workflow — that's still the right tool when the operator needs to dial in specific BATNA values per faction. What changes: the compiler's default output is now closer to usable on first try, and when it isn't, the validator says so explicitly with a hint about how to fix.

**Next:** Tooling debt item #3 — dated OpenAI model pricing in toolkit (`gpt-4.1-mini-2025-04-14` falls back to conservative default because pricing table only has `gpt-4.1-mini`).

---

## Phase 19 — tooling debt: LoggingLLMClient SCORE/RECON visibility

### 2026-05-30 — Fix unwrap regressions; surface concurrency bug; add re-snapshot of call log

**Action:** Closed the first tooling-debt item from `NEXT_STEPS.md` sequencing position #1. `LoggingLLMClient` now sees reconciliation (RECON) and post-game scoring (SCORE) calls with correct per-faction attribution.

**Three independent fixes, all in `tests/self_play/`:**

1. **Stop unwrapping the LoggingLLMClient at the reconciler and scorer call sites** (`game_environment.py` lines 325, 606 in pre-fix file). Both used `getattr(self.llm_client, "_inner", self.llm_client)` to bypass the logging wrapper. Now they wrap the logging client in a per-subsystem `_TaggedLLMClient` that pins a fixed faction tag (`recon:<faction>` or `scorer`) onto every call, with graceful fallback to the inner adapter when logging is disabled.

2. **New `_TaggedLLMClient` helper** in `game_environment.py`. **Async, not sync-returning-coroutine.** This matters: if `complete()` were sync, `set_faction()` would run at arg-evaluation time, so `asyncio.gather(tagged_a.complete(...), tagged_b.complete(...))` would resolve both `set_faction` calls before either coroutine ran — leaving every snapshot pointing at the last tag. Making `complete()` async forces the tag-set to happen inside the coroutine body, after the event loop enters it. Caught by `test_two_tagged_clients_dont_cross_tags_concurrently` — the first version of this fix failed the test, which surfaced the bug.

3. **`LoggingLLMClient.complete()` snapshots `_current_faction` at entry** instead of reading it in the `finally` block. Required for concurrent tagged calls: even with correctly-async wrappers, two calls can interleave their `set_faction` updates while one is still awaiting its inner API call. Without the snapshot, the wrong tag would be logged. Verified by `test_snapshot_faction_survives_concurrent_set`.

**Bonus fix: call-log snapshot timing in `run_game()`.** `collect_results()` snapshots `llm_call_log` via `to_dicts()`. `score_game()` runs *after* `collect_results()` and adds the SCORE call to the live log — which never made it into the serialized output. Fixed by re-snapshotting `results["llm_call_log"]` after scoring completes. This was the actual reason the dry-run smoke test initially showed 0 SCORE calls even with the wiring correct.

**verify_dryrun updated:** Invariant 7 (Scoring) was previously: *"check the results-JSON `scores` field instead of the call log"* (with an explicit "SCORE calls bypass LoggingLLMClient" comment). Now: *"expected at least 1 SCORE call in the LLM call log"* with a regression-hint message pointing back to `game_environment.py score_game()` if SCORE drops to 0.

**Tests:** 5 new tests in `tests/test_self_play.py` (`TestLoggingLLMClient` × 3, `TestTaggedLLMClient` × 2):
- Basic call recording with faction tag
- Error recording + re-raise
- Snapshot survives concurrent set_faction
- Tagged client applies fixed tag per call
- Two tagged clients don't cross-tag concurrently (the race test that caught the sync vs async bug)

**End-to-end validation:** Dry-run with 2-round Water Rights scenario. Call log now contains:
```
By type: {EXTRACT: 27, GEN: 6, ADV: 6, RECON: 6, ANALYST: 12, SCORE: 1}
By tag: {recon:gamma: 23, gamma: 16, unknown: 6, alpha: 4, beta: 4,
         recon:alpha: 2, recon:beta: 2, scorer: 1}
```
RECON calls correctly attributed per faction; SCORE call tagged `scorer`. `verify_dryrun` passes with `SCORE calls: 1` reported.

**Note on tag stickiness (not fixed):** After a reconciler call sets `_current_faction = "recon:gamma"`, subsequent ANALYST/EXTRACT calls in the same orchestrator chain inherit that tag until the next agent's `run_response_pipeline()` resets it (visible in `recon:gamma: 23` above). This is technically a misattribution for the trailing ANALYST/EXTRACT calls but doesn't affect the bug we set out to fix (SCORE/RECON visibility). Could be addressed later by tagging analyst/extraction calls explicitly with the orchestrator's owning faction at handle_round_boundary time, but the current behavior is at worst cosmetically misleading, not functionally wrong.

**Verification:**
- Full diplomat suite: 260 passed + 3 pre-existing Windows/network-share flakes (unchanged from baseline).
- Dry-run end-to-end: SCORE and RECON calls now visible and correctly tagged in the call log.
- `verify_dryrun.py` invariant 7 passes against the new output.

**Files modified:**
- `tests/self_play/game_environment.py` (snapshot in LoggingLLMClient.complete, new `_TaggedLLMClient`, RECON unwrap fix, SCORE unwrap fix, re-snapshot of llm_call_log after scoring)
- `tests/self_play/verify_dryrun.py` (invariant 7 now asserts SCORE call count)
- `tests/test_self_play.py` (5 new tests in TestLoggingLLMClient + TestTaggedLLMClient)

**Next:** Tooling debt item #2 — scenario compiler BATNA hardcode. Then #3 — dated OpenAI model pricing in toolkit.

---

## Phase 19 — toolkit complete_with_retry

### 2026-05-30 — Retry-with-backoff + safety-filter handling shipped

**Action:** Built `complete_with_retry` in `toolkit.llm_client` and wired it through `CostAccountant.complete` and Diplomat's `ToolkitLLMAdapter`. Closes the retry-with-backoff and safety-filter empty-response items from `NEXT_STEPS.md` §1.

**Toolkit changes (`p:\shared\toolkit`):**
- `src/toolkit/llm_client/providers.py` — new `complete_with_retry()` function. Exponential backoff with jitter, honors `LLMAPIError.retry_after` from Anthropic/OpenAI rate-limit response headers. Retries on 429 / 5xx / network errors (status_code is None) / LLMResponseError (empty responses, opt-out via `retry_on_empty=False`). Does NOT retry on 400/401/403/404/422. Sync (matches existing `complete()` API).
- `src/toolkit/llm_client/__init__.py` — exported `complete_with_retry`.
- `src/toolkit/cost_accountant/core.py` — changed `from toolkit.llm_client import complete as llm_complete` → `complete_with_retry as llm_complete`. Drop-in replacement; same positional signature. Ledger writes one entry per successful call; retried-then-failed calls write a single failure entry as before.
- `tests/llm_client/test_core.py` — 15 new tests in `TestCompleteWithRetry` covering: succeeds-first-try, retries on 429/5xx/network/empty, no-retry on 400/401, max_attempts exhaustion, max_attempts=1 (no retry), retry-after header honoring, exponential backoff math, max_delay cap, retry_on_empty=False opt-out, ValueError not retried.

**Diplomat changes (`p:\shared\diplomat`):**
- `src/adapters.py` — `ToolkitLLMAdapter.complete()` direct path (when no cost accountant injected) now uses `complete_with_retry` via `getattr(self._toolkit, "complete_with_retry", self._toolkit.complete)`. Graceful fallback for old toolkit versions. Accountant path inherits retry through the toolkit's `CostAccountant.complete`.

**Safety-filter audit (closes the second open item):** Confirmed that existing
`LLMResponseError` raised by each provider on empty content (Gemini's
`if not response.text or not response.text.strip()`) already catches
safety-filter cases. Previously `structured_call` caught these as
infrastructure failures and failed immediately. Now the underlying
`complete_with_retry` retries up to 3 times, so transient empty responses
recover automatically; genuinely-filtered responses still fail after retries
(correct behavior — caller sees the LLMResponseError).

**Verification:**
- Full toolkit test suite: 217 passed (was 29 for llm_client + 19 structured_llm + others; new 15 brings llm_client total to 44).
- Full Diplomat test suite: 254 passed + 4 pre-existing Windows/network-share timing flakes unchanged (`test_round_boundary_time_mode`, two `test_pipeline_flow` settle races, one secondary-analyst race that passes on isolated retry). Matches DEVPLAN documented baseline.
- Live 3-provider probe through the new adapter path (OpenAI, Anthropic, Google flash-lite): all green, no behavior regression.

**What this is NOT:**
- Not a CostAccountant pricing audit (NEXT_STEPS.md §6 — separate larger effort).
- Not a per-role model strategy (NEXT_STEPS.md §7 — separate experimental program).
- Not an OpenRouter integration (NEXT_STEPS.md §1.5 — sequencing item #1).
- Not Stage 2 conversation model (NEXT_STEPS.md §3 — sequencing item #4).

**Files modified:**
- `p:\shared\toolkit\src\toolkit\llm_client\providers.py`
- `p:\shared\toolkit\src\toolkit\llm_client\__init__.py`
- `p:\shared\toolkit\src\toolkit\cost_accountant\core.py`
- `p:\shared\toolkit\tests\llm_client\test_core.py`
- `p:\shared\diplomat\src\adapters.py`
- `p:\shared\diplomat\NEXT_STEPS.md` (closure update + change history row)
- `p:\shared\diplomat\TUNING.md` (§6 Tuning Changelog row added)
- `p:\shared\diplomat\DEVLOG.md` (this entry)

**Next:** Sequencing item #1 is now OpenRouter integration + Run 9 multi-provider rotation.

---

## Phase 18 Close + Regime Shift Acknowledgment

### 2026-05-30 — Phase 18 closed, regime retroactively reclassified Build → Explore

**Action:** Closing Phase 18. Originally planned as a Build phase with 6 structured
steps; in execution expanded to 16 steps (18.1–18.16) and morphed into Explore
regime as the work shifted from "wire up self-play infrastructure" (Build) to
"run simulations and tune until behavior is interesting" (Explore). Recording
the regime shift here so future cold-start sessions see the regime change clearly
rather than only a step count anomaly.

**Why the shift happened:** Steps 18.1–18.5 (GameEnvironment, runner, analysis,
unit tests, scenario fixtures) were genuine Build — testable infrastructure with
clear acceptance criteria. Step 18.6 (debounce fix) surfaced from Run 2 failure
diagnosis, was Debug. Steps 18.7–18.13 (structured_call, cost wiring, prompt
tuning, scenario compiler, post-game scoring, game-mode system) were issued one
at a time in response to per-run observations — the canonical Explore loop
"prototype → run → evaluate → revise." Step 18.14 (reconciliation) and 18.15
(budget gate) returned to Build for the underlying mechanics, with their
behavior validated empirically only in later runs.

Per GOVERNANCE Explore criteria: this Explore phase was *not* explicitly
time-boxed at the outset, but in retrospect was self-time-boxed by spending
(~$5–6 across 8 runs) and by the natural "we're done iterating, time to plan
next" decision after Run 8. The phase closes with a clear decision: the
Diplomat pipeline is functionally complete and self-play-validated; next phase
goes to a planning regime (Discuss) to pick concrete work from `NEXT_STEPS.md`.

**Design constraints carried throughout Phase 18:**
- 3 generic factions with distinct negotiation strategies, identical technical capabilities
- Multiple scenario types tested: territory dispute, water rights, dirty bargaining, coalition exercise
- All agents use real LLM calls (LLMAnalyst, LLMGenerator, LLMAdversarialReader, OpenAIStructuredExtractor)
- AutoApproveReviewGate for no human in the loop
- GameEnvironment supports `extra_module_overrides` for unit tests, `--scenario` flag for auto-compiled personas
- CLI runner: `python -m tests.self_play.run_simulation --rounds 4 [--scenario <path>]`

**Compressed step list (full detail in TUNING_LOG per-run entries):**

| # | What | Type | Run that surfaced or validated it |
|---|------|------|-----------------------------------|
| 18.1 | Faction personas + scenario text | Build | Run 1 setup |
| 18.2 | GameEnvironment (lifecycle, broadcast, results) | Build | Run 1 |
| 18.3 | Simulation runner CLI | Build | Run 1 |
| 18.4 | Post-game analysis tool | Build | Run 3 |
| 18.5 | Unit tests (24 self-play + 11 compiler = 35) | Build | continuous |
| 18.6 | Orchestrator debounce fix (per-event tasks) | Debug | Run 2 surfaced |
| 18.7 | `structured_call()` toolkit function + rewire 4 LLM modules | Build | Run 3 |
| 18.8 | Cost accountant wiring through `ToolkitLLMAdapter` | Build | Run 3 |
| 18.9 | Prompt tuning: generation, extraction, analyst, adversarial | Explore | Runs 3–5 |
| 18.10 | Analyst transcript feed (`recent_events`) | Build | Run 4 fix |
| 18.11 | Scenario compiler (narrative → scored personas) | Build | Run 6 enabled |
| 18.12 | Post-game scoring (winner/loser vs BATNA) | Build | Run 7 validated |
| 18.13 | Game mode system (cooperative/competitive/mixed) | Build | Run 6+ |
| 18.14 | State reconciliation module | Build | Run 7 dedup validated |
| 18.15 | Budget gate fix (real spend from shared accountant) | Debug | Run 7 surfaced |
| 18.16 | Documentation catch-up (DEVPLAN, DECISIONS, ARCH files, TUNING_LOG, ARCH_reconciliation) | Build | end of phase |

Plus Run 7 Prep (endgame awareness) and Run 8 (multi-provider) carried out
within the same Phase 18 timeline; see dedicated entries below.

**Total spend across Runs 1–8: ~$5–6.** See `TUNING_LOG.md` for run-by-run
analysis with hypotheses, results, and decisions taken.

**Decisions added in Phase 18:** D-20 through D-24 in `DECISIONS.md`.

**Architecture deltas captured during Phase 18:** Reconciliation module
(`ARCH_reconciliation.md`), conversation model taxonomy and Stage 1 commitment
(`ARCH_conversation_model.md`), updated coupling notes and Testing Status in
`ARCHITECTURE.md`, ARCH_cost_accountant updated for adapter routing.

**Verification at close:**
- 240+ tests pass (1 pre-existing Windows timing flake on `test_round_boundary_time_mode`)
- 8 simulation runs documented in TUNING_LOG
- `pipeline.yaml` unchanged from Phase 16; production deployment path unchanged
- All scope expansion items absorbed into the same Phase 18 number with explicit DEVLOG entries (Run 7 Prep, Run 8 infra)

**Closing the phase frontmatter:** `phase: 19`, `blocked: false`, `state: discuss`,
`steps_remaining: 0`. Phase 19 scope is set by operator review of `NEXT_STEPS.md`.

---

## Run 8 — Multi-Provider Showdown (Water Rights)

### 2026-05-29 — Run 8 infrastructure + first live run

**Action:** Built per-faction provider routing, pre-compiled analysis loader, scenario optimum verifier, and the Water Rights scenario itself. Ran Run 8 with three Generator providers (OpenAI / Anthropic / Google) on the Water Rights scenario. Surfaced and fixed two silent-failure bugs (`.env` not loaded; toolkit `parse_json_response` missing Markdown fence handling). See `TUNING_LOG.md` "Run 8" for full experimental analysis.

**Scope:**

*New scenario and verifier:*
- `tests/self_play/scenarios/water_rights.md` — 3 issues × 3 outcomes, asymmetric positions (dam/farms/city), distinct priority per faction.
- `tests/self_play/scenarios/water_rights_compiled/` — compiled analysis JSON + 3 persona files. BATNAs hand-patched upward (alpha 7.5→11, beta 4→8, gamma 6→10) to force genuine negotiation pressure. The compiler's hardcoded BATNA range guidance ("typically 4-8 total") under-pressures the scenario; the hand-patch is the workaround.
- `tests/self_play/verify_scenario_optimum.py` — enumerates all possible deals, reports Pareto frontier, BATNA-clearing deals, logrolling quality. Use before spending money on a live run to confirm the scenario has a non-trivial optimum.

*Runner extensions (`tests/self_play/run_simulation.py`):*
- `--per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},...}'` overrides only the Generator slot per faction. Other modules (Extractor, Analyst, Adversarial, Reconciliation) stay on shared primary/secondary.
- `--analysis-json <path>` skips live LLM compilation and loads a pre-existing analysis JSON. Personas regenerated from the loaded analysis at startup. Requires `--scenario` (for seed-message text).
- `load_dotenv()` at module top. Without this, only env vars already in the parent shell were visible — typically only `OPENAI_API_KEY`. Anthropic and Google calls failed auth.

*Game environment (`tests/self_play/game_environment.py`):*
- `GameEnvironment.__init__` takes `per_faction_providers: dict[str, dict[str, str]] | None`.
- `_generate_faction_config` writes a `generator_override` entry into `llm_providers` and points only the Generator module at it when the override is set.
- `_api_key_env_for(provider)` helper maps provider name → expected env var (openai/anthropic/google/openrouter).
- Fixed: `─` box-drawing characters in the final-scores print crashed Windows cp1252; switched to ASCII `-`.

*Verifier (`tests/self_play/verify_dryrun.py`):*
- New `--expect-providers '{"alpha":"openai",...}'` flag walks the call log and asserts each faction's GEN calls went through the expected provider. Catches per-faction routing regressions cheaply.

*Toolkit dependency change (`p:\shared\toolkit\src\toolkit\structured_llm\core.py`, committed separately):*
- `parse_json_response` now strips a single surrounding Markdown code fence before `json.loads`. Anthropic and Google wrap JSON in ` ```json ... ``` ` even when instructed to return raw JSON; without stripping, structured_call's retries silently exhausted. 19 toolkit tests still pass.

**What this is NOT:**
- Not a Stage 2 conversation model change. Still Model 1 (single-shot sealed) per `ARCH_conversation_model.md`.
- Not a change to production `pipeline.yaml` or any non-self-play code path.
- Not a fix to the Google rate-limit issue (gamma R4 was dropped due to free-tier 429; see TUNING_LOG open items).
- Not a fix to the persona payment-issue rigidity (Alpha never proposed Shared as a compromise even though it cleanly beats her BATNA). Recurring across Run 7 and Run 8; deferred to keep Run 9's variable isolation clean.

**Verification:**
- `pytest tests/structured_llm/` in toolkit: 19/19 pass.
- Dry-run with `--per-faction-providers` and `--analysis-json`: all infrastructure invariants pass, per-faction provider routing confirmed.
- Live Run 8: `tests/self_play/results/run8_water_rights_3provider_v3.json`. 11/12 expected agent messages reached the transcript (1 lost to Google rate limit). All three providers reached the transcript with substantive content. Promises tracked per faction: alpha=8, beta=15, gamma=5.

**Files modified:**
- `tests/self_play/game_environment.py` (per-faction provider routing, unicode fix)
- `tests/self_play/run_simulation.py` (`--per-faction-providers`, `--analysis-json`, `load_dotenv()`)
- `tests/self_play/verify_dryrun.py` (`--expect-providers`)
- `tests/self_play/scenarios/water_rights.md` (NEW)
- `tests/self_play/scenarios/water_rights_compiled/{scenario_analysis.json, alpha.txt, beta.txt, gamma.txt}` (NEW)
- `tests/self_play/verify_scenario_optimum.py` (NEW)
- `tests/self_play/results/run8_water_rights_3provider_v3.{json,log}` (NEW — canonical Run 8 result)
- `TUNING_LOG.md` (Run 8 section completed; Inter-Run Infrastructure section; new Key Insights 10-13; new Open Items)
- `DEVPLAN.md` (Open Items updated with Run 8 follow-ups)
- `p:\shared\toolkit\src\toolkit\structured_llm\core.py` + `ARCH_structured_llm.md` + `DEVLOG.md` (committed separately in toolkit repo)

**Next:**
- Run 9 — rotate provider→faction assignments on the same Water Rights scenario. Same plumbing. Controls for position-vs-provider confound (Alpha won by tiebreak with the highest BATNA — coincidence?).
- Eventually: fix Google rate-limit handling in toolkit's `llm_client` (retry-with-backoff on 429) so the third provider doesn't drop a message per game.

---

## Run 7 Prep — Endgame Awareness

### 2026-05-29 — Endgame-awareness implementation

**Action:** Prep work for the Run 7 self-play simulation (per `TUNING_LOG.md` Phase 6). Goal is to test whether agents change behavior when they know there's a hard scoring round with winners, losers, and a BATNA floor.

**Scope:**
- Persona module: `build_round_context()` gains an optional `total_rounds: int | None = None` kwarg. When set, the round header renders "Round N of M" and `rounds_remaining` is derived authoritatively from `total_rounds - round_number` (overrides any caller-supplied value). Adds a `### PENULTIMATE ROUND` block when effective remaining == 1, a `### FINAL ROUND` block when == 0. Early rounds are unchanged. Existing callers passing 3 positional args keep current behavior.
- Orchestrator: new `self.total_rounds: int | None = None` attribute, default `None` for production (real games don't know the round count). `run_response_pipeline` threads it into `build_round_context`. Self-play harnesses set the attribute before the round loop.
- GameEnvironment: `run_game` sets `handle.orchestrator.total_rounds = total_rounds` for every agent before running rounds.
- Scenario compiler `PERSONA_TEMPLATE`: new `ENDGAME:` paragraph inserted between BATNA WARNING and TRUE priority. Tells the agent the game has a fixed round count, final-round position is what's scored, and to plan backwards.
- Doc updates: `ARCH_persona.md` (new signature), `ARCH_orchestrator.md` (State section now lists `total_rounds`), `TUNING_LOG.md` (Run 7 + Run 8 plans).

**What this is NOT:**
- No explicit "FINAL ROUND" prompt toggle separate from `rounds_remaining==0`. Per Run 7's design, we want to see whether knowing the round count alone is enough before adding extra pressure mechanisms.
- No changes to production `pipeline.yaml` — production stays `total_rounds=None`. This is self-play instrumentation.
- No changes to static personas in `tests/self_play/personas/` (alpha/beta/gamma.txt) — Run 7 uses the compiled-scenario path.

**Verification:**
- `tests/test_persona.py`: 14/14 pass (6 existing + 5 new endgame tests + 3 pre-existing other).
- Suites touched by these changes: 118/119 pass. The 1 failure (`test_round_boundary_time_mode`) is a pre-existing timing flake on this network-share env, reproducible on clean baseline.
- 4 failures observed in full suite are all pre-existing infrastructure flakes (`_settle()` is `asyncio.sleep(0.05)` — racing against extraction on the network-share filesystem). Already noted in DEVPLAN as needing live re-smoke before Pi deployment.
- `validate_changes`: 0 diagnostic errors across the 7 modified files.

**Files modified:**
- `src/modules/persona/__init__.py`
- `src/orchestrator.py`
- `src/tools/scenario_compiler.py`
- `tests/self_play/game_environment.py`
- `tests/test_persona.py` (+5 new tests)
- `tests/test_orchestrator.py` (FakePersona kwarg compat)
- `ARCH_persona.md`, `ARCH_orchestrator.md`, `TUNING_LOG.md`, `DEVLOG.md` (this entry)

**Next:** Run 7 — regenerate Three-Party Coalition personas via scenario compiler, then `python -m tests.self_play.run_simulation --rounds 4 --scenario tests/self_play/scenarios/three_party_coalition.md`. Inspect rounds 3 and 4 for actual behavioral shift.

## Phase 18: Multi-Agent Self-Play + Tuning

### 2026-05-28/29 — Phase 18 Complete

**Action:** Built complete self-play infrastructure; ran 7 simulations; discovered and fixed core pipeline bugs; built scenario compiler and post-game scoring.

**Scope (expanded from original plan):**
- Self-play infrastructure: GameEnvironment, LoggingLLMClient, simulation runner CLI, post-game analysis
- Pipeline fixes: Orchestrator debounce rewrite (D-20), cost accountant wiring through adapter
- Toolkit enhancements: `structured_call()` function (D-21), OpenAI pricing, optional budget
- Module rewires: all 4 LLM modules → structured_call
- Prompt tuning: generation, extraction, analyst, adversarial prompts updated based on run analysis
- Scenario compiler (`src/tools/scenario_compiler.py`) — production pre-game tool (D-23)
- Post-game scoring: evaluates final proposals against scoring tables, declares winner
- Game mode system: cooperative/competitive/mixed behavioral instructions (D-24)

- State reconciliation: `src/modules/reconciliation/` — post-round LLM cleanup of promise duplicates, fulfillment/broken detection, inconsistency flagging, missed proposals
- Budget gate fix: `DiplomatCostGate.available_budget()` reads real spend from shared accountant
- State Manager: added `delete_entity()` and `update_promise_status()` methods

**Key findings from 7 runs (~$2.50 total):**
1. RuleBasedExtractor misses all natural negotiation language (Run 1)
2. Debounce cancel-and-replace silently drops messages in bursts (Run 2 — critical bug)
3. Narrative-only prompts fail schema validation ~30% of the time (Run 3)
4. LLMs default to cooperative without explicit competitive instructions (Runs 1-4)
5. Point tables + named deception tactics produce genuinely strategic play (Run 5)
6. Scenario compiler successfully auto-generates scored personas (Run 6-7)

See `TUNING_LOG.md` for the full iterative tuning record with per-run analysis.

**Verification:**
- 41 self-play + scenario compiler + reconciliation tests pass
- 240+ total tests across the project (1 pre-existing flaky timer test on Windows)
- 7 live simulation runs completed across 4 scenario types

**New decisions:** D-20 through D-24 added to DECISIONS.md.

**Next steps:** See DEVPLAN.md "Next Steps: Modularization Roadmap" and "Open Items and Future Plans" sections.


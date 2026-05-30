# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

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


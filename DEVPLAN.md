---
phase: 18
blocked: false
state: review
steps_remaining: 0
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before deployment; implement `TelethonUserTransport` only if bot-to-bot messaging is unavailable
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop
  - `toolkit` lives at `../toolkit` and must be installed editable into the diplomat venv (`<venv>/bin/python3 -m pip install -e ../toolkit`). It is not declared in `pyproject.toml` to avoid a misleading install contract — fresh `pip install -e .` cannot resolve `toolkit` from PyPI, so the editable install is a one-time per-host setup step. Module-level tests use dependency-injected fakes for isolation; that pattern is fine and should continue, but integration paths in Orchestrator must exercise real `toolkit` imports
  - Debounce strategy: **rewritten in Phase 18** from per-message cancel-and-replace to per-event task set. Each game message gets its own extraction task; no cancellation between different messages. The original design (11.2) silently dropped messages in multi-message bursts.
  - Cost governance: CostAccountant is now wired through `ToolkitLLMAdapter` — every LLM call routes through `accountant.complete()` for budget-check + ledger write. The `DiplomatCostGate` check-before-call pattern remains for round-level budget control. Both share the same accountant instance.
  - All four LLM modules (extraction, analyst, adversarial, generation) now use `toolkit.structured_llm.structured_call()` for schema-enforced JSON output with automatic retry on validation failure.
  - Self-play cost ledger uses a local temp path (`%TEMP%/diplomat_selfplay/`) to avoid UNC path issues on network shares.
  - Before deployment, install `../toolkit` editable and run live probes for `llm_client`, `telegram_client`, and `cost_accountant`; this environment cannot import `toolkit`, so Phase 11 close recorded probe specs rather than live matches
  - Prompt regression runner: `_judge_response_text()` JSON path extraction must be wrapped in try-catch — if a scenario's `path` does not exist in module output, the raw KeyError propagates and crashes the runner. Fixed in Phase 17 review; always validate extraction paths before production scenario runs.
  - **Cross-provider JSON formatting (Run 8 fix).** Anthropic and Google wrap JSON output in ` ```json ... ``` ` Markdown fences regardless of explicit "return raw JSON" instructions. OpenAI returns raw JSON. Toolkit's `parse_json_response` (in `structured_llm/core.py`) now strips a single surrounding code fence before parsing. Without this, structured_call's retries silently exhaust and downstream modules see "no error" but receive nothing.
  - **Self-play env loading (Run 8 fix).** `tests/self_play/run_simulation.py` calls `load_dotenv()` at module top. Previously only env vars in the parent shell were visible to subprocess SDKs — typically only `OPENAI_API_KEY` was reliable; Anthropic and Google calls silently failed auth.
  - **Per-faction provider routing (Run 8).** Use `--per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},...}'` to vary only the Generator per faction. Other modules stay on shared primary/secondary. Verify with `verify_dryrun --expect-providers '{"alpha":"openai",...}'`.
  - **Pre-compiled analysis loader (Run 8).** Use `--analysis-json <path>` to skip live LLM compilation and load a pre-edited analysis JSON (preserves hand-tuned BATNAs, scoring tables, deception tactics). Requires `--scenario` for the seed-message text. Personas are regenerated from the loaded analysis at startup.
  - **Compiler BATNA anchor (Run 8 surfaced).** `tools/scenario_compiler.py` hardcodes "BATNAs should be low enough (typically 4-8 total)" in its system prompt regardless of narrative. If you need stronger BATNA pressure, hand-edit the analysis JSON and use `--analysis-json` to feed it back in.
  - **Run live probe before multi-provider games.** `python -m tests.self_play.probe_providers --providers '<same JSON as --per-faction-providers>'` hits each provider once with a trivial JSON request and verifies auth + roundtrip + parse. ~$0.001 total. Catches integration bugs (missing API keys, fence wrapping, model name typos) that `DryRunLLMClient` cannot catch by design (DryRun replaces the LLM client entirely with canned responses, so no real auth/parse path runs). Run this before every multi-provider simulation — Run 8 burned ~14 Gemini calls on silent retry loops because we didn't probe first; Google's free tier here is **20 requests/day** for gemini-2.5-flash, so two failed iterations exhausts the daily budget.
  - **Google Gemini free-tier quota on this project: 20 requests/day** for `gemini-2.5-flash` (most other Gemini models return `limit: 0`). With a clean 4-round game using ~4-6 gemini GEN calls, that's comfortably 1-3 games per day. Bug-tax (silent retries) can burn 14+ calls per failed attempt — probe first.

## Current Status

- **Phase** — Phase 18 complete + Run 8 (multi-provider) complete. Awaiting human audit before next phase.
- **Focus** — Self-play infrastructure, prompt tuning, scenario compiler, state reconciliation, cost wiring, multi-provider. 8 simulation runs (~$5-6 total). See `TUNING_LOG.md`.
- **Blocked/Broken** — None. Audit gate set.

## Next Steps: Modularization Roadmap

The system is functional for the diplomacy game. The following levels of modularization would make it reusable across domains (customer service, contract negotiation, sales, etc.). See `ARCH_reconciliation.md` for reconciliation design.

### Level 1: Config-Driven Prompts and Examples (recommended next)

Move all entity-type-specific content out of Python code into config files that sit alongside the schema. The code reads the schema to discover entity types and loads corresponding examples and prompt fragments dynamically.

**What changes:**
- Extraction few-shot examples (`_EXTRACTION_EXAMPLES`) → `config/examples/extraction_examples.json`
- Reconciliation prompt entity references → derived from schema keys
- Analysis tool entity iteration → reads schema instead of hardcoding "promises", "coalitions"
- Persona library structure: `config/personas/styles/` for reusable behavioral templates, overlaid with domain-specific scoring by the scenario compiler

**Result:** Switching domains = replace `config/` directory. No code changes.

**Effort:** 1-2 hours.

### Level 2: Schema-Driven State Manager (needed for true reuse)

The state manager generates SQLite tables from `state_patch.json` at startup. Each entity type in the schema becomes a table. Upsert/delete/query methods derive field names and primary keys from the schema rather than hardcoding them.

**What changes:**
- `_create_tables()` reads schema and generates `CREATE TABLE` statements
- `_upsert_promise()` / `_upsert_coalition()` etc. → generic `_upsert_entity(table, item)`
- Table-to-ID-column mapping derived from schema `required` fields

**Result:** `state_patch.json` is the single source of truth for both validation and storage.

**Effort:** Half a day. Wait until you actually try a second domain to feel the pain first.

### Level 3: Domain-Agnostic Orchestrator (future)

Remove game-specific flow assumptions (round boundaries, direct-address triggers). Replace with configurable triggers and a flow definition.

**What changes:**
- Orchestrator becomes a state machine configured by a flow YAML
- Round detection → generic "boundary condition" pattern matching
- Direct-address → generic "response trigger" rules

**Effort:** Multiple days. Only if you have a concrete non-game use case.

## Open Items and Future Plans

### Immediate (before deployment)
- [ ] **Live Telegram re-smoke.** Phase 18 changes (debounce fix, structured_call, cost wiring, reconciliation) have only been validated in self-play. Need a manual Telegram smoke test on the Pi covering multi-message burst, review gate, and cost ledger.
- [ ] **Switch to TelegramReviewGate.** Production `pipeline.yaml` uses `AutoApproveReviewGate` (safe default). Change to `TelegramReviewGate` on the Pi when deploying with real credentials.
- [ ] **Run scored Three-Party Coalition.** The last attempt failed on a UNC path issue (now fixed). Validates post-game scoring + reconciliation end-to-end.

### Self-Play / Multi-Provider Experimentation
- [ ] **Run 9 — rotated provider assignments.** Water Rights scenario, rotate provider→faction mapping to control for position-vs-provider confound (Alpha won Run 8 by tiebreak with the highest BATNA — coincidence?). Same plumbing as Run 8.
- [ ] **Persona payment rigidity (recurring across Run 7 + Run 8).** Agents anchor on extreme outcomes on their priority issue and refuse to propose Pareto compromises that beat all BATNAs. The persona-prompt rule "don't accept the first reasonable framework" may be over-anchoring. A/B test a softened variant.
- [ ] **Google free-tier rate limiting.** Gemini-2.5-flash hit 429 on Run 8 R4. Add retry-with-backoff to toolkit's `llm_client`, OR switch gamma to a paid Gemini tier.
- [ ] **Compiler BATNA anchor.** `tools/scenario_compiler.py` hardcodes BATNA range guidance regardless of narrative. Add a `--batna-fraction` override, OR relax the range guidance, OR accept the hand-patch workflow (currently using `--analysis-json` to preserve hand-edits).
- [ ] **`LoggingLLMClient` doesn't see SCORE or RECON calls (Run 7).** Both unwrap the wrapper to call the inner client. Fix the unwrap so all calls go through one observable client.

### Extraction Quality
- [ ] **Promise dedup via reconciliation.** Reconciler is built but untested with live LLM. Run 4 showed 5 duplicates of the same $2M commitment.
- [ ] **Fulfillment detection.** Only 1/21 promises ever marked "kept". Reconciler should fix this — needs live validation.
- [ ] **Inconsistency detection.** Zero inconsistencies detected across 7 runs despite clear position shifts. Reconciler prompt specifically targets this.
- [ ] **Under-extraction in coalition games.** Run 6 (Three-Party Coalition) tracked only 1 promise out of 12 concrete proposals. Broadened extraction prompt may help; needs re-test.

### Prompt Tuning
- [ ] **Persona drift over 8+ rounds.** All runs were 4 rounds. Longer games may show persona drift — agents gradually losing their distinctive voice.
- [ ] **Provider-native structured output.** OpenAI's `response_format: json_schema` would give near-100% schema compliance at the token level. Requires toolkit `llm_client` changes to pass the parameter through.
- [ ] **Add more extraction few-shot examples.** Current 5 examples cover promise/coalition/fulfillment/broken/empty. Could add: conditional offer, demand with deadline, position shift, multi-issue proposal.

### Infrastructure
- [ ] **Persona library.** Separate behavioral styles from domain-specific scoring. Reusable templates in `config/personas/styles/`.
- [ ] **Game-mode runtime override.** `--game-mode` flag on the runner to override the compiler's classification without regenerating personas.
- [ ] **Level 1 modularization.** Config-driven prompts and examples (see roadmap above).
- [ ] **Dated model pricing in toolkit.** OpenAI returns `gpt-4.1-mini-2025-04-14` but pricing table has `gpt-4.1-mini`. Fallback pricing works but overestimates cost.

### Game-Specific
- [ ] **Real game rules.** Game rules are still being finalized. When available, compile them through the scenario compiler to generate the real faction persona.
- [ ] **ClankmatesTransport.** If the game moves to Clankmates platform, build a polling-based transport (no webhooks). Keep Telegram for operator coaching.
- [ ] **Multi-game support.** Run multiple instances with different faction prompts and databases for parallel games.

## Phase 18: Layer 4 — Multi-Agent Self-Play + Tuning

Regime: Build. Scope expanded significantly from original plan. Started as self-play infrastructure; grew to include core pipeline fixes (debounce, cost wiring), toolkit enhancements (structured_call, OpenAI pricing), prompt tuning across all 4 LLM modules, a scenario compiler tool, and post-game scoring. See `TUNING_LOG.md` for the full iterative tuning record.

**Design constraints:**
- 3 generic factions with distinct negotiation strategies, identical technical capabilities
- Multiple scenario types tested: territory dispute, water rights, dirty bargaining, coalition exercise
- All agents use real LLM calls (LLMAnalyst, LLMGenerator, LLMAdversarialReader, OpenAIStructuredExtractor)
- AutoApproveReviewGate for no human in the loop
- GameEnvironment supports `extra_module_overrides` for unit tests, `--scenario` flag for auto-compiled personas
- CLI runner: `python -m tests.self_play.run_simulation --rounds 4 [--scenario <path>]`

Steps:

- [x] 18.1 — **Faction personas and scenario text.** Created `tests/self_play/personas/` and `tests/self_play/scenario.py` with territory-dispute scenario. Later replaced with water rights, dirty bargaining, and Three-Party Coalition scenarios.

- [x] 18.2 — **GameEnvironment.** Per-faction YAML config generation, Orchestrator lifecycle, `broadcast()`/`broadcast_to_all()` message routing, `run_round()`/`run_game()`, `collect_results()`. Added `LoggingLLMClient` for full prompt/response/timing capture. Supports `extra_module_overrides`, `seed_message`/`round_updates` overrides, and `scenario_analysis` for scoring.

- [x] 18.3 — **Simulation runner CLI.** Argparse with `--rounds`, `--output`, `--factions`, `--scenario`, `--scenario-title`. Single shared CostAccountant between adapter and gate. Results written before teardown. Unbuffered stdout for long-running simulations.

- [x] 18.4 — **Post-game analysis.** Per-agent summary, communication patterns, round-by-round responses, promise cross-reference. CLI: `python -m tests.self_play.analysis --results <path>`.

- [x] 18.5 — **Unit tests.** 24 self-play tests + 11 scenario compiler tests = 35 total. Config generation, broadcast, lifecycle, analysis, persona generation, schema validation.

- [x] 18.6 — **Orchestrator debounce fix.** Rewrote from single `_debounce_task` (cancel-and-replace) to `_extraction_tasks: set[asyncio.Task]` (per-event, no cancellation). Fixed bug where burst messages silently dropped all but the last. Run 1-2 had zero extractions because of this.

- [x] 18.7 — **structured_call toolkit function.** Built `toolkit.structured_llm.structured_call()`: prompt assembly + schema injection + few-shot examples + JSON parse + schema validate + retry on failure. Rewired all 4 Diplomat LLM modules (extraction, analyst, adversarial, generation) to use it. 19 new toolkit tests.

- [x] 18.8 — **Cost accountant wiring.** `ToolkitLLMAdapter` now accepts optional `cost_accountant` and routes calls through `accountant.complete()`. Added OpenAI models to toolkit pricing table. Made `budget` parameter optional with default. Unknown models use conservative fallback pricing ($15/$75 per Mtok).

- [x] 18.9 — **Prompt tuning.** Generation prompt: reference intelligence, hold factions accountable, cite specifics, adapt to round pressure. Extraction prompt: explicit field allowlists, few-shot examples (promise, coalition, fulfillment, broken+inconsistency, empty), promise state tracking (pending/kept/broken/void), dedup rules, proposals as promises. Analyst prompt: use transcript alongside state tables, note contradictions.

- [x] 18.10 — **Analyst transcript feed.** Added `recent_events` parameter to `LLMAnalyst.analyze()`. Orchestrator passes last 30 events alongside state data. Fixed empty early-round intelligence.

- [x] 18.11 — **Scenario compiler.** Built `src/tools/scenario_compiler.py`: takes narrative scenario description, uses `structured_call` to extract issues/outcomes/scoring/BATNAs/deception tactics/logrolling/game-mode. Generates ready-to-use persona files. CLI: `python -m tools.scenario_compiler --scenario <path>`. Wired into self-play runner via `--scenario` flag.

- [x] 18.12 — **Post-game scoring.** Added `score_game()` to GameEnvironment: evaluates final proposals against scoring tables via `structured_call`, determines deal reached, calculates per-faction scores vs BATNA, declares winner/loser.

- [x] 18.13 — **Game mode system.** Scenario compiler classifies scenarios as cooperative/competitive/mixed. Persona template injects mode-specific behavioral instructions (competitive: maximize your score; cooperative: find mutual value but maximize your share).

- [x] 18.14 — **State reconciliation.** Built `src/modules/reconciliation/` with `StateReconciler`: post-round LLM call that merges duplicate promises, detects fulfillments (pending→kept/broken), flags inconsistencies from position shifts, and catches missed proposals. Added `delete_entity()` and `update_promise_status()` to State Manager. Wired into Orchestrator's `handle_round_boundary()` before analysts. 6 tests.

- [x] 18.15 — **Budget gate fix.** `DiplomatCostGate.available_budget()` now reads actual spend from the shared `CostAccountant.session_total` instead of relying on `record_spend()` calls that never happened. Round spend = delta since last `reset_round_budget()`.

- [x] 18.16 — **Documentation catch-up.** Updated DEVPLAN, DECISIONS (D-20 through D-24), ARCHITECTURE (coupling notes, testing status), ARCH_cost_accountant, diplomat-testing-doc (Layer 4 rewrite), DEVLOG, PROJECT scope. Created TUNING_LOG.md and ARCH_reconciliation.md.

Summary: Phase 18 expanded from 6 planned steps to 16 actual steps. Built complete self-play infrastructure with scenario compiler, post-game scoring, state reconciliation, and game-mode system. Ran 7 simulations across 4 scenario types totaling ~$2.50. Fixed critical debounce bug, wired real cost tracking, built reusable `structured_call` toolkit function, tuned all prompts based on empirical analysis. See `TUNING_LOG.md` for detailed run-by-run record.

Summary (in progress): Built complete self-play infrastructure with scenario compiler, post-game scoring, and game-mode system. Ran 7 simulations across 4 scenario types totaling ~$2.50 in LLM costs. Fixed critical debounce bug, wired real cost tracking, built reusable `structured_call` toolkit function, and tuned all prompts based on empirical run analysis. See `TUNING_LOG.md` for detailed run-by-run analysis.

## Phase 17: Layer 2 — Prompt Regression Infrastructure

Regime: Build. Scope: Create the prompt regression testing framework — scenario JSON format, scenario runner, LLM-as-judge evaluator, and a starter set of scenarios for Extraction and Generation modules. This infrastructure validates that prompt changes don’t break expected behavior. Reference: `diplomat-testing-doc.md` §4.

**Design constraints:**
- Scenarios are JSON files with structural assertions (`json_path_exists`, `json_path_equals`) and/or LLM-as-judge qualitative evaluations
- The LLM-as-judge uses the same adapter interface as all Diplomat modules (injected `llm_client`, plain dicts in, plain str out) — no direct toolkit imports
- The scenario runner calls real LLM APIs for the module under test and (optionally) for judge evaluations — **this costs money**. Use `commodity` tier models for judging.
- Scenarios target individual modules (extraction, generation, analyst, adversarial), not the full pipeline
- All existing 193 unit/integration tests must continue to pass
- Runner must work on the Pi where toolkit is installed; scenarios can be authored anywhere

Steps:

- [x] 17.1 — **Scenario format and result types.** Create `tests/prompt_regression/__init__.py` and `tests/prompt_regression/types.py` with:
  - `PropertyCheck` dataclass: `type` (json_path_exists | json_path_equals | llm_judge), `path`/`value`/`criteria`/`pass_instruction`/`fail_instruction`, `description`
  - `PropertyResult` dataclass: `passed`, `description`, `expected`, `actual`, `judge_explanation`
  - `ScenarioResult` dataclass: `scenario_id`, `description`, `properties: list[PropertyResult]`, `passed`
  - `RunReport` dataclass: `results: list[ScenarioResult]`, `total`, `passed`
  - `load_scenario(path) -> dict` and `load_scenarios(directory) -> list[dict]` helpers that read and validate scenario JSON files
  - `json_path_exists(data, path) -> bool` and `json_path_get(data, path) -> Any` helpers for dotted-bracket path navigation (e.g., `patch.data.promises[0].status`)
  Add unit tests for the path helpers in `tests/test_prompt_regression_types.py`. Run full regression.

- [x] 17.2 — **LLM-as-judge module.** Create `tests/prompt_regression/judge.py` with:
  - `JudgeResult` dataclass: `verdict` (PASS/FAIL), `explanation`, `criteria`
  - `LLMJudge` class: constructor accepts `llm_client` and `llm_config: dict` and `tier: str = "commodity"`; `async evaluate(response_text, criteria, pass_instruction, fail_instruction, context="") -> JudgeResult`
  - The evaluate prompt asks the LLM to return `PASS|explanation` or `FAIL|explanation`; parser splits on `|`
  - Add a unit test with a fake LLM client that returns canned `PASS|reason` and `FAIL|reason` to verify parsing
  Run full regression.

- [x] 17.3 — **Scenario runner.** Create `tests/prompt_regression/runner.py` with:
  - `ScenarioRunner` class: constructor accepts `llm_client`, `llm_config: dict`, and module builder callables
  - `async run_scenario(scenario: dict) -> ScenarioResult`: calls the appropriate module (extraction/generation/analyst/adversarial) with the scenario input, then evaluates each `expected_properties` entry using structural checks or LLM-as-judge
  - `async run_all(scenario_dir: str) -> RunReport`: loads all scenarios, runs each, prints per-scenario PASS/FAIL, prints summary
  - CLI entry point: `python -m tests.prompt_regression.runner --scenarios <dir>` with optional `--module <name>` filter
  Add a smoke test with a fake LLM client and one inline scenario dict to verify the runner produces a `RunReport`. Run full regression.

- [x] 17.4 — **Starter scenarios: extraction.** Create `tests/prompt_regression/scenarios/extraction/` with 4 JSON scenarios:
  1. `promise_explicit.json` — explicit promise creates pending promise entry (structural: `json_path_exists` on `patch.data.promises[0]`, `json_path_equals` on status=pending)
  2. `promise_vague.json` — vague offer does NOT create promise (structural: promises array empty or absent)
  3. `coalition_formation.json` — alliance announcement creates coalition entry
  4. `inconsistency_detection.json` — contradiction creates inconsistency entry
  These scenarios use `RuleBasedExtractor` (free, no API calls) so they double as structural validation. Run full regression.

- [x] 17.5 — **Starter scenarios: generation.** Create `tests/prompt_regression/scenarios/generation/` with 2 JSON scenarios:
  1. `constraint_respect.json` — CONSTRAINT coaching must be respected (llm_judge: response does not accept forbidden alliance)
  2. `persona_consistency.json` — response matches faction persona tone (llm_judge: response uses appropriate diplomatic framing)
  These require real LLM calls for both generation and judging. Document expected cost per run. Run full regression.

- [x] 17.6 — **Documentation and regression.** Verify full test suite (193 existing + new type/runner tests). Update DEVPLAN Phase 17 summary. Update `diplomat-testing-doc.md` Layer 2 status. Append DEVLOG entry. Transition to `state: review`.

Summary: Implemented Layer 2 prompt regression infrastructure: scenario/result dataclasses, scenario JSON validation, dotted/bracket JSON-path helpers, LLM-as-judge evaluation, a module-builder based scenario runner with CLI, 15 focused prompt-regression unit tests, 4 free Extraction scenarios, 2 LLM-backed Generation scenarios, and cost documentation for paid generation runs. Phase Review applied 1 must-fix (wrapped `_judge_response_text()` path extraction in try-catch) and added 4 edge-case tests (judge whitespace/blank-explanation handling, runner missing-builder and invalid-path errors). Full regression: 211 tests pass. Generation scenarios require a live injected LLM client on the Pi to execute. See `DEVLOG.md`.

## Phase 16: Deployment Readiness

Complete. Restored regression coverage for live-smoke fixes, documented two-channel Telegram deployment, added `config/diplomat.service`, removed temporary transport debug prints, fixed the CostAccountant adapter construction found during review, and verified 193 passing tests. See `DEVLOG.md`.

## Phase 15: Live Smoke Test — Environment Setup

Complete. Created `.env.template` and `config/pipeline_smoke.yaml`. Validated startup on Pi with real toolkit imports. Manual smoke test confirmed: Telegram transport receives messages, operator commands (`/status`, `/state`, `/ledger`, `/commands`) respond correctly, `/preview` triggers LLM generation, review gate (`/approve`, `/block`) works. Five integration fixes applied during smoke test:
1. Transport: added `message_text` to content field lookup (TelegramUpdate compatibility)
2. Transport: changed `start_polling()` from blocking await to background task with race condition fix
3. Review Gate: added `message_text` to content field lookup
4. Orchestrator: added `/commands` handler listing all commands and coaching tags
5. Orchestrator: added `/block` acknowledgement message

All fixes committed. See `DEVLOG_archive.md`.

## Phase 14: Layer 3 — Transcript Replay Tests

Complete. Two JSON transcript fixtures (`cooperative_3round.json`, `betrayal_arc.json`) and five replay integration tests verify multi-round promise, coalition, inconsistency, and intelligence persistence through the fake-backed Orchestrator pipeline. Full regression: 187 passed. See `DEVLOG.md`.

## Phase 13: Layer 3 — Pipeline Integration Tests

Complete. Implemented fake-backed Layer 3 integration infrastructure and 12 tests covering fixture startup, core Orchestrator flow, and failure handling. Full regression: 182 passed. See `DEVLOG.md`.

## Phase 12: Orchestrator Refactor

Complete. Extracted `ToolkitLLMAdapter` and `DiplomatCostGate` to `src/adapters.py`, expanded State Manager with 5 persistence APIs, removed Orchestrator sqlite3 fallbacks, typed `InboundEvent` on public event/pipeline methods, and verified 170 regression tests. See `DEVLOG.md`.

## Phase 11: Orchestrator

Complete. Implemented `pipeline.yaml`, registry lookup, Orchestrator startup/event-loop/round-management/response-pipeline/cost-governance wiring, `src/main.py`, and 44 focused Orchestrator tests with 165 total regression tests passing. Phase Review applied three should-fix items and no must-fix items. Post-phase toolkit integration probes found 3 mismatches; adapters (`ToolkitLLMAdapter`, `DiplomatCostGate`) applied and verified on Pi. See `DEVLOG.md`.

## Phase 10: Adversarial

Complete. Implemented `AdversarialResult`, `LLMAdversarialReader`, local adversarial JSON/schema validation, prompt/schema artifacts, and 9 focused tests with 121 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG_archive.md`.

## Phase 9: Review Gate

Complete. Implemented review decisions, auto-approve mode, Telegram approve/edit/block workflow, optional timeout auto-block, and 14 focused tests with 112 total regression tests passing. Phase Review applied two should-fix items. See `DEVLOG_archive.md`.

## Phase 8: Generation

Regime: Build. Scope: `GenerationResult` dataclass, `LLMGenerator.generate()`, review-gate JSON response parsing, plain-text mode, generation prompt/config artifacts, and full regression coverage. No direct provider SDK imports; all LLM calls stay behind toolkit-compatible dependency injection.

Steps:
- [x] 8.1 — Implement `GenerationResult` and `LLMGenerator` in `src/modules/generation/__init__.py`. Constructor accepts toolkit-compatible LLM config/client dependency, tier, max_tokens, and `review_gate_enabled`; `generate(context)` calls the injected completion client with `DecisionContext.system_prompt` and `DecisionContext.user_prompt`, returns `success=False` for client exceptions, and preserves provider/debug response data where available. Add `tests/test_generation.py` coverage for successful plain-text generation, client exception failure, prompt forwarding, tier/max token forwarding, and provider/raw response propagation. Run focused tests.
- [x] 8.2 — Add review-gate JSON handling and generation prompt/config artifacts. When `review_gate_enabled=True`, require JSON containing `response` and `reasoning`; reject malformed JSON, missing/blank response, and schema-shaped failures through `GenerationResult.success=False`. When disabled, treat nonblank plain text as `response_text` with `reasoning=None`. Create `config/prompts/generation.txt` with JSON/plain output instructions aligned to `ARCH_generation.md`. Run focused tests plus full regression.
- [x] 8.3 — Documentation cleanup and regression verification. Verify the full suite, update Phase 8 summary/status, mark implementation sequence row 9 as pending review, and transition DEVPLAN to `state: review`.

Summary: Implemented `GenerationResult`, `LLMGenerator`, review-gate JSON parsing (`response`, `reasoning`), plain-text mode, raw response preservation, `config/prompts/generation.txt`, and 11 focused Generation tests. Full regression: 98 passed. Phase Review found and fixed one must-fix: Context Assembler was instructing the LLM to use `draft_message`/`rationale` keys while Generation expected `response`/`reasoning` — fixed in both `_format_output_instruction` and its test. Phase complete.

## Phase 7: Context Assembler

Complete. Implemented `CoachingEntry`, `DecisionContext`, `DefaultContextAssembler` (pure composition, no external deps), 7-test coverage with 87 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG.md`.

## Phase 6: Analyst + Divergence

Complete. Implemented shared intelligence result types, `LLMAnalyst`, pure divergence comparison, analyst prompt/schema, and 12-test coverage with 80 total regression tests passing. See `DEVLOG.md`.

## Phase 5: Persona

Regime: Build. Scope: `CoachingContext` dataclass, `FileBasedPersona` (both public methods), hot-reload, `config/faction_prompt.txt` sample, full test coverage.

Steps:
- [x] 5.1 — Implement `CoachingContext` + `FileBasedPersona` (`get_base_prompt`, `build_round_context`) in `src/modules/persona/__init__.py`. Write `tests/test_persona.py` covering: FileNotFoundError, fresh read, hot-reload on mtime change, no-reload when unchanged, CURRENT ROUND CONTEXT section stripping, `build_round_context` formatting with all fields, empty fields, `rounds_remaining=None`. Run full suite.
- [x] 5.2 — Create `config/faction_prompt.txt` with sample faction persona including `## CURRENT ROUND CONTEXT` marker. Run full regression (59 + new persona tests pass). Update DEVPLAN summary, DEVLOG, ARCHITECTURE.md status.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Complete. Implemented `config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, config validation, tagged/free coaching parsing, slash command parsing, and 11-test coverage with 38 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 4: Transport

Complete. Implemented shared Transport API exports, `CLITransport`, dependency-injected `TelegramBotTransport` send/listen paths, and 21 focused Transport tests with 59 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

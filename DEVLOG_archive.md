# Diplomat — Development Log Archive

## Archived 2026-05-30 — Phases 6, 7, 8, 11, 12, 13, 14, 16, 17 + Post-Phase 11 toolkit adapters

Moved during DEVPLAN/DEVLOG cleanup as part of closing Phase 18. Active DEVLOG kept only Phase 18 + Run 7 Prep + Run 8 entries after this archive.

## Module 6: Analyst + Divergence

### 2026-05-25 — Phase 6 Plan

**Action:** Phase Plan for Analyst + Divergence
**Outcome:** Complete — DEVPLAN updated with step breakdown, state transitioned to execute

Planned 2-step phase:
- **Step 6.1** — Types (`AnalysisResult`, `Divergence`), `LLMAnalyst`, `compare()`, intelligence prompt + schema, full test coverage
- **Step 6.2** — Doc cleanup and ARCHITECTURE.md status update

DEVPLAN frontmatter: `phase: 6`, `state: execute`, `steps_remaining: 0`.

### Step 6.1: Analyst implementation and divergence detection

**Mode:** Build
**Outcome:** Complete — implemented LLM analyst, divergence comparison, schema, prompt, and tests
**Contract changes:** Added `AnalysisResult` and `Divergence` shared dataclasses in `src/modules/types.py`; added Analyst public API in `src/modules/analyst/__init__.py` and `src/modules/analyst/divergence.py`; added `config/schemas/intelligence.json`

Implemented `LLMAnalyst` as a provider-parameterised wrapper around toolkit-compatible `llm_client.complete`, with prompt/schema loading, state/schema prompt assembly, JSON parsing, local JSON Schema validation, timezone-aware result timestamps, and failure reporting through `AnalysisResult(success=False)`.

Implemented pure `compare()` divergence detection that returns no flags for failed analyst results and reports material threat-level gaps, missing leverage points, and coalition-stability mismatches using Phase 6 default thresholds.

Added the analyst prompt and intelligence schema, plus 12 analyst tests covering success, invalid JSON, LLM exception, schema failure, provider propagation, failed-result comparisons, identical reports, threat thresholds, missing leverage items, and coalition-stability mismatches.

Verification:
- `python3 -m pytest` — 80 passed

### Step 6.2: Documentation cleanup and regression verification

**Mode:** Build
**Outcome:** Complete — DEVPLAN status updated, ARCHITECTURE.md updated, regression verified, state transitioned to review
**Contract changes:** None

Updated DEVPLAN Current Status to reflect Phase 6 complete and state transitioned to `review`. Updated `ARCHITECTURE.md` Implementation Sequence row 7 (Analyst + Divergence) from "Not started" to "Phase 6 complete". Confirmed full regression: 80 tests pass (12 new analyst tests + 68 regression).

Verification:
- `python3 -m pytest tests/` — 80 passed

### 2026-05-25 — Phase 6 Review

**Action:** Phase Review for Analyst + Divergence
**Outcome:** Pass — no must-fix or should-fix items found

Implementation matches ARCH_analyst.md contract exactly: `LLMAnalyst` constructor with correct parameters, `async analyze()` returning `AnalysisResult`, all failures routed through `success=False` path, pure `compare()` function with all three divergence checks (threat_level_steps, missing_leverage_item, coalition_stability_mismatch). Types (`AnalysisResult`, `Divergence`) are frozen dataclasses matching spec. Intelligence schema has correct fields, types, constraints, and `additionalProperties: false`. Prompt correctly requests JSON-only output aligned to schema.

Test coverage satisfies all DEVPLAN 6.1 requirements: successful analysis, invalid JSON, LLM exception, schema validation failure, provider_id propagation, compare() with both failed, one failed, both identical, threat level steps divergence, within-threshold no-divergence, missing leverage item, coalition stability mismatch.

Verification:
- `python3 -m pytest tests/` — 80 passed

DEVPLAN transitioned to `state: close`.

### 2026-05-25 — Phase 6 Complete

**Action:** Phase Complete for Analyst + Divergence
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed shared `AnalysisResult` and `Divergence` dataclasses, `LLMAnalyst` with toolkit-compatible plain-text completion handling, local JSON parsing and JSON Schema validation, provider-aware failure reporting, pure divergence comparison, `config/prompts/analyst.txt`, and `config/schemas/intelligence.json`. Phase Review found no must-fix or should-fix items.

All 80 tests pass (12 analyst tests + 68 regression). Analyst remains toolkit-bound through dependency injection and Divergence remains pure Python.

Verification:
- `python3 -m pytest tests/` — 80 passed

No new gotchas promoted. No contract changes require propagation beyond the Phase 6 Analyst API and shared intelligence types already captured in `ARCH_analyst.md` and `ARCHITECTURE.md`.

## Module 7: Context Assembler

### Step 7.1: Context assembler implementation and tests

**Mode:** Build
**Outcome:** Complete — implemented the Context Assembler public API, prompt assembly, metadata, filtering, truncation, and tests
**Contract changes:** Added `CoachingEntry`, `DecisionContext`, and `DefaultContextAssembler` public exports in `src/modules/context_assembler/__init__.py`

Implemented `DefaultContextAssembler` as a pure async composition module with a `recent_events_limit=30` default, deterministic section ordering, pretty-printed intelligence, divergence formatting, recent transcript formatting, coaching filtering, review-gate output instructions, and metadata for `round_number`, `event_count`, and `coaching_count`.

Added focused Context Assembler tests covering all five non-INTEL coaching types, INTEL exclusion, divergence present/absent formatting, review-gate enabled/disabled instructions, recent transcript truncation, metadata counts, empty coaching placeholder, and section order.

Verification:
- `.venv/bin/python -m pytest -q` — 87 passed

### Step 7.2: Documentation cleanup and regression verification

**Mode:** Build
**Outcome:** Complete — DEVPLAN status updated, ARCHITECTURE.md updated, regression verified, state transitioned to review
**Contract changes:** None

Ran full regression after the Context Assembler implementation and confirmed all tests pass. Updated DEVPLAN Current Status to mark Phase 7 ready for review, marked Step 7.2 complete, and updated `ARCHITECTURE.md` Implementation Sequence row 8 from "In progress" to "Phase 7 complete, pending review".

Verification:
- `.venv/bin/python -m pytest -q` — 87 passed

### Phase 7 Review

**Mode:** Review
**Outcome:** Pass — no must-fix or should-fix items found

Implementation matches ARCH_context_assembler.md contract exactly: `DefaultContextAssembler` constructor with `recent_events_limit=30` default, `async assemble()` returning `DecisionContext`, correct seven-section context template ordering (round_context → INTELLIGENCE → DIVERGENCES → RECENT TRANSCRIPT → COACHING → TASK), `persona_prompt` in `system_prompt`, INTEL coaching type excluded from assembled context, divergence formatting, event transcript formatting, review-gate conditional output instructions, and metadata fields (round_number, event_count, coaching_count). Types (`CoachingEntry`, `DecisionContext`) are frozen dataclasses matching spec. No external dependencies — pure composition.

Test coverage satisfies all DEVPLAN 7.1 requirements: all five non-INTEL coaching types included, INTEL exclusion, divergences present vs. absent, review_gate enabled vs. disabled instructions, recent_events_limit truncation, metadata counts, empty coaching placeholder, section order.

Optional (skipped): RECENT TRANSCRIPT header uses `self.recent_events_limit` (the cap) rather than actual event count — cosmetically misleading when fewer events exist than the limit. Not a contract violation.

Verification:
- `python3 -m pytest tests/ -q` — 87 passed

DEVPLAN transitioned to `state: close`.

### 2026-05-25 — Phase 7 Complete

**Action:** Phase Complete for Context Assembler
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `CoachingEntry`, `DecisionContext`, and `DefaultContextAssembler` as a pure async composition module assembling persona prompt, round context, intelligence report, divergences, recent transcript, and coaching into a `DecisionContext` for the Generation module. INTEL coaching excluded from assembled context (already applied to database). All section ordering, formatting, and conditional review-gate instructions match `ARCH_context_assembler.md` template. Phase Review found no must-fix or should-fix items.

All 87 tests pass (7 context assembler tests + 80 regression). No external dependencies — pure composition.

Verification:
- `python3 -m pytest tests/ -q` — 87 passed

No new gotchas promoted. No contract changes require propagation — `CoachingEntry` and `DecisionContext` are new types consumed by Generation (Phase 8, not yet implemented).

## Module 8: Generation

### Phase 8 Plan

**Mode:** Discuss
**Outcome:** Planned — Generation phase broken into three Build steps and state transitioned to execute
**Contract changes:** None

Planned `GenerationResult` and `LLMGenerator` implementation against `ARCH_generation.md`: consume `DecisionContext`, call toolkit-compatible completion dependency, support review-gate JSON output with local parsing, support plain-text mode when review gate is disabled, and cover all behavior with fake-client tests before full regression.

Updated `ARCHITECTURE.md` Implementation Sequence row 9 to `In progress`.

### Step 8.1: Basic generator implementation and tests

**Mode:** Build
**Outcome:** Complete — implemented the Generation public API and plain-text completion path
**Contract changes:** Added `GenerationResult` and `LLMGenerator` public exports in `src/modules/generation/__init__.py`

Implemented `LLMGenerator.generate()` as an async wrapper around a toolkit-compatible injected LLM client. It forwards `DecisionContext.system_prompt` and `DecisionContext.user_prompt` as chat messages, passes configured LLM config, tier, and max token settings, reports provider/client exceptions through `GenerationResult.success=False`, rejects blank output, and preserves raw dict responses when the client supplies provider/debug metadata.

Added focused Generation tests for successful plain-text generation, exception failure, prompt forwarding, tier/config/max token forwarding, raw response propagation, and blank output failure.

Verification:
- `.venv/bin/python -m pytest tests/test_generation.py -q` — 6 passed

### Step 8.2: Review-gate JSON parsing and prompt artifact

**Mode:** Build
**Outcome:** Complete — added review-gate JSON parsing, generation prompt artifact, and regression coverage
**Contract changes:** Added `config/prompts/generation.txt` documenting Generation output keys `response` and `reasoning`

Implemented review-gate mode parsing in `LLMGenerator.generate()`: JSON responses must be objects containing a nonblank `response` string and a `reasoning` string. Malformed JSON, missing response, blank response, and missing reasoning now return `GenerationResult.success=False`. Plain-text mode continues to return nonblank text with `reasoning=None`.

Added `config/prompts/generation.txt` with the Generation output contract and expanded Generation tests for valid review-gate JSON, invalid JSON, missing/blank response, and missing reasoning. Full regression passes.

Verification:
- `.venv/bin/python -m pytest tests/test_generation.py -q` — 11 passed
- `.venv/bin/python -m pytest -q` — 98 passed

### Step 8.3: Documentation cleanup and regression verification

**Mode:** Build
**Outcome:** Complete — Phase 8 implementation marked ready for review
**Contract changes:** None

Ran final full regression after Generation implementation and confirmed all tests pass. Updated DEVPLAN Current Status, marked Step 8.3 complete, summarized Phase 8 output, transitioned DEVPLAN to `state: review`, and updated `ARCHITECTURE.md` Implementation Sequence row 9 to `Phase 8 complete, pending review`.

Review note: Context Assembler currently instructs review-gate output as `draft_message` and `rationale`, while `ARCH_generation.md` and Generation parsing expect `response` and `reasoning`. This should be evaluated during Phase 8 review before close.

Verification:
- `.venv/bin/python -m pytest -q` — 98 passed

### Phase 8 Review: Generation

**Mode:** Review
**Outcome:** Must-fix applied — transitioning to close

Review checked Generation implementation against `ARCH_generation.md`. One must-fix identified and resolved.

**Must-fix — JSON key mismatch (cross-module contract):**
`DefaultContextAssembler._format_output_instruction()` instructed the LLM to return `draft_message` and `rationale`, while `GenerationResult` parsing in `LLMGenerator._parse_review_response()` and `config/prompts/generation.txt` both expect `response` and `reasoning`. This would cause all review-gate generation calls to fail at the parse step with "LLM response JSON must include a nonblank response". Fixed `_format_output_instruction` to emit the correct keys and updated the matching test assertion.

All other review checks passed:
- `GenerationResult` dataclass matches ARCH schema exactly
- Constructor signature matches ARCH (llm_client, llm_config, tier, max_tokens, review_gate_enabled)
- generate() delegates to llm_client.complete() with messages/config/tier/max_tokens
- Plain-text mode strips text, sets reasoning=None
- All failures surfaced via GenerationResult.success=False (no exceptions bubble)
- No direct provider SDK imports
- 11 Generation tests cover all required cases; full regression 98 passed
- generation.txt output instructions match parser expectations

Verification:
- `python3 -m pytest -q` — 98 passed (post-fix)

### Phase 8 Close

**Mode:** Close
**Outcome:** Phase 8 complete — blocked awaiting human audit

Doc cleanup complete:
- DEVPLAN: summary updated with review fix note, Current Status updated to Phase 9 focus, state=close, blocked=true
- ARCHITECTURE.md: Implementation Sequence row 9 updated to "Phase 8 complete" (was "pending review")
- DEVLOG: review and close entries appended

No gotchas to promote — the JSON key mismatch was caught and fixed in review. The pattern to watch in future phases: when Context Assembler output instructions reference specific field names, verify they match the consuming module's parser.

Verification:
- `python3 -m pytest -q` — 98 passed

## Module 11: Orchestrator

### 2026-05-26 — Phase 11 Plan: Orchestrator

**Action:** Phase Plan
**Outcome:** 4-step breakdown committed to DEVPLAN

Phase 11 is the final module — Orchestrator wires all 11 prior modules into the live event loop. Steps:

- 11.1: `config/pipeline.yaml` schema + `registry.py` + `Orchestrator.__init__()` with startup sequence tests
- 11.2: `start()`/`shutdown()` event loop, operator routing (command/INTEL/coaching), game message debounced extraction, all command handlers (/status /state /ledger /intel /divergences /edits)
- 11.3: Round boundary detection (signal and time modes), dual-analyst + divergence, response pipeline with per-step failure handling (generation retry, adversarial skip, transport retry)
- 11.4: CostAccountant wiring (per-round budget check), `main.py` entry point, full regression targeting 140+ tests, docs and phase close

Design decisions captured in Gotchas:
- Debounce: per-message cooldown (cancel+reschedule timer on each new message)
- Budget lifecycle: per-round reset with CostBudget; session totals in cost_ledger.jsonl
- CostAccountant role: budget gate at Orchestrator before dispatching each LLM call

### Step 11.1: Config, registry, and Orchestrator init

**Mode:** Build
**Outcome:** Complete - pipeline config, registry resolution, Orchestrator startup wiring, and focused tests added
**Contract changes:** Added `config/pipeline.yaml`, `src/registry.py`, and `Orchestrator` startup API in `src/orchestrator.py`

Created the Orchestrator pipeline configuration with transport, LLM provider, module selection, cost, round detection, feature flag, prompt, and schema sections. Added registry lookup for every module implementation used by the pipeline, including the divergence comparator callable.

Implemented `Orchestrator.__init__()` to load and validate `pipeline.yaml`, resolve paths relative to the project root, initialize SQLite with WAL mode, load prompt/config artifacts fail-fast, build LLM config dictionaries from provider entries, and instantiate module objects from the registry with injectable LLM/Telegram clients for test and production wiring.

Added `tests/test_orchestrator.py` coverage for successful construction with fakes, bad config path, missing required config key, and registry lookup for every module type.

Verification:
- `python3 -m pytest tests/test_orchestrator.py -q` - 19 passed

### Step 11.2: Event loop, operator routing, and command dispatch

**Mode:** Build
**Outcome:** Complete - async event loop, shutdown, operator routing, debounced game-message extraction, command replies, and regression tests added
**Contract changes:** Extended `Orchestrator` public behavior with `start()`, `shutdown()`, and `process_event()`

Implemented the live event dispatch layer: `start()` consumes the configured transport listener and appends every event to the event store; `shutdown()` cancels pending debounce work and closes transports with a close hook. Operator messages now route through `TaggedCoachingParser`: slash commands dispatch to handlers, `INTEL` runs extraction with `intel_correction` and applies patches, and other coaching entries are stored unconsumed. Non-operator messages schedule debounced extraction so new messages cancel and replace the pending extraction task.

Added command handlers for `/status`, `/state`, `/ledger`, `/intel`, `/divergences`, and `/edits`, each sending a coaching-channel `OutboundMessage`. Added focused fake-driven tests for listener startup/shutdown, command routing, INTEL patch application, coaching persistence, debounce cancel/reschedule, and command reply formats.

Verification:
- `python3 -m pytest tests/test_orchestrator.py -q` - 30 passed
- `python3 -m pytest -q` - 151 passed

### Step 11.3: Round management and response pipeline

**Mode:** Build
**Outcome:** Complete - signal/time round detection, dual-analyst round analysis, response pipeline, and failure-path coverage added
**Contract changes:** Extended `Orchestrator` behavior with `handle_round_boundary()` and `run_response_pipeline()`

Implemented signal-mode round boundary detection during event processing and time-mode round boundaries via an async timer task. Round boundaries now run primary and secondary analysts concurrently, skip analysis with an operator alert on primary failure, proceed with primary-only analysis on secondary failure, compare divergences when both analysts succeed, persist the intelligence payload, and advance the round counter in `game_state`.

Added direct-address and `/preview` response triggers plus the full response pipeline: persona prompt/context, context assembly, generation with one retry, optional adversarial read with warning-on-failure, review gate submission, public send with three attempts, adversarial-read persistence, and coaching consumption after successful send.

Added focused coverage for signal/time round detection, primary and secondary analyst failure paths, happy-path response generation, direct-address and preview triggers, generation retry, adversarial failure propagation to review, review gate block, and transport retry behavior.

Verification:
- `python3 -m pytest tests/test_orchestrator.py -q` - 41 passed
- `python3 -m pytest -q` - 162 passed

### Step 11.4: Cost governance, main.py, full regression, and docs

**Mode:** Build
**Outcome:** Complete - per-call cost gates, entry point, final docs, and full regression verification added
**Contract changes:** Added `src/main.py`; extended `Orchestrator.__init__()` with cost-accountant injection

Added cost governance hooks around every LLM-backed operation owned by Orchestrator: extraction, primary analyst, secondary analyst, generation, generation retry, and adversarial read. The Orchestrator resets the per-round budget on startup and after each successful round advance, checks `available_budget()` before each LLM call, alerts the operator on exhausted budget, and skips the call as a hard limit.

Implemented `src/main.py` to load `.env`, read `DIPLOMAT_PIPELINE_CONFIG` or default `config/pipeline.yaml`, instantiate Orchestrator with toolkit-backed modules, run `asyncio.run()`, and shut down cleanly on SIGINT/SIGTERM. Updated Phase 11 docs and marked the architecture implementation sequence complete.

Verification:
- `python3 -m pytest tests/test_orchestrator.py -q` - 43 passed
- `python3 -m py_compile src/main.py src/orchestrator.py` - passed
- `python3 -m pytest -q` - 164 passed

### Phase 11 Review

**Mode:** Review
**Outcome:** Phase review complete — 3 should-fix items applied, no must-fix issues found

Reviewed Orchestrator implementation against ARCH_orchestrator.md contract. All seven responsibilities satisfied: startup, event loop, round management, response pipeline, failure handling, cost governance, and command dispatch. 164 tests passed pre-review.

**Should-fix items applied:**
1. `start()` now prints `DIPLOMAT ONLINE - Round {n} - {faction_id} - session budget ${X.XX}` at startup (ARCH startup sequence step 10).
2. `_apply_extraction()` now logs extraction failures (ARCH failure table: "Log, skip patch for this batch, continue").
3. Added `test_generation_double_failure_alerts_operator` — covers the path where both generation retries fail and the operator is alerted.

**Known gap noted (not applied):** Scheduled response time trigger mentioned in step 11.3 spec and ARCH event loop has no pipeline.yaml configuration support and no defined semantics; deferred to a future phase or operator-defined config extension.

Verification:
- `python3 -m pytest -q` — 165 passed

### Step 11.5: Dependency Probe — Orchestrator

**Mode:** Probe
**Outcome:** 0 matches, 0 mismatches, 3 unknown
**Contract changes:** None

#### toolkit.llm_client
- **Fake location:** `tests/test_orchestrator.py`, plus focused LLM-module fake clients in `tests/test_extraction.py`, `tests/test_analyst.py`, `tests/test_generation.py`, and `tests/test_adversarial.py`
- **Status:** Unknown
- **Probe result:** `python3` could not import `toolkit.llm_client` in this environment (`ModuleNotFoundError: No module named 'toolkit'`).
- **Probe spec:** After installing `../toolkit` editable, import `toolkit.llm_client`, confirm `LLMConfig` construction supports the provider/model/API-key-env fields used by `config/pipeline.yaml`, and confirm `complete(messages=..., config=..., tier=..., max_tokens=...)` returns plain text or a dict with a text-like payload compatible with the module parsers.

#### toolkit.telegram_client
- **Fake location:** `tests/test_orchestrator.py`, `tests/test_transport.py`, and `tests/test_review_gate.py`
- **Status:** Unknown
- **Probe result:** `python3` could not import `toolkit.telegram_client` in this environment (`ModuleNotFoundError: No module named 'toolkit'`).
- **Probe spec:** After installing `../toolkit` editable, import `toolkit.telegram_client`, confirm one of `build_client_from_env`, `create_client_from_env`, or `create_client` is present, and confirm the returned client supports the send/listen/update methods assumed by `TelegramBotTransport` and `TelegramReviewGate`.

#### toolkit.cost_accountant
- **Fake location:** `tests/test_orchestrator.py::FakeCostAccountant`
- **Status:** Unknown
- **Probe result:** `python3` could not import `toolkit.cost_accountant` in this environment (`ModuleNotFoundError: No module named 'toolkit'`).
- **Probe spec:** After installing `../toolkit` editable, import `CostAccountant`, confirm it can be initialized with `per_round_budget_usd` and `session_budget_usd`, and confirm it exposes `reset_round_budget(...)` or compatible reset behavior plus `available_budget()` returning a numeric remaining budget.

### 2026-05-27 — Phase 11 Complete

**Action:** Phase Complete for Orchestrator
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed the final planned module: `config/pipeline.yaml`, registry lookup, Orchestrator startup validation, async event loop, operator command routing, debounced game-message extraction, signal/time round boundaries, dual-analyst intelligence persistence, response pipeline, per-call cost gates, and `src/main.py`. Phase Review applied three should-fix items and found no must-fix issues.

All 165 tests pass (44 Orchestrator tests + 121 regression). `toolkit` was not importable in this environment, so the close dependency probe produced executable probe specs rather than live interface matches.

Verification:
- `python3 -m pytest` — 165 passed
- `python3` toolkit import probe — unknown, `toolkit` not installed

Promoted gotchas:
- Before deployment, install `../toolkit` editable and run the Orchestrator dependency probe specs against real `llm_client`, `telegram_client`, and `cost_accountant`; fake-driven tests cannot validate those sibling-library interfaces here.

No contract changes require propagation beyond the Phase 11 Orchestrator API, `pipeline.yaml`, and resolved budget/debounce contracts already captured in `ARCHITECTURE.md`, `DEVPLAN.md`, and `PROJECT.md`.

## Post-Phase 11: Toolkit Integration Probes and Adapter Fixes

### 2026-05-27 — Dependency probe (source-level)

**Mode:** Debug
**Outcome:** Three integration mismatches identified between Diplomat's fakes and real toolkit APIs

Toolkit was not importable in the worker's environment, but the source is accessible on the shared filesystem at `../toolkit/src/toolkit/`. Read the real type definitions and function signatures to compare against Diplomat's fakes and Orchestrator wiring.

**Probe 1: `toolkit.llm_client`** — MISMATCH
- Diplomat modules call `llm_client.complete(messages=[dict], config=dict, tier=str)` expecting `str` back
- Toolkit's `complete()` expects `list[Message]`, `LLMConfig` (with `models` dict, not single `model`), `ModelTier` enum; returns `LLMResponse` (need `.content`)
- Four sub-mismatches: message type, config type, tier type, return type

**Probe 2: `toolkit.telegram_client`** — MISMATCH
- `main.py` tried factory functions (`build_client_from_env`, `create_client_from_env`, `create_client`) — none exist
- Real API: `TelegramClient(bot_token=str)` constructed directly
- Transport method signatures (send_message, start_polling, get_next_update) match

**Probe 3: `toolkit.cost_accountant`** — MISMATCH
- Orchestrator used `available_budget()` / `reset_round_budget()` — neither exists
- Real API: `CostAccountant(ledger_path=Path)` with `complete()` wrapping `llm_client.complete()` and `CostBudget` per call
- Architectural pattern differs: toolkit wraps LLM calls, Diplomat gates before LLM calls

Root cause: Worker built fakes from ARCH prose descriptions ("calls toolkit/llm_client.complete()") without reading the real toolkit source. Recorded as D-13 in DECISIONS.md.

### 2026-05-27 — Adapter implementation

**Mode:** Code
**Outcome:** Three adapter fixes applied; all 165 tests pass
**Contract changes:** `config/pipeline.yaml` `llm_providers` section, `src/orchestrator.py` exports, `src/main.py` rewrite

**Fix 1: `ToolkitLLMAdapter`** (in `src/orchestrator.py`)
Wraps toolkit's real `complete()` into the interface Diplomat modules expect:
- Accepts `messages` as `list[dict]`, wraps into `toolkit.llm_client.Message`
- Accepts `config` as dict, maps to `toolkit.llm_client.LLMConfig` with `models` dict
- Accepts `tier` as str, maps to `toolkit.llm_client.ModelTier` enum
- Returns `response.content` (plain str) instead of `LLMResponse`

**Fix 2: `main.py` telegram client construction**
Replaced factory function search with direct `TelegramClient(bot_token=os.getenv("TELEGRAM_BOT_TOKEN"))`.

**Fix 3: `DiplomatCostGate`** (in `src/orchestrator.py`)
Wraps toolkit's `CostAccountant` with the `available_budget()` / `reset_round_budget()` API that Orchestrator's existing budget-gate pattern expects. Preserves all existing cost governance tests unchanged.

**Config change:** `pipeline.yaml` `llm_providers.*.model` (single string) changed to `llm_providers.*.models` (tier→model dict). `_build_llm_configs()` handles both formats for backward compatibility.

Existing tests unaffected — modules still call `llm_client.complete()` with the same interface; adapters only run in production.

### 2026-05-27 — Adapter verification on Pi

**Mode:** Debug
**Outcome:** All probes confirmed; adapters match real toolkit APIs

Ran verification inside the Incus container where toolkit is importable:
- Fixed `.pth` file path for editable toolkit install (container uses `/home/claude/workspace/`, not `/mnt/passport/shared/`)
- `python -m pytest -q` — 165 passed (all existing tests)
- Toolkit import probe confirmed:
  - `Message` fields: `['role', 'content']` — adapter wraps correctly
  - `LLMConfig` fields: `['provider', 'api_key', 'models', 'max_tokens', 'temperature']` — adapter builds correctly
  - `LLMResponse` fields: `['content', 'model', 'provider', 'token_usage']` — adapter extracts `.content`
  - `ModelTier` values: `['quality', 'default', 'commodity']` — adapter maps str to enum
  - `CostAccountant.__init__`: `(self, ledger_path: Path, pricing: dict | None)` — `DiplomatCostGate` wraps correctly
  - `TelegramClient.__init__`: `(self, bot_token: str, ...)` — `main.py` constructs correctly

Verification:
- `incus exec claude-code -- bash -c "cd /home/claude/workspace/diplomat && .venv/bin/python -m pytest -q"` — 165 passed
- Toolkit probe script — all three modules confirmed matching

## Phase 12: Orchestrator Refactor

### 2026-05-27 — Phase 12 Complete

**Action:** Phase Complete for Orchestrator Refactor
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed adapter extraction to `src/adapters.py`, State Manager persistence API expansion, Orchestrator SQLite fallback removal, and public `InboundEvent` typing. Phase Review applied one should-fix and found no must-fix issues. Full regression: 170 passed.

## Phase 13: Layer 3 Pipeline Integration Tests

### 2026-05-27 — Phase plan

**Mode:** Discuss
**Outcome:** Phase 13 plan recorded for fake-backed pipeline integration coverage

Phase 13 is a Build-regime testing phase. Scope is limited to shared integration test infrastructure and Layer 3 tests for the Orchestrator pipeline: TestTransport, StubAnalyst, fake LLM/cost helpers, test pipeline config, happy-path pipeline flow tests, failure-handling tests, and documentation cleanup.

Key constraints carried into the plan:
- No real API calls; all LLM and cost behavior is injected through fakes.
- SQLite tests use `tmp_path` database files, not `:memory:`.
- `Orchestrator.start()` runs in background tasks during integration tests.
- Existing 170 unit tests remain part of every regression checkpoint.

Next step: 13.1 builds the reusable test helpers and fixture artifacts.

### Step 13.1: Test infrastructure helpers and fixtures

**Mode:** Build
**Outcome:** Complete — reusable integration helper package, StubAnalyst fixture path, and registry entry added
**Contract changes:** `src/registry.py` now includes `StubAnalyst` for test pipeline resolution

Created `tests/helpers/` with `TestTransport`, `StubAnalyst`, and helper factories for inbound events, round-end events, fake LLM completions, and fake cost accounting. Added `tests/integration/` plus fixture data for a valid intelligence report and minimal persona prompt.

`TestTransport` implements the transport contract directly over `asyncio.Queue` and exposes injection/output helpers for background Orchestrator integration tests. `StubAnalyst` loads fixture JSON into an `AnalysisResult`, avoiding LLM calls in integration coverage.

Verification:
- `python3 -c "from tests.helpers.test_transport import TestTransport"` — passed
- `python3 -m pytest` — 170 passed

### Step 13.2: Test pipeline config and integration fixture

**Mode:** Build
**Outcome:** Complete — test pipeline config, async pipeline fixture, and fixture smoke test added
**Contract changes:** `Orchestrator` can instantiate `StubAnalyst` from a configured fixture path for test-only pipeline configs

Added `config/pipeline_test.yaml` with CLI transport wiring, `RuleBasedExtractor`, `StubAnalyst` primary/secondary analysts, `AutoApproveReviewGate`, test persona path, signal-based `[ROUND END]` detection, and fake provider config.

Added `tests/integration/conftest.py` with a `pipeline` fixture that builds a real Orchestrator over a tmp_path SQLite database, injects `TestTransport`, `FakeLLMClient`, and `FakeCostAccountant`, starts `Orchestrator.start()` in the background, and tears down with `shutdown()` plus task cancellation. A smoke test verifies the fixture starts and creates the database.

Verification:
- `python3 -m pytest tests/integration/test_pipeline_fixture.py -q` — 1 passed
- `python3 -m pytest` — 171 passed

### Step 13.3: Core pipeline flow tests

**Mode:** Build
**Outcome:** Complete — six fake-backed Orchestrator integration flow tests added
**Contract changes:** None

Added `tests/integration/test_pipeline_flow.py` covering game-message ingestion and extraction, PRIORITY coaching persistence, INTEL coaching state changes, `[ROUND END]` intelligence persistence, direct-address response generation, and `/preview` response generation.

The tests inject `InboundEvent` objects through `TestTransport`, let the background Orchestrator process them, and assert against real `SQLiteEventStore`, real `SQLiteStateManager`, and captured outbound transport messages.

Verification:
- `python3 -m pytest tests/integration/test_pipeline_flow.py -q` — 6 passed
- `python3 -m pytest` — 177 passed

### Step 13.4: Failure handling integration tests

**Mode:** Build
**Outcome:** Complete — five Orchestrator failure-handling integration tests added
**Contract changes:** None

Added `tests/integration/test_failure_handling.py` covering extraction failure continuity, secondary analyst failure with primary intelligence persistence, adversarial failure warning with public post continuation, double generation failure operator alerting, and public transport send retry exhaustion.

The tests monkeypatch targeted module methods on the integration fixture while preserving the real background Orchestrator loop, real event store, real state manager, and `TestTransport` output capture.

Verification:
- `python3 -m pytest tests/integration/test_failure_handling.py -q` — 5 passed
- `python3 -m pytest` — 182 passed

### Step 13.5: Documentation cleanup and regression verification

**Mode:** Build (cleanup)
**Outcome:** Complete — Phase 13 summary recorded, Layer 3 testing guide status updated, phase ready for review
**Contract changes:** None

Updated `DEVPLAN.md` to mark all Phase 13 steps complete and summarize the Layer 3 integration test work. Updated `diplomat-testing-doc.md` to mark Pipeline integration as complete with 12 tests and 182 total regression tests.

Verification:
- `python3 -m pytest` — 182 passed

Phase 13 is ready for review.

### 2026-05-27 — Phase 13 Complete

**Action:** Phase Complete for Layer 3 Pipeline Integration Tests
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Closed Phase 13 after fake-backed Layer 3 integration infrastructure and tests were completed. The suite now includes `TestTransport`, `StubAnalyst`, shared fake factories, `config/pipeline_test.yaml`, an async integration pipeline fixture, one fixture smoke test, six core pipeline flow tests, and five failure-handling tests.

Integration check:
- Orchestrator pipeline flow is covered end to end with real Event Store and State Manager instances, fake transport, fake LLM client, fake cost accountant, and stub analysts.
- No real API calls are made by Layer 3 integration tests.
- No cross-module production contract changes were introduced during Phase 13 beyond test-only `StubAnalyst` registry resolution.

Verification:
- `python3 -m pytest -q` — 182 passed

No new gotchas promoted. Contract changes are already reflected in `diplomat-testing-doc.md`, `ARCHITECTURE.md`, and `DEVPLAN.md`.

## Phase 14: Layer 3 Transcript Replay Tests

### 2026-05-27 — Phase 14 Planned

**Action:** Phase Plan for Layer 3 Transcript Replay Tests
**Outcome:** Complete — Phase 14 build steps are ready for execution

Confirmed Phase 14 scope: add deterministic synthetic transcript fixtures, replay them through the existing fake-backed Orchestrator integration pipeline, and assert final promise/coalition/inconsistency/intelligence state. The phase remains Layer 3 only: no real API calls, no prompt-quality assertions, and no Telegram dependencies.

Scope decision logged in `DECISIONS.md` as D-16.

### Step 14.1: Cooperative 3-round transcript fixture

**Mode:** Build
**Outcome:** Complete — deterministic cooperative replay fixture added
**Contract changes:** None

Created `tests/integration/fixtures/transcripts/cooperative_3round.json` with nine timestamped events across three rounds. The transcript includes two promise messages and one coalition message that match `RuleBasedExtractor` patterns, plus three `[ROUND END]` signals for later replay tests.

The fixture records expected final state for two pending promises (`Atlas` to `Beacon`, `Harbor` to `Atlas`) and one coalition (`Beacon` with `Harbor`).

Verification:
- `python3 -m json.tool tests/integration/fixtures/transcripts/cooperative_3round.json >/dev/null` — passed
- `python3 -m pytest -q` — 182 passed

### Step 14.2: Betrayal arc transcript fixture

**Mode:** Build
**Outcome:** Complete — deterministic betrayal replay fixture added
**Contract changes:** None

Created `tests/integration/fixtures/transcripts/betrayal_arc.json` with nine timestamped events across three rounds. The transcript covers `Crown` promising `Delta`, later contradicting the pact, and then forming a coalition with `Ember`, using text that matches the rule-based promise, inconsistency, and coalition patterns.

The fixture records expected final state for one pending promise, one inconsistency, and one coalition.

Verification:
- `python3 -m json.tool tests/integration/fixtures/transcripts/betrayal_arc.json >/dev/null` — passed
- `python3 -m pytest -q` — 182 passed

### Step 14.3: Transcript replay tests

**Mode:** Build
**Outcome:** Complete — replay helper and five integration tests added
**Contract changes:** None

Created `tests/integration/test_replay.py` with `replay_transcript()`, which loads transcript JSON fixtures, injects each event through `TestTransport`, waits for debounce/round-boundary processing, and returns persisted state from `SQLiteStateManager`.

Added replay assertions for cooperative promises, cooperative coalition state, one intelligence record per round boundary, betrayal-arc inconsistency state, and betrayal-arc promise plus coalition state. The helper uses a conservative per-event settle interval so sequential transcript events do not cancel pending debounced extraction.

Verification:
- `python3 -m pytest tests/integration/test_replay.py -q` — 5 passed
- `python3 -m pytest -q` — 187 passed

### Step 14.4: Documentation cleanup and regression

**Mode:** Build (cleanup)
**Outcome:** Complete — Phase 14 implementation ready for review
**Contract changes:** None

Verified the full suite after transcript replay implementation and updated `DEVPLAN.md` with the Phase 14 summary. Updated `diplomat-testing-doc.md` build order to mark Layer 3 transcript replay complete with two fixtures, five replay tests, and 187 total regression tests.

Verification:
- `python3 -m pytest -q` — 187 passed

### 2026-05-27 — Phase 14 Complete

**Action:** Phase Review and Phase Complete for Layer 3 Transcript Replay Tests
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Phase Review found no must-fix or should-fix items. All fixture messages match `RuleBasedExtractor` patterns, `state_manager.query()` intelligence ordering is deterministic (ORDER BY id ASC, records inserted in round sequence), all imports used, and the conftest `pipeline` fixture is correctly reused across all five replay tests.

Two transcript fixtures and five replay integration tests verify multi-round state accumulation through the fake-backed Orchestrator pipeline:
- `cooperative_3round.json` — 2 promises, 1 coalition, 3 round boundaries; 3 intelligence records
- `betrayal_arc.json` — 1 promise, 1 inconsistency, 1 coalition over 3 rounds

ARCHITECTURE.md Testing Status updated to record transcript replay tier complete.

Verification:
- `python3 -m pytest -q` — 187 passed

## Phase 16: Deployment Readiness

### 2026-05-27 — Phase 16 Planned

**Action:** Phase Plan for Deployment Readiness
**Outcome:** Complete — Phase 16 build steps are ready for execution

Confirmed Phase 16 scope: restore regression coverage for smoke-test fixes, document two-channel Telegram deployment, add a Raspberry Pi systemd service file, remove temporary transport debug prints, and run final regression. The phase remains deployment hardening only: no game-rule tuning, faction prompt changes, or round-mechanics changes.

Scope decision logged in `DECISIONS.md` as D-18.

### Step 16.1: Transport and review gate regression coverage

**Mode:** Build
**Outcome:** Complete — smoke-test fixes are covered by regression tests
**Contract changes:** None

Updated transport tests for background polling behavior, `None` update resilience, invalid-update skipping, and `message_text` content lookup. Updated review gate tests to verify object-style `message_text` command lookup. Added orchestrator coverage for `/commands` output and `/block` acknowledgement.

Fixed one transport edge case found by the new coverage: if background `start_polling()` fails before an update arrives, `TelegramBotTransport.listen()` now raises `TransportError` instead of silently ending after a `None` update.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_review_gate.py tests/test_orchestrator.py -q` — 85 passed
- `python3 -m pytest -q` — 193 passed

### Step 16.2: Two-channel Telegram setup guide

**Mode:** Build (documentation)
**Outcome:** Complete — deployment routing setup documented in `diplomat-testing-doc.md` §5b
**Contract changes:** None

Added a two-channel Telegram setup section covering the public game group, private coaching chat, bot membership, `.env` channel/user ID variables, `pipeline.yaml` `transport.faction_map`, and routing verification checks for non-operator game messages versus operator coaching commands.

### Step 16.3: Systemd service file

**Mode:** Build
**Outcome:** Complete — Pi service unit and management commands documented
**Contract changes:** None

Created `config/diplomat.service` for running the bot under systemd with the project root as `WorkingDirectory`, `.env` as `EnvironmentFile`, `PYTHONPATH` pointing at `src`, `.venv/bin/python` executing `src/main.py`, and `Restart=on-failure` with a 10-second delay.

Updated `diplomat-testing-doc.md` §5b with install, start, status, log, restart, and stop commands, plus a note to edit service paths if the Pi checkout location or user differs.

Verification:
- `systemd-analyze verify config/diplomat.service` — passed for the Diplomat unit

### Step 16.4: Remove transport debug prints

**Mode:** Build (cleanup)
**Outcome:** Complete — temporary transport debug output removed
**Contract changes:** None

Removed the `[DEBUG transport]` print statements from `TelegramBotTransport.listen()` while preserving invalid-update skip behavior.

Verification:
- `grep -RIn "\\[DEBUG transport\\]" src tests` — no matches
- `python3 -m pytest tests/test_transport.py -q` — 24 passed

### Step 16.5: Documentation and regression

**Mode:** Build (cleanup)
**Outcome:** Complete — Phase 16 implementation ready for review
**Contract changes:** None

Updated `diplomat-testing-doc.md` test counts and build-order status to reflect Phase 16 deployment readiness work. Updated `DEVPLAN.md` with the Phase 16 summary, marked all Phase 16 steps complete, and transitioned to review.

Verification:
- `python3 -m pytest -q` — 193 passed

### Phase 16 Review

**Mode:** Review
**Outcome:** One must-fix found and applied — full regression passes.

**Must-fix applied:**
- `_build_cost_accountant` in `src/orchestrator.py` was calling `CostAccountant(per_round_budget_usd=..., session_budget_usd=..., ledger_path=...)` but the toolkit's `CostAccountant` only accepts `ledger_path` and `pricing`. The try/except fallback `CostAccountant()` also failed because `ledger_path` is a required positional argument. Fixed by calling `CostAccountant(ledger_path=...)` and wrapping it in `DiplomatCostGate(accountant, per_round_budget_usd=...)` as the adapter pattern requires. This caused 26 test failures in the local environment (tests that didn't inject a fake cost_accountant).

Verification:
- `python3 -m pytest -q` — 193 passed

### 2026-05-27 — Phase 16 Complete

**Action:** Phase Complete for Deployment Readiness
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed deployment hardening after the live smoke test: regression coverage now protects the Telegram polling, `message_text`, `/commands`, and `/block` fixes; two-channel Telegram setup and systemd operation are documented; `config/diplomat.service` is present; temporary transport debug prints are removed; and Phase Review's CostAccountant construction must-fix is applied.

Verification:
- `.venv/bin/python -m pytest -q` — 193 passed

## Phase 17: Layer 2 Prompt Regression Infrastructure

### 2026-05-27 — Phase 17 Plan

**Action:** Phase Plan for Layer 2 prompt regression infrastructure
**Outcome:** Complete — Phase 17 scope confirmed and architecture status marked in progress

Confirmed the Build-regime plan for a module-scoped prompt regression framework: scenario JSON loading, dotted/bracket JSON-path structural assertions, LLM-as-judge evaluation through the existing injected LLM adapter shape, a runner with CLI support, and starter Extraction/Generation scenario libraries. The phase intentionally avoids full-pipeline replay and direct toolkit/provider SDK imports.

### Step 17.1: Scenario format and result types

**Mode:** Build
**Outcome:** Complete — prompt regression type helpers and unit coverage added
**Contract changes:** None

Created the `tests.prompt_regression` package with dataclasses for property checks/results, scenario results, and run reports. Added scenario JSON loading/validation plus dotted/bracket JSON-path helpers for structural assertions such as `patch.data.promises[0].status`.

Added focused unit tests for JSON-path navigation, falsey existing values, missing keys/indexes, invalid path syntax, type mismatches, scenario validation, and recursive scenario loading.

Verification:
- `python3 -m pytest tests/test_prompt_regression_types.py -q` — 8 passed
- `python3 -m pytest -q` — 201 passed

### Step 17.2: LLM-as-judge module

**Mode:** Build
**Outcome:** Complete — adapter-compatible LLM judge and parsing tests added
**Contract changes:** None

Added `tests.prompt_regression.judge` with `JudgeResult` and `LLMJudge`. The judge builds a strict evaluation prompt, calls the injected `llm_client.complete(messages=..., config=..., tier=...)`, and parses only `PASS|explanation` or `FAIL|explanation` responses.

Added fake-client tests for PASS parsing/request forwarding, FAIL parsing, and malformed judge output rejection.

Verification:
- `python3 -m pytest tests/test_prompt_regression_judge.py -q` — 3 passed
- `python3 -m pytest -q` — 204 passed

### Step 17.3: Scenario runner

**Mode:** Build
**Outcome:** Complete — scenario runner, CLI entry point, and smoke coverage added
**Contract changes:** None

Added `tests.prompt_regression.runner` with `ScenarioRunner.run_scenario()` and `run_all()`. The runner invokes module builders for extraction, generation, analyst, and adversarial scenarios, normalizes dataclass/dict results into structural output, evaluates `json_path_exists`, `json_path_equals`, and `llm_judge` properties, prints per-scenario PASS/FAIL lines, and returns a `RunReport`.

Added a CLI entry point for `python -m tests.prompt_regression.runner --scenarios <dir>` with optional `--module <name>` filtering. The default CLI can run free extraction scenarios through `RuleBasedExtractor`; LLM-backed scenarios should construct `ScenarioRunner` with an injected client.

Added smoke tests for structural property evaluation, LLM-judge property evaluation with a fake client, and `run_all()` loading/filtering behavior.

Verification:
- `python3 -m pytest tests/test_prompt_regression_runner.py -q` — 3 passed
- `python3 -m pytest -q` — 207 passed

### Step 17.4: Starter extraction scenarios

**Mode:** Build
**Outcome:** Complete — four free extraction prompt-regression scenarios added
**Contract changes:** None

Added `tests/prompt_regression/scenarios/extraction/` with scenarios for explicit promises, vague non-promises, coalition formation, and inconsistency detection. These use structural checks only and run through the CLI's default `RuleBasedExtractor`, so they do not call paid APIs.

Adjusted the prompt-regression package initializer so `python -m tests.prompt_regression.runner` runs without an eager-import `runpy` warning.

Verification:
- `python3 -m tests.prompt_regression.runner --scenarios tests/prompt_regression/scenarios --module extraction` — 4/4 scenarios passed
- `python3 -m pytest -q` — 207 passed

### Step 17.5: Starter generation scenarios

**Mode:** Build
**Outcome:** Complete — two LLM-backed generation scenarios and cost note added
**Contract changes:** None

Added `tests/prompt_regression/scenarios/generation/constraint_respect.json` and `persona_consistency.json`. Both scenarios target `LLMGenerator` output through LLM-as-judge checks: one verifies operator CONSTRAINT coaching blocks a forbidden France alliance, and the other verifies restrained diplomatic persona consistency.

Added `tests/prompt_regression/scenarios/generation/README.md` documenting that the two starter scenarios require four commodity-tier calls per run, normally less than USD 0.05 with mini/commodity models depending on the injected Pi provider configuration.

Verification:
- `python3 -m tests.prompt_regression.runner --scenarios tests/prompt_regression/scenarios --module extraction` — 4/4 extraction scenarios passed and all scenario JSON loaded successfully
- `python3 -m pytest -q` — 207 passed

Generation scenarios were not executed in this environment because they require paid live LLM calls and an injected production client.

### Step 17.6: Documentation and regression

**Mode:** Build (cleanup)
**Outcome:** Complete — Phase 17 implementation ready for review
**Contract changes:** None

Updated `diplomat-testing-doc.md` to mark Layer 2 prompt regression infrastructure complete, document the implemented scenario format/runner behavior, list the starter scenario library, clarify that generation scenarios require an injected live LLM client, and update the regression count to 207 tests.

Updated `DEVPLAN.md` with the Phase 17 implementation summary, marked all Phase 17 steps complete, and transitioned to review.

Verification:
- `python3 -m tests.prompt_regression.runner --scenarios tests/prompt_regression/scenarios --module extraction` — 4/4 scenarios passed
- `python3 -m pytest -q` — 207 passed

### Phase 17 Review

**Mode:** Review
**Outcome:** One must-fix applied, two should-fix test additions — full regression passes.

**Must-fix applied:**
- `_judge_response_text()` in `tests/prompt_regression/runner.py` called `json_path_get(output, path)` without a try-catch. If a scenario specified a path not present in module output, the raw `KeyError`/`IndexError` propagated uncaught and crashed the runner with no context. Fixed by wrapping in try-except and raising `ValueError(f"Cannot extract judge response text from path '{path}': ...")`.

**Should-fix applied (test additions):**
- `test_prompt_regression_judge.py`: added whitespace/case normalisation test (`"  pass  | explanation  "` → verdict `"PASS"`, explanation stripped) and blank-explanation rejection test (`"PASS|   "` raises `ValueError`).
- `test_prompt_regression_runner.py`: added missing-module-builder error test (raises `ValueError` with `"No module builder"`) and invalid-judge-path error test (raises `ValueError` with `"Cannot extract judge response text"`).

**Optional (skipped, logged):** Hardcoded module dispatch (`if module_name == "extraction"`) is an if-elif chain that will need extension for new modules. Acceptable for Phase 17 (4 modules) — table-driven refactor deferred to a future phase.

Verification:
- `python3 -m pytest -q` — 211 passed

### 2026-05-27 — Phase 17 Complete

**Action:** Phase Complete for Layer 2 Prompt Regression Infrastructure
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed Layer 2 testing framework: `tests.prompt_regression` package with scenario/result dataclasses, dotted/bracket JSON-path helpers, LLM-as-judge evaluation, a module-builder based scenario runner with CLI, 4 free Extraction scenarios, 2 LLM-backed Generation scenarios, and comprehensive unit coverage. Phase Review applied one must-fix (safe path extraction for judge properties) and added 4 edge-case tests.

Testing Status: 211 total tests (14 prompt-regression unit tests + 197 other regression). Extraction prompt-regression scenarios pass free (via `RuleBasedExtractor`). Generation scenarios require a live injected client on the Pi.

Verification:
- `python3 -m pytest -q` — 211 passed
- `python3 -m tests.prompt_regression.runner --scenarios tests/prompt_regression/scenarios --module extraction` — 4/4 passed

No contract changes require propagation — Phase 17 is test infrastructure only. Architecture Testing Status table updated to "Phase 17 complete".

<!-- Entries above archived from Phases 6-17, 2026-05-30 -->

## Archived 2026-05-26 — Module 9 Phase 9: Review Gate

### Phase 9 Plan

**Mode:** Discuss
**Outcome:** Planned - Review Gate phase broken into three Build steps and state transitioned to execute
**Contract changes:** Resolved provisional timeout behavior as optional configurable auto-block

Planned `ReviewDecision`, `AutoApproveReviewGate`, and `TelegramReviewGate` implementation against `ARCH_review_gate.md`: auto-approve path first, Telegram approve/edit/block workflow second, and timeout/documentation cleanup third. All Telegram behavior will use toolkit-compatible dependency injection and fake clients in tests.

Updated `ARCHITECTURE.md` Implementation Sequence row 10 to `In progress`.

### Step 9.1: Auto-approve review gate

**Mode:** Build
**Outcome:** Complete - implemented Review Gate decision type, auto-approve path, and focused tests
**Contract changes:** Added `ReviewDecision` and `AutoApproveReviewGate` public exports in `src/modules/review_gate/__init__.py`

Implemented `ReviewDecision` as a frozen dataclass matching `ARCH_review_gate.md`, and added `AutoApproveReviewGate.submit()` for `review_gate.enabled: false`. Successful nonblank drafts are approved with stripped final text. Failed or blank drafts return blocked decisions with explanatory edit notes, so the Orchestrator never posts unusable output through the disabled-review path.

Added `tests/test_review_gate.py` coverage for successful auto-approval, failed draft blocking, blank draft blocking, and the `ReviewDecision` field contract.

Verification:
- `.venv/bin/python -m pytest tests/test_review_gate.py -q` - 4 passed

### Step 9.2: Telegram review workflow

**Mode:** Build
**Outcome:** Complete - implemented TelegramReviewGate command workflow and fake-client tests
**Contract changes:** Added `TelegramReviewGate` public export in `src/modules/review_gate/__init__.py`

Implemented `TelegramReviewGate.submit()` with dependency-injected toolkit-compatible Telegram client calls. The gate sends a formatted coaching-channel review prompt containing draft text, optional reasoning, adversarial analysis or failure/skipped warning, and `/approve`, `/edit: ...`, `/block` command instructions. It waits for coaching-channel updates, ignores other channels, accepts approve/edit/block commands, retries after unknown commands, tracks in-memory pending state, and calls an optional `state_manager.log_review_decision(...)` hook when present.

Expanded `tests/test_review_gate.py` to cover prompt formatting, approve/edit/block decisions, other-channel filtering, unknown command retry, optional edit-log hook calls, and adversarial failure formatting.

Verification:
- `.venv/bin/python -m pytest tests/test_review_gate.py -q` - 12 passed

### Step 9.3: Timeout behavior and review handoff

**Mode:** Build
**Outcome:** Complete - timeout auto-block implemented, docs updated, full regression verified, state transitioned to review
**Contract changes:** Resolved Review Gate timeout contract in `ARCH_review_gate.md`; updated `ARCHITECTURE.md` status/provisional contract list

Added configurable `timeout_seconds` to `TelegramReviewGate`. When unset, the gate waits indefinitely for an operator command. When set, the wait is bounded with `asyncio.wait_for`; timeout returns a blocked `ReviewDecision` and still logs through the optional state-manager hook. Non-positive timeout values are rejected at construction.

Updated `ARCH_review_gate.md` with the resolved timeout behavior, removed the resolved Review Gate timeout item from `ARCHITECTURE.md` provisional contracts, marked implementation sequence row 10 as `Phase 9 complete, pending review`, and transitioned DEVPLAN to `state: review`.

Verification:
- `.venv/bin/python -m pytest tests/test_review_gate.py -q` - 14 passed
- `.venv/bin/python -m pytest -q` - 112 passed

### Phase 9 Review: Review Gate

**Mode:** Review
**Outcome:** Complete — two should-fix items applied, no must-fix items found

Review of `src/modules/review_gate/__init__.py` and `tests/test_review_gate.py` against `ARCH_review_gate.md`.

**Must fix:** None. Contract fully implemented: `ReviewDecision`, `AutoApproveReviewGate`, `TelegramReviewGate.submit()`, formatting, approve/edit/block parsing, channel filtering, unknown-command retry, optional state-manager hook, configurable timeout auto-block.

**Should fix applied:**
1. Removed `_pending` instance flag — written in `submit()` but never read by any consumer; dead code. ARCH documents it as state but no caller observes it, so removing it is cleaner.
2. Changed `except TimeoutError` to `except asyncio.TimeoutError` — more explicit and cross-version correct (pre-3.11, `asyncio.TimeoutError` is not a subclass of the built-in `TimeoutError`).

**Optional skipped:** None identified.

Verification:
- `python3 -m pytest -q` — 112 passed

### Phase 9 Complete: Review Gate

**Action:** Phase Complete
**Outcome:** Complete — audit gate set in DEVPLAN frontmatter

Phase 9 (Review Gate) is fully implemented and reviewed. All 14 focused tests pass; full regression 112 passed. Architecture sequence row 10 updated to "Phase 9 complete".

Next: Phase 10 — Adversarial module (optional LLM-based draft critique, skippable).

---

## Archived 2026-05-25 — Module 5 Phase 5: Persona

### Step 5.1: FileBasedPersona implementation

**Mode:** Build
**Outcome:** Complete — implemented Persona public API and focused tests
**Contract changes:** None

Implemented frozen `CoachingContext` and `FileBasedPersona` in `src/modules/persona/__init__.py`. `get_base_prompt` now reads `config/faction_prompt.txt`-style files, strips the `## CURRENT ROUND CONTEXT` section, raises `FileNotFoundError` naturally when the prompt is absent, and caches by `st_mtime_ns` for hot-reload behavior. `build_round_context` formats round metadata and all coaching context buckets with explicit empty-state bullets.

Added `tests/test_persona.py` covering public exports, missing file handling, fresh read, mtime reload, unchanged-mtime cache reuse, marker stripping, complete context formatting, empty fields, and unknown rounds remaining.

Verification:
- `.venv/bin/python -m pytest` — 68 passed

### Step 5.2: Sample faction persona config

**Mode:** Build
**Outcome:** Complete — added sample persona config and marked Phase 5 ready for review
**Contract changes:** `ARCHITECTURE.md` implementation sequence status updated for Persona

Created `config/faction_prompt.txt` with a sample England persona, strategic identity, negotiation rules, behavioral style, and a `## CURRENT ROUND CONTEXT` placeholder section compatible with `FileBasedPersona.get_base_prompt` stripping.

Updated `DEVPLAN.md` to mark both Persona implementation steps complete and transition Phase 5 to review. Updated `ARCHITECTURE.md` implementation status for Persona to ready for review.

Verification:
- `.venv/bin/python -m pytest` — 68 passed

### 2026-05-25 — Phase 5 Review

**Action:** Phase Review for Persona
**Outcome:** Pass — no must-fix or should-fix items found

Implementation matches ARCH_persona.md contract exactly: `CoachingContext` dataclass (frozen), `get_base_prompt` with mtime-based hot-reload and marker stripping, `build_round_context` with all coaching buckets and unknown-rounds handling, correct `__all__` exports. Sample config includes `## CURRENT ROUND CONTEXT` marker compatible with stripping logic.

Test coverage satisfies all DEVPLAN 5.1 requirements: FileNotFoundError, fresh read, hot-reload, unchanged-mtime cache, marker stripping, full-field formatting, empty fields, `rounds_remaining=None`.

Verification:
- `python3 -m pytest tests/` — 68 passed

DEVPLAN transitioned to `state: close`.

### 2026-05-25 — Phase 5 Complete

**Action:** Phase Complete for Persona
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `CoachingContext` (frozen dataclass), `FileBasedPersona` with `get_base_prompt` (mtime-based hot-reload, `## CURRENT ROUND CONTEXT` marker stripping, `FileNotFoundError` on missing file) and `build_round_context` (formatted round metadata and all coaching buckets with empty-state bullets). Added `config/faction_prompt.txt` sample England persona with `## CURRENT ROUND CONTEXT` placeholder. Phase Review found no must-fix or should-fix items.

All 68 tests pass (9 new persona tests + 59 regression). Persona is a leaf module with no dependencies beyond the filesystem.

Verification:
- `.venv/bin/python -m pytest tests/` — 68 passed

No new gotchas promoted. No contract changes — Persona exposes `FileBasedPersona` and `CoachingContext` as documented in `ARCH_persona.md`; no other modules depend on it yet.

---

## Archived 2026-05-25 — Module 4 Phase 4: Transport

### 2026-05-25 — Phase 4 Planned

**Action:** Phase Plan for Transport
**Outcome:** Planned — DEVPLAN moved to execute state

Defined Phase 4 as a Build phase with six testable steps covering toolkit dependency probing, shared Transport API exports, CLI transport, Telegram bot send path, Telegram bot listen path, and phase verification. Telethon user-account support remains deferred pending moderator confirmation that bot-to-bot messaging is unavailable.

No code was changed during planning.

### Step 4.1: Dependency probe and contract reconciliation

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Confirmed `toolkit` is not importable in this development environment, so Transport implementation will rely on dependency injection and fake-client tests until runtime wiring supplies the toolkit client. Reconciled `ARCH_transport.md` to the existing shared `modules.types.InboundEvent` shape used by Event Store instead of introducing a parallel Transport-only inbound event. Added the public Transport API surface: `OutboundMessage`, `TransportError`, and runtime-checkable `Transport` protocol, re-exporting the shared `InboundEvent` from `modules.transport`.

Added `tests/test_transport.py` covering public exports, outbound defaults, protocol conformance, and shared inbound event reuse.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 42 passed

### Step 4.2: Shared Transport exports

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Completed the shared Transport API surface with canonical channel validation, outbound recipient rules, and `normalize_inbound_event()` for adapter code to create the existing shared `InboundEvent` type without altering Event Store semantics. Public exports now include `VALID_CHANNELS`, `validate_channel`, and `normalize_inbound_event` alongside `OutboundMessage`, `TransportError`, `Transport`, and `InboundEvent`.

Expanded `tests/test_transport.py` for channel validation, private-message recipient requirements, public/coaching recipient rejection, and inbound normalization.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 45 passed

### Step 4.3: CLITransport

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `CLITransport` as an async JSON-lines adapter with injectable reader, writer, and clock. Outbound messages are serialized as one JSON object per line. Inbound lines are parsed as JSON objects, validated through the shared channel and event-normalization helpers, and yielded as shared `InboundEvent` instances. Writer, reader, malformed JSON, invalid payload shape, and invalid field values are wrapped in `TransportError`.

Expanded `tests/test_transport.py` with deterministic CLI send/listen coverage, timestamp fallback via injected clock, EOF behavior, writer/reader error propagation, and malformed inbound rejection.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 51 passed

### Step 4.4: TelegramBotTransport send path

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `TelegramBotTransport` send behavior with dependency-injected toolkit-compatible client, public/coaching chat routing, private recipient chat routing, configurable jitter, and bounded retry handling. The class does not import toolkit directly, matching the dependency probe result and keeping tests credential-free. Unconfigured private recipients and persistent send failures raise `TransportError`; invalid send configuration raises `ValueError`.

Expanded fake-client tests for public/private/coaching routing, jitter calls, retry success, persistent failure wrapping, missing private-recipient routes, and constructor validation.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 56 passed

### Step 4.5: TelegramBotTransport listen path

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `TelegramBotTransport.listen()` using dependency-injected `start_polling()` and `get_next_update()` client methods. The listener accepts dict-like and object-like updates, maps chat IDs to public/private/coaching channels, maps configured user IDs to factions or operator, falls back private-chat senders to their configured faction, falls back coaching senders to operator, and falls back unmatched public senders to system. Timestamps support ISO strings, `datetime`, epoch seconds, or injected-clock fallback. Telegram message IDs are preserved in the shared `telegram_msg_id` field.

Expanded fake-client tests for public/private/coaching inbound normalization, polling startup, fallback source and timestamp behavior, malformed update wrapping, unknown chat rejection, and polling failure wrapping.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed

### Step 4.6: Phase verification

**Mode:** Build
**Outcome:** Complete — DEVPLAN moved to review state
**Contract changes:** `ARCH_transport.md`

Ran the full current regression suite and Python bytecode compilation. Tightened `ARCH_transport.md` so the usage example matches the implemented dependency-injected `TelegramBotTransport` constructor and toolkit client boundary.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

### 2026-05-25 — Phase 4 Review

**Action:** Phase Review for Transport
**Outcome:** Complete — DEVPLAN moved to close state

Reviewed Transport implementation against `ARCH_transport.md` and the phase plan. No must-fix or should-fix issues were found. The implementation preserves existing Event Store `InboundEvent` semantics, keeps toolkit access dependency-injected, avoids direct Telegram SDK imports, and has focused fake-client coverage for CLI and Telegram paths.

Verification carried forward from Step 4.6:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

---

## Archived 2026-05-25 — Module 3 Phase 3: Coaching

### 2026-05-25 — Phase 3 Plan

**Action:** Phase Plan for Coaching
**Outcome:** Planned — state set to execute

Defined Phase 3 as a Build phase for a stateless, config-driven coaching parser. The plan keeps persistence, command dispatch, INTEL forwarding, and Orchestrator integration out of scope for this module.

Planned steps:
- 3.1 Add `config/coaching_routes.yaml`.
- 3.2 Implement public types, route loading, and initialization errors.
- 3.3 Implement tagged/free coaching parsing.
- 3.4 Implement slash command parsing.
- 3.5 Add focused parser tests.
- 3.6 Run Coaching and regression tests, then clean up exports/docs.

### Step 3.1: Add coaching routes config

**Mode:** Build
**Outcome:** Complete
**Contract changes:** Added `config/coaching_routes.yaml` implementing the Phase 3 route contract from `ARCH_coaching.md`.

Added the coaching tag routes and command allowlist used by `TaggedCoachingParser`. The file keeps routing data out of code: `INTEL` routes to `state_updater`, all other defined coaching tags and default free coaching route to `coaching_queue`, and the MVP slash commands are listed explicitly.

Verification:
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.2: Add coaching public types and route loader

**Mode:** Build
**Outcome:** Complete
**Contract changes:** Implemented the public Coaching API types from `ARCH_coaching.md`.

Added frozen `CoachingEvent` and `Command` dataclasses, a `TaggedCoachingParser` shell, route-rule normalization, YAML config loading, command allowlist normalization, and startup validation for missing or malformed routing config. The parser still returns default free coaching until tag and command parsing are implemented in the next steps.

Verification:
- `python3 - <<'PY' ... TaggedCoachingParser('config/coaching_routes.yaml') ... PY` — loaded expected tags, commands, and default route
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.3: Implement tagged and free coaching parsing

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Implemented case-insensitive tag parsing for configured coaching tags and canonical route output from the YAML route table. Unknown tags, malformed tag-like text, untagged input, and empty input fall back to default `FREE` coaching with the configured default route.

Verification:
- `python3 - <<'PY' ... parser.parse(...) assertions ... PY` — tagged, INTEL, unknown tag, and empty input cases passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.4: Implement slash command parsing

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Implemented config-allowlisted slash command parsing before coaching tag parsing. Command names are returned without the leading slash and are matched case-insensitively. `/edit: ...` and `/edit ...` populate `args["text"]`; other commands return empty args. Unknown slash commands fall back to `FREE` coaching.

Verification:
- `python3 - <<'PY' ... parser.parse(...) command assertions ... PY` — preview, status, edit, unknown slash, and tagged fallback cases passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.5: Add focused coaching parser tests

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Added `tests/test_coaching.py` covering public exports, route config loading, configured tag routes, INTEL routing, free-coaching defaults, malformed and unknown input fallback, command parsing, edit command arguments, unknown slash fallback, and config validation errors.

Verification:
- `python3 -m pytest tests/test_coaching.py` — 11 passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py tests/test_coaching.py` — 38 passed

### Step 3.6: Run full tests and clean up

**Mode:** Build
**Outcome:** Complete — state set to review
**Contract changes:** None.

Ran the full test suite and performed a small cleanup in command parsing: the command regex is wrapped for readability and configured command strings are normalized after trimming. Phase 3 implementation is complete and ready for review.

Verification:
- `python3 -m pytest` — 38 passed
- `python3 -m pytest tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 38 passed

### 2026-05-25 — Phase 3 Review

**Action:** Phase Review — Coaching
**Outcome:** Passed — no must-fix or should-fix items found. State set to close.

Reviewed `src/modules/coaching/__init__.py` and `tests/test_coaching.py` against `ARCH_coaching.md`.

Contract compliance:
- `parse(str) -> CoachingEvent | Command` signature matches exactly.
- No exceptions raised for unrecognized input — returns FREE CoachingEvent.
- `CoachingEvent` and `Command` frozen dataclasses match ARCH types.
- All routing loaded from `config/coaching_routes.yaml`, no hardcoded routing logic.
- YAML structure matches ARCH exactly: 5 tags + default + 10 commands.
- INTEL -> state_updater, all others -> coaching_queue, unknown tag -> FREE.
- `/edit:` and `/edit ` argument variants both handled.
- Pure parsing function — no state, persistence, dispatch, or Orchestrator coupling.
- `__all__` exports `TaggedCoachingParser`, `CoachingEvent`, `Command`, `RouteRule`, `load_routes_config`.
- Phase scope respected — no coaching queue, no INTEL forwarding, no Orchestrator integration.

All 38 tests pass (11 coaching + 27 regression).

---

## Archived 2026-05-25 — Module 1 Phase 1: Event Store + State Manager

### Phase 1: Core Storage

### 2026-05-25 — Phase Plan (1.0)

**Action:** Phase Plan for Phase 1 (Event Store + State Manager)
**Outcome:** Step breakdown written to DEVPLAN.md. 6 steps defined.

Steps planned:
- 1.1 — Shared types module (`src/modules/types.py`): InboundEvent, StoredEvent, EventFilter, StatePatch, PatchSource
- 1.2 — SQLiteEventStore implementation with append/query, WAL mode
- 1.3 — Event Store tests
- 1.4 — State patch JSON schema (`config/schemas/state_patch.json`)
- 1.5 — SQLiteStateManager implementation with all domain tables, schema validation, audit log
- 1.6 — State Manager tests

Key design decisions confirmed from ARCH files: single SQLite file with WAL mode, shared types module to avoid circular imports, apply_patch validates then audits then applies.

**State transition:** plan → execute

### Step 1.1: Shared types module

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/types.py`

Added shared dataclasses for inbound and stored events, event filtering, state
patches, and patch audit sources. These types keep Event Store and State
Manager contracts independent of each other while giving later Transport and
Extraction work a common import surface.

### Step 1.2: SQLiteEventStore implementation

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/event_store/__init__.py`

Implemented the append-only SQLite event store with WAL enabled on every
connection, table/index initialization, UUID event IDs, and parameterized query
filters for round, sender/source, channel, timestamp, and limit.

### Step 1.3: Event Store tests

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** None

Added async pytest coverage for Event Store append/query behavior, including
WAL mode, round/source/channel/since filters, timestamp ordering, limit
handling, and empty result cases.

### Step 1.4: State patch JSON schema

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `config/schemas/state_patch.json`

Added the JSON schema used by State Manager to validate extraction patches for
faction state, promises, coalitions, and inconsistencies before any domain
tables are updated.

### Step 1.5: SQLiteStateManager implementation

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/state_manager/__init__.py`

Implemented the State Manager API with WAL-backed SQLite table ownership,
schema validation at patch application time, audit logging before domain writes,
parameterized get/query operations, and full-state snapshots for Analyst input.

### Step 1.6: State Manager tests

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** None

Added pytest coverage for State Manager initialization, WAL mode, patch
validation, audit logging, domain table upserts, public get/query behavior,
unknown entity errors, and full-state filtering for pending/unspent records.

### 2026-05-25 — Phase 1 Review

**Action:** Architecture contract review for Event Store and State Manager
**Outcome:** Clean — all 9 tests pass, no must-fix or should-fix items

Review checklist:
- Event Store API signatures match ARCH exactly (append, query)
- messages table schema and indices match ARCH
- WAL mode enabled on every connection
- All queries parameterised; no SQL injection surface
- State Manager API signatures match ARCH (get, query, apply_patch, get_full_state)
- All 10 domain tables created at init
- apply_patch validates first, writes audit log, then applies domain changes — in one transaction
- get_full_state returns pending promises and unspent inconsistencies only
- Unknown entity_type and column raise ValueError
- Schema (state_patch.json) enforces required fields, non-empty strings, score range [0,1], promise status enum

No contract drift from ARCH files. No gotchas to promote.

**State transition:** review → close

---

## Archived 2026-05-25 — Module 2 Phase 2: Extraction

### 2026-05-25 — Phase Plan (2.0)

**Action:** Phase Plan for Extraction
**Outcome:** Step breakdown written to DEVPLAN.md. 4 steps defined.

Defined a Build-regime plan for the Extraction module. Scope covers the public extraction API, local JSON/schema enforcement for plain-text LLM responses, deterministic rule-based fallback behavior, prompt configuration, and focused fake-provider tests.

Scope decision: Extraction remains stateless; batching/debounce behavior stays with Orchestrator.

**State transition:** plan → execute

### Step 2.1: Extraction API and Patch Validation Helpers

**Mode:** Build
**Outcome:** Complete — extraction result type, prompt/schema loading, JSON parsing, and state patch validation helpers added with focused tests.
**Contract changes:** None

Added the public `ExtractionResult` type and reusable helper functions for loading prompts, loading JSON schemas, parsing plain-text LLM responses as JSON objects, and validating decoded patch data against the state patch schema before wrapping it in `StatePatch`.

### Step 2.2: Rule-Based Extraction Fallback

**Mode:** Build
**Outcome:** Complete — deterministic fallback extraction added for simple promises, coalitions, inconsistencies, and no-match empty patches.
**Contract changes:** `config/schemas/state_patch.json` now permits an empty root object so fallback extraction can return a valid no-op patch.

Implemented `RuleBasedExtractor` as a stateless async fallback with deterministic IDs and schema validation for every returned patch. The root schema now accepts `{}` while preserving validation for entity objects when they are present.

### Step 2.3: OpenAI Structured Extractor

**Mode:** Build
**Outcome:** Complete — LLM-backed extractor added with injected toolkit-compatible client, prompt assembly, COMMODITY tier usage, JSON parsing, schema validation, and failure reporting.
**Contract changes:** None

Implemented `OpenAIStructuredExtractor` without direct provider SDK imports. The extractor builds system/user messages from the configured prompt, schema, current state, trigger type, and input text, marks `intel_correction` inputs as high-confidence operator intel, and returns failed `ExtractionResult` values for LLM exceptions, invalid JSON, invalid schema, and non-text responses.

### Step 2.4: Extraction Prompt and Phase Readiness

**Mode:** Build
**Outcome:** Complete — state updater prompt added, public exports verified, and phase regression tests passed.
**Contract changes:** None

Added `config/prompts/state_updater.txt` with JSON-only state patch guidance for the LLM extractor. Added tests that verify the configured prompt loads and the public module exports include both primary and fallback extractors. Phase 2 is ready for review.

---

## Archived 2026-05-27 — Module 10 Phase 10: Adversarial

### Phase 10 Plan

**Mode:** Discuss
**Outcome:** Planned - Adversarial phase broken into three Build steps and state transitioned to execute
**Contract changes:** Confirmed local JSON schema enforcement for adversarial analysis and that skip/persistence behavior remains with Orchestrator

Planned `AdversarialResult` and `LLMAdversarialReader` implementation against `ARCH_adversarial.md`: core reader contract and failure handling first, structured prompt/schema validation second, and documentation/regression cleanup third. All LLM behavior will use toolkit-compatible dependency injection and fake clients in tests.

Updated `ARCHITECTURE.md` Implementation Sequence row 11 to `In progress`.

### Step 10.1: Core adversarial reader

**Mode:** Build
**Outcome:** Complete - implemented Adversarial result type, core reader contract, and focused tests
**Contract changes:** Added `AdversarialResult` and `LLMAdversarialReader` public exports in `src/modules/adversarial/__init__.py`

Implemented the Phase 10 reader shell with dependency-injected toolkit-compatible LLM client calls. `LLMAdversarialReader.read()` rejects blank drafts before calling the client, forwards the system prompt, schema, draft, config, and tier to the injected client, reports provider exceptions through `AdversarialResult.success=False`, and remains stateless.

Added `tests/test_adversarial.py` coverage for result contract fields, blank draft handling without client calls, client exception failure, prompt/draft forwarding, and config/tier forwarding.

Verification:
- `.venv/bin/python -m pytest tests/test_adversarial.py -q` - 5 passed

### Step 10.2: Structured adversarial JSON

**Mode:** Build
**Outcome:** Complete - schema-validated adversarial analysis, prompt/schema artifacts, and regression coverage added
**Contract changes:** Added `config/prompts/adversarial.txt`, `config/schemas/adversarial.json`, and `validate_adversarial_analysis`

Implemented local JSON parsing and Draft 2020-12 schema validation for adversarial reads. Successful reads now return the validated analysis dict; malformed JSON, schema violations, non-text LLM responses, blank drafts, and provider exceptions all return `AdversarialResult.success=False` without raising to callers.

Created the adversarial prompt and schema artifacts for the four analysis buckets: revealed position, commitments, exploitable issues, and likely counter-moves. Expanded focused coverage for valid analysis, malformed JSON, missing required keys, wrong value types, and non-text provider responses.

Verification:
- `.venv/bin/python -m pytest tests/test_adversarial.py -q` - 9 passed
- `.venv/bin/python -m pytest -q` - 121 passed

### Step 10.3: Documentation cleanup and review handoff

**Mode:** Build
**Outcome:** Complete - docs updated, full regression verified, state transitioned to review
**Contract changes:** Updated `ARCH_adversarial.md` and `ARCHITECTURE.md`

Aligned the documented adversarial analysis keys with the schema and tests, using `commits_to` consistently with the existing ARCH usage example. Updated `ARCH_adversarial.md` to list the concrete schema keys, marked implementation sequence row 11 as `Phase 10 complete, pending review`, added the Phase 10 DEVPLAN summary, and transitioned DEVPLAN to `state: review`.

Verification:
- `.venv/bin/python -m pytest tests/test_adversarial.py -q` - 9 passed
- `.venv/bin/python -m pytest -q` - 121 passed

### Phase 10 Review: Adversarial

**Mode:** Review
**Outcome:** Passed — no must-fix, no should-fix items
**Verdict:** Clean. Transitioning to close.

Reviewed `AdversarialResult`, `LLMAdversarialReader`, schema artifacts, and prompt against ARCH_adversarial.md contract. All public API signatures match. Blank draft rejection, client exception handling, JSON parse failures, and schema violations all correctly return `success=False` without raising. Config artifacts (`adversarial.txt`, `adversarial.json`) present with correct structure. `validate_adversarial_analysis` exported in `__all__` mirrors the established extraction module pattern — acceptable.

Full regression: 121 passed.

### 2026-05-26 — Phase 10 Complete

**Action:** Phase Complete for Adversarial
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `AdversarialResult`, `LLMAdversarialReader`, local JSON parsing and Draft 2020-12 schema validation, `config/prompts/adversarial.txt`, and `config/schemas/adversarial.json`. Phase Review found no must-fix or should-fix items.

All 121 tests pass (9 adversarial tests + 112 regression). Adversarial remains optional and stateless; Orchestrator owns skip behavior and persistence.

Verification:
- `.venv/bin/python -m pytest -q` — 121 passed

No new gotchas promoted. No contract changes require propagation beyond the Phase 10 Adversarial API and schema already captured in `ARCH_adversarial.md` and `ARCHITECTURE.md`.

---

## Archived 2026-05-27 — Module 12 Phase 11: Orchestrator and Adapter Probes

Phase 11 implemented the final Orchestrator module: `config/pipeline.yaml`, registry lookup, startup validation, event loop, operator command routing, debounced extraction, round boundaries, dual-analyst intelligence persistence, response pipeline, per-call cost gates, and `src/main.py`. Phase Review applied three should-fix items and found no must-fix issues. Full regression reached 165 passing tests.

Post-phase source-level toolkit probes found integration mismatches between earlier fakes and real toolkit APIs. Adapter fixes introduced `ToolkitLLMAdapter` and `DiplomatCostGate`, corrected Telegram client construction, updated `pipeline.yaml` LLM provider shape, and were verified on the Pi with real toolkit imports. This produced D-13: external dependency fakes must be derived from source, not prose.

Verification:
- `python3 -m pytest` — 165 passed
- Pi toolkit probe — `llm_client`, `telegram_client`, and `cost_accountant` signatures confirmed

---

## Archived 2026-05-27 — Module 12 Phase 12: Orchestrator Refactor

Phase 12 extracted `ToolkitLLMAdapter` and `DiplomatCostGate` into `src/adapters.py`, expanded `SQLiteStateManager` with public persistence APIs for coaching, intelligence, game state, adversarial reads, and coaching consumption, and removed Orchestrator raw SQLite fallback writes. It also typed public Orchestrator event/pipeline methods with `InboundEvent`.

Phase Review applied one should-fix: move the round-boundary regex import to module scope. No must-fix items were found.

Verification:
- `python3 -m pytest` — 170 passed

---

## Archived 2026-05-27 — Phase 15: Live Smoke Test Environment Setup

### 2026-05-27 — Phase 15 Planned

**Action:** Phase Plan for Live Smoke Test — Environment Setup
**Outcome:** Complete — Phase 15 plan accepted and ready for execution

Planned the live smoke-test preparation phase around environment artifacts and Pi validation:
- `.env.template` for Telegram and provider credentials
- `config/pipeline_smoke.yaml` using OpenAI `gpt-4.1-mini`, tight budgets, live review gate, and adversarial disabled
- Pi startup validation for toolkit imports, config validation, Telegram connection, and online banner
- human-driven Telegram smoke checklist from `diplomat-testing-doc.md` §5b

Scope decision logged in `DECISIONS.md` as D-17. Next step: 15.1 creates `.env.template` and `config/pipeline_smoke.yaml`.

### Step 15.1: Smoke environment artifacts

**Mode:** Build
**Outcome:** Complete — `.env.template` and OpenAI-only smoke pipeline config added
**Contract changes:** None

Created `.env.template` with placeholders and comments for Telegram bot token, public/coaching channel IDs, operator user IDs, OpenAI API key, and optional Anthropic API key.

Added `config/pipeline_smoke.yaml` as a dedicated live-smoke config copied from the production pipeline shape with `gpt-4.1-mini` for both primary and secondary OpenAI providers, `RuleBasedExtractor`, `TelegramReviewGate`, review gate enabled, adversarial disabled, and budgets set to `$0.50` per round / `$2.00` per session.

Verification:
- `python3 -m py_compile src/main.py` — passed
- `python3 -m pytest -q` — 187 passed

Next step: 15.2 validates startup on the Pi with real `.env` values and toolkit installed.

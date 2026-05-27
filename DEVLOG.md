# Diplomat — Development Log

<!-- Chronological record of what happened during development.
     Each step gets a structured entry. This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

## Module 1: Event Store + State Manager

### 2026-05-25 — Phase 1 Complete

**Action:** Phase Complete for Event Store + State Manager
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and focused tests for both modules. Detailed Phase 1 development entries were archived to `DEVLOG_archive.md`.

Verification:
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py` — 9 passed

No new gotchas were promoted. No contract changes require propagation beyond the Phase 1 storage interfaces already captured in the ARCH files.

## Module 2: Extraction

Phase 2 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 2 Complete

**Action:** Phase Review and Phase Complete for Extraction
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, extraction validators, rule-based fallback, fake-provider test coverage, and system prompt. Phase Review applied one should-fix: `load_schema` now inlines JSON loading with schema-specific error messages rather than routing through `parse_json_object` (which emitted misleading "LLM response" error text for schema file failures).

All 27 tests pass. Structured output enforcement resolved: local prompt + parse + jsonschema validate is sufficient — no toolkit extension needed.

Verification:
- `python3 -m pytest tests/test_extraction.py tests/test_event_store.py tests/test_state_manager.py` — 27 passed

## Module 3: Coaching

Phase 3 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 3 Complete

**Action:** Phase Complete for Coaching
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `config/coaching_routes.yaml`, frozen Coaching result dataclasses, `TaggedCoachingParser`, route config validation, case-insensitive tagged coaching parsing, default free coaching fallback, allowlisted slash command parsing, and edit command argument parsing. Phase Review found no must-fix or should-fix items.

All 38 tests pass. Coaching remains a pure parser with no persistence, dispatch, INTEL forwarding, or Orchestrator coupling.

Verification:
- `python3 -m pytest tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 38 passed

No new gotchas were promoted. No contract changes require propagation beyond the Phase 3 Coaching API and route config already captured in `ARCH_coaching.md`.

## Module 4: Transport

Phase 4 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 4 Complete

**Action:** Phase Complete for Transport
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed shared `OutboundMessage`, `TransportError`, `Transport`, channel validation, inbound normalization helpers, `CLITransport`, and dependency-injected `TelegramBotTransport` send/listen behavior. Phase Review found no must-fix or should-fix items.

All 59 tests pass. Transport remains toolkit-bound at the adapter boundary without direct Telegram SDK imports; local tests use fake toolkit-compatible clients because `toolkit` may be absent in the development environment.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

Promoted gotchas:
- Bot vs. user account question remains a deployment decision; implement `TelethonUserTransport` only if the moderator confirms bot-to-bot messaging is unavailable.
- Transport tests use dependency-injected toolkit-compatible fakes when `toolkit` is not installed locally.

No contract changes require propagation beyond `ARCH_transport.md`, `ARCHITECTURE.md`, and the existing `PROJECT.md` risk wording updated during close.

## Module 5: Persona

Phase 5 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 5 Complete

**Action:** Phase Complete for Persona
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `CoachingContext`, `FileBasedPersona`, hot-reload behavior, dynamic round-context formatting, and sample `config/faction_prompt.txt`. All 68 tests passed. Detailed Phase 5 development entries were archived to `DEVLOG_archive.md`.

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

Phase 9 development entries archived to `DEVLOG_archive.md` (2026-05-26).

Phase 10 development entries archived to `DEVLOG_archive.md` (2026-05-27).

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

## Phase 12: Orchestrator Refactor Plan

### 2026-05-27 — Phase plan

**Mode:** Discuss
**Outcome:** Phase 12 plan recorded for adapter extraction, State Manager persistence API expansion, and Orchestrator SQLite fallback removal

Phase 12 is a Build-regime refactor, not a feature phase. The planned work splits misplaced Orchestrator concerns into their owning modules: toolkit adapters move to `src/adapters.py`, persistence helpers move into `SQLiteStateManager`, and Orchestrator calls those explicit APIs directly.

The cross-module State Manager/Orchestrator contract expansion is intentional phase scope, documented in DEVPLAN and DECISIONS, so workers should not escalate it as emergent contract drift.

### Step 12.1: Extract adapters to src/adapters.py

**Mode:** Build
**Outcome:** Complete — adapter classes moved out of Orchestrator; compile check and full regression passed
**Contract changes:** `src/adapters.py` now owns `ToolkitLLMAdapter` and `DiplomatCostGate`; `src/orchestrator.py` no longer exports them

Moved `ToolkitLLMAdapter` and `DiplomatCostGate` into the new `src/adapters.py` module and updated `src/main.py` to import adapters from there. Removed both adapter names and class definitions from `src/orchestrator.py` so Orchestrator returns to composition/event-loop responsibility.

Verification:
- `python3 -m py_compile src/adapters.py src/orchestrator.py src/main.py` — passed
- `python3 -m pytest` — 165 passed

Next step: 12.2 expands `SQLiteStateManager` with the five persistence APIs now planned for direct Orchestrator calls.

### Step 12.2: Expand State Manager API with persistence methods

**Mode:** Build
**Outcome:** Complete — five persistence methods added, documented, and covered by focused tests
**Contract changes:** `SQLiteStateManager` public API now includes `store_coaching`, `store_intelligence`, `set_game_state`, `store_adversarial_read`, and `mark_coaching_consumed`; `ARCH_state_manager.md` updated

Added explicit State Manager write helpers for coaching entries, intelligence records, game state key/value updates, adversarial read records, and coaching consumption. Each method uses the existing SQLite connection helper, State Manager-owned tables, and `_now()` timestamps where the table records creation time.

Focused tests verify row insertion/update behavior, JSON round-tripping with sorted dumps for persisted analysis payloads, and coaching consumed-state updates. The full suite now includes 170 tests.

Verification:
- `python3 -m pytest tests/test_state_manager.py` — 10 passed
- `python3 -m pytest` — 170 passed

Next step: 12.3 removes Orchestrator raw SQLite fallbacks and calls the new State Manager API directly.

### Step 12.3: Remove SQLite fallbacks from Orchestrator

**Mode:** Build
**Outcome:** Complete — Orchestrator now calls State Manager persistence APIs directly and event parameters use `InboundEvent`
**Contract changes:** Orchestrator now requires the expanded State Manager persistence API from Step 12.2

Removed raw SQLite fallback write paths from `_store_coaching`, `_store_intelligence`, `_set_game_state`, `_store_adversarial_read`, and `_mark_coaching_consumed`. Those helpers now call the State Manager methods directly, keeping table ownership inside the State Manager. `sqlite3` remains in Orchestrator only for pre-flight database initialization.

Typed `process_event()` and `run_response_pipeline()` with `InboundEvent` where they previously accepted `Any`. The existing Orchestrator fake state manager already implements the expanded persistence API, so the behavior tests continue to exercise the production contract.

Verification:
- `python3 -m pytest tests/test_orchestrator.py` — 44 passed
- `python3 -m pytest` — 170 passed

Next step: 12.4 performs architecture/doc cleanup and final regression verification before review.

### Step 12.4: Documentation cleanup and regression verification

**Mode:** Build (cleanup)
**Outcome:** Complete — ARCHITECTURE.md coupling notes updated, full regression passes, phase ready for review

Updated `ARCHITECTURE.md` coupling notes:
- `ToolkitLLMAdapter` reference now points to `src/adapters.py` (was `orchestrator.py`)
- `DiplomatCostGate` reference now points to `src/adapters.py`
- Added explicit `Orchestrator ↔ State Manager` write-path coupling note documenting the 5 persistence methods

Verification:
- `python3 -m pytest` — 170 passed

Phase 12 complete: adapter extraction, State Manager API expansion, and Orchestrator fallback removal all verified. State transitions to review.

### 2026-05-27 — Phase 12 Review

**Action:** Phase Review for Phase 12 (Orchestrator Refactor)
**Outcome:** Complete — one should-fix applied; no must-fix items

Review findings:
- **Must fix:** None.
- **Should fix (applied):** `import re` was a local import inside `_check_round_boundary`; moved to module level alongside other stdlib imports.
- **Optional (skipped):** `_store_coaching` returns `coaching_id` but caller never captures it; private helpers `_route_operator_event`/`_enqueue_message_extraction`/`_debounced_message_extraction` still use `event: Any` (spec only required typing the two public methods).

Verification:
- `python3 -m pytest` — 170 passed

Phase 12 ready for human audit. Transitioning to `state: close`.

### 2026-05-27 — Phase 12 Complete

**Action:** Phase Complete for Orchestrator Refactor
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Closed Phase 12 after adapter extraction, State Manager persistence API expansion, Orchestrator SQLite fallback removal, and public `InboundEvent` typing. Phase Review applied one should-fix and found no must-fix issues.

Integration check:
- Orchestrator now writes coaching, intelligence, game state, adversarial reads, and coaching consumption through State Manager's public methods.
- No module imports the orchestration layer; module coupling remains through shared types and configured dependencies.
- No bridge logic is needed between Orchestrator and State Manager beyond the new public State Manager methods documented in `ARCH_state_manager.md` and `ARCHITECTURE.md`.

Verification:
- `python3 -m pytest -q` — 170 passed

Phase 11 development and post-phase adapter probe entries archived to `DEVLOG_archive.md` (2026-05-27).

No new gotchas promoted. Contract changes are already propagated to `ARCH_state_manager.md`, `ARCH_orchestrator.md`, and `ARCHITECTURE.md`.

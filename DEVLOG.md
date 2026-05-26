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

Phase 9 (Review Gate) is the next module: human approval workflow via toolkit/telegram_client.

## Module 9: Review Gate

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
**Outcome:** Complete — audit gate set, DEVPLAN blocked awaiting human review

Phase 9 (Review Gate) is fully implemented and reviewed. All 14 focused tests pass; full regression 112 passed. Architecture sequence row 10 updated to "Phase 9 complete". DEVPLAN blocked with `awaiting-human-audit`.

Next: Phase 10 — Adversarial module (optional LLM-based draft critique, skippable).

Phase 10 (Adversarial) is the next module: optional LLM-based draft critique via toolkit/llm_client.

## Module 10: Adversarial

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

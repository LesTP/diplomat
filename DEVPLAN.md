---
phase: 14
blocked: false
state: execute
steps_remaining: 7
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before deployment; implement `TelethonUserTransport` only if bot-to-bot messaging is unavailable
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop
  - `toolkit` lives at `../toolkit` and must be installed editable into the diplomat venv (`<venv>/bin/python3 -m pip install -e ../toolkit`). It is not declared in `pyproject.toml` to avoid a misleading install contract — fresh `pip install -e .` cannot resolve `toolkit` from PyPI, so the editable install is a one-time per-host setup step. Module-level tests use dependency-injected fakes for isolation; that pattern is fine and should continue, but integration paths in Orchestrator must exercise real `toolkit` imports
  - Debounce strategy resolved (11.2): per-message cooldown — each new message cancels and reschedules the extraction timer; avoids redundant LLM calls under burst traffic
  - Cost governance resolved (11.4): CostBudget resets per round (strict per-round cap); session totals tracked in cost_ledger.jsonl by CostAccountant
  - CostAccountant is a thin wrapper around the module-level llm_client call: Orchestrator checks budget before dispatching each LLM call and alerts operator on over-budget
  - Before deployment, install `../toolkit` editable and run live probes for `llm_client`, `telegram_client`, and `cost_accountant`; this environment cannot import `toolkit`, so Phase 11 close recorded probe specs rather than live matches

## Current Status

- **Phase** — Phase 14: Layer 3 transcript replay tests.
- **Focus** — Write synthetic game transcripts that exercise RuleBasedExtractor patterns, replay them through the full pipeline, assert on final state.
- **Blocked/Broken** — none.

## Phase 14: Layer 3 — Transcript Replay Tests

Regime: Build. Scope: Create synthetic game transcript fixtures that use `RuleBasedExtractor` regex patterns for deterministic extraction, implement a transcript replay test module, and verify that multi-round pipeline execution accumulates correct promise/coalition/inconsistency state. Reference: `diplomat-testing-doc.md` §5.4.

**Design constraints:**
- No real API calls — reuses Phase 13 integration infrastructure (TestTransport, FakeLLMClient, StubAnalyst, FakeCostAccountant, conftest.py `pipeline` fixture)
- Transcript messages must match `RuleBasedExtractor` regex patterns for deterministic state changes:
  - Promise: `"{Faction} promises {Faction} {content}."` (faction names must start with uppercase)
  - Coalition: `"{Faction} and {Faction} formed a coalition."`
  - Inconsistency: `"{Faction} contradicts {description}."`
- Round boundaries use `[ROUND END]` signal (matching `pipeline_test.yaml` round detection pattern)
- Each transcript is a JSON file in `tests/integration/fixtures/transcripts/` with events + expected final state
- Replay tests inject events via TestTransport, allow processing time after each event and round boundary, then assert on `state_manager.query()` results
- Existing 182 tests must continue to pass

Steps:

- [ ] 14.1 — **Create transcript fixture: cooperative 3-round game.** Create `tests/integration/fixtures/transcripts/` directory and `cooperative_3round.json`. Write a 3-round transcript with ~8-10 events covering: one promise (round 1), one coalition formation (round 2), and a second promise (round 3), each using `RuleBasedExtractor` regex patterns. Include `expected_final_state` with 2 promises (both pending) and 1 coalition. Include 3 `[ROUND END]` signals. Validate the fixture parses cleanly. Run full regression.

- [ ] 14.2 — **Create transcript fixture: betrayal arc.** Create `betrayal_arc.json`. Write a 3-round transcript where: faction A promises faction B (round 1), faction A contradicts that promise (round 2, matching `_INCONSISTENCY_RE`), and faction A forms a coalition with faction C (round 3). Include `expected_final_state` with the promise, 1 inconsistency, and 1 coalition. Run full regression.

- [ ] 14.3 — **Implement replay test module.** Create `tests/integration/test_replay.py` with:
  - A `replay_transcript(pipeline, fixture_path)` helper that loads the JSON, injects each event via `TestTransport.inject()` with appropriate sleep intervals (short for regular messages, longer after round boundaries for analysis), and returns the final state.
  - `test_cooperative_3round_promises` — replays `cooperative_3round.json`, asserts 2 pending promises exist with correct from/to factions.
  - `test_cooperative_3round_coalition` — replays same transcript, asserts 1 coalition exists with correct factions.
  - `test_cooperative_3round_intelligence` — replays same transcript, asserts 3 intelligence records (one per round boundary).
  - `test_betrayal_arc_inconsistency` — replays `betrayal_arc.json`, asserts 1 inconsistency exists.
  - `test_betrayal_arc_promise_and_coalition` — replays same transcript, asserts the promise and coalition are both present.
  Run focused + full regression.

- [ ] 14.4 — **Documentation cleanup and regression.** Verify full test suite. Update DEVPLAN Phase 14 summary. Append DEVLOG entry. Update `diplomat-testing-doc.md` build order table to mark transcript replay as complete. Transition to `state: review`.

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

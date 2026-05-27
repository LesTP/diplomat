---
phase: 13
blocked: false
state: review
steps_remaining: 2
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

- **Phase** — Phase 13: Layer 3 pipeline integration tests.
- **Focus** — Phase 13 implementation complete; ready for Layer 3 integration test review.
- **Blocked/Broken** — none.

## Phase 13: Layer 3 — Pipeline Integration Tests

Regime: Build. Scope: Build the test infrastructure needed for integration tests (TestTransport, StubAnalyst, test pipeline config, shared fixtures), then implement integration tests that exercise the full Orchestrator pipeline with fake LLM clients and no real API calls. Reference: `diplomat-testing-doc.md` §2, §5.

**Design constraints:**
- No real API calls — all LLM modules use a `FakeLLMClient` that returns canned responses via `module_overrides`
- No `:memory:` SQLite — use `tmp_path` fixtures (SQLiteStateManager creates new connections per call; `:memory:` gives a fresh empty DB each time)
- TestTransport implements `send()`/`listen()` directly via asyncio.Queue — not a CLITransport wrapper
- StubAnalyst returns fixture-loaded `AnalysisResult` — no LLM call
- Orchestrator.start() blocks on listen, so integration tests run it in a background `asyncio.create_task` and inject events via TestTransport
- All existing 170 unit tests must continue to pass

Steps:

- [x] 13.1 — **Test infrastructure: TestTransport + StubAnalyst + factories.** Create `tests/helpers/__init__.py`, `tests/helpers/test_transport.py` (TestTransport with inject/send/listen/get_output/clear_output via asyncio.Queue), `tests/helpers/stub_analyst.py` (StubAnalyst loading fixture JSON → AnalysisResult), and `tests/helpers/factories.py` (make_event, make_round_end_event, FakeLLMClient, FakeCostAccountant helper functions). Register `StubAnalyst` in `src/registry.py`. Create `tests/integration/__init__.py` and `tests/integration/fixtures/` with `intelligence_stub.json` (valid against `config/schemas/intelligence.json`) and `test_persona.txt` (minimal faction persona). Verify `python3 -c "from tests.helpers.test_transport import TestTransport"` imports cleanly. Run full regression.

- [x] 13.2 — **Test pipeline config + integration conftest.** Create `config/pipeline_test.yaml` matching the real `pipeline.yaml` schema but with `CLITransport`, `RuleBasedExtractor`, `StubAnalyst`, `AutoApproveReviewGate`, and `test_persona.txt` paths. Create `tests/integration/conftest.py` with a `pipeline` fixture that constructs Orchestrator with `pipeline_test.yaml`, passes TestTransport + FakeLLMClient + FakeCostAccountant via module_overrides, runs `start()` in a background task, and tears down with `shutdown()` + task cancel in cleanup. Verify the fixture constructs and starts without error. Run full regression.

- [x] 13.3 — **Core pipeline flow tests.** Create `tests/integration/test_pipeline_flow.py` with tests: (1) game message ingested → event stored + extraction runs, (2) operator PRIORITY coaching → stored in coaching table as unconsumed, (3) operator INTEL coaching → state_change_log entry with trigger_type=intel_correction, (4) round boundary signal `[ROUND END]` → intelligence table populated with analysis_json, (5) direct address to faction_id → public response generated and sent, (6) `/preview` command → response pipeline runs. Each test injects events via TestTransport.inject() and asserts on state_manager.query() results after an asyncio.sleep for processing. Run focused + full regression.

- [x] 13.4 — **Failure handling tests.** Create `tests/integration/test_failure_handling.py` with tests: (1) extraction failure → pipeline continues running + event still in store, (2) secondary analyst failure → intelligence stored with primary only, (3) adversarial failure → response still posted with warning, (4) double generation failure → operator alerted on coaching channel, (5) transport send failure after 3 retries → operator alerted. Use monkeypatch to inject failures into specific module methods. Run focused + full regression.

- [x] 13.5 — **Documentation cleanup and regression.** Verify full test suite (170 existing + new integration tests). Update DEVPLAN Phase 13 summary. Append DEVLOG entry. Update `diplomat-testing-doc.md` Layer 3 status to "Complete" with test count. Transition to `state: review`.

Summary: Implemented Layer 3 pipeline integration infrastructure and tests: `TestTransport`, `StubAnalyst`, shared fake factories, `pipeline_test.yaml`, async integration pipeline fixture, fixture smoke test, six core pipeline flow tests, and five failure-handling tests. Full regression: 182 passed (170 pre-existing tests + 12 integration tests). Phase ready for review.

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

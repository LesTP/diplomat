---
phase: 12
blocked: false
state: execute
steps_remaining: 3
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

- **Phase** — Phase 12: Orchestrator refactor — adapter extraction, State Manager contract expansion, SQLite fallback removal.
- **Focus** — Reduce Orchestrator complexity by moving misplaced concerns to their proper modules.
- **Blocked/Broken** — none.

## Phase 12: Orchestrator Refactor

Regime: Build. Scope: Extract adapter classes to their own module, expand the State Manager's public API to cover persistence operations currently handled by Orchestrator SQLite fallbacks, remove all fallback persistence code from the Orchestrator, and type the event parameter correctly. No new features — pure refactor with full regression verification.

**Cross-module note:** This phase intentionally modifies both State Manager and Orchestrator as a planned contract expansion. The State Manager gains 5 new methods; the Orchestrator drops its fallback implementations and calls the State Manager directly. Both sides are specified below. This is not an emergent scope change — do not escalate under WORKER_SPEC §5 "contract change would affect other modules."

Steps:

- [ ] 12.1 — **Extract adapters to `src/adapters.py`.** Move `ToolkitLLMAdapter` and `DiplomatCostGate` classes from `src/orchestrator.py` to a new `src/adapters.py`. Remove them from `orchestrator.py`'s `__all__`. Update `src/main.py` to import from `adapters` instead of `orchestrator`. Run `python3 -m py_compile src/adapters.py src/orchestrator.py src/main.py` and full regression.

- [ ] 12.2 — **Expand State Manager API with 5 persistence methods.** Add the following async methods to `SQLiteStateManager` in `src/modules/state_manager/__init__.py`, each using the existing `self._connect()` helper and `self._now()` timestamp:
  - `store_coaching(self, coaching_id: str, tag: str, content: str, consumed: bool) -> None` — INSERT into coaching table
  - `store_intelligence(self, round_number: int, provider: str, analysis: dict) -> None` — INSERT into intelligence table with `json.dumps(analysis, sort_keys=True)` for analysis_json
  - `set_game_state(self, key: str, value: str) -> None` — INSERT OR UPDATE into game_state table
  - `store_adversarial_read(self, round_number: int, analysis: dict) -> None` — INSERT into adversarial_reads table with `json.dumps(analysis, sort_keys=True)` for analysis_json
  - `mark_coaching_consumed(self) -> None` — UPDATE coaching SET consumed=1 WHERE consumed=0

  Add focused tests for each new method in `tests/test_state_manager.py`: verify row insertion/update, verify data round-trips correctly, verify `mark_coaching_consumed` only marks unconsumed rows. Update `ARCH_state_manager.md` Public API section with the 5 new method signatures. Run full regression.

- [ ] 12.3 — **Remove SQLite fallbacks from Orchestrator; type InboundEvent.** In `src/orchestrator.py`:
  - Replace `_store_coaching` body: remove the `getattr` check and raw `sqlite3` fallback; call `await self.state_manager.store_coaching(coaching_id, event.coaching_type, event.content, False)` directly.
  - Replace `_store_intelligence` body: remove the `getattr` check and raw `sqlite3` fallback; call `await self.state_manager.store_intelligence(round_number, provider, payload)` directly.
  - Replace `_set_game_state` body: remove the `getattr` check and raw `sqlite3` fallback; call `await self.state_manager.set_game_state(key, value)` directly.
  - Replace `_store_adversarial_read` body: remove the `getattr` check and raw `sqlite3` fallback; call `await self.state_manager.store_adversarial_read(round_number, payload)` directly. Keep the `if adversarial_result is None: return` guard.
  - Replace `_mark_coaching_consumed` body: remove the `getattr` check and raw `sqlite3` fallback; call `await self.state_manager.mark_coaching_consumed()` directly.
  - Remove `import sqlite3` if `_initialize_sqlite` is the only remaining usage — check first. If `_initialize_sqlite` still needs it, keep the import but add a comment noting it's only for pre-flight DB init.
  - Type `process_event(self, event: Any)` → `process_event(self, event: InboundEvent)`. Add `InboundEvent` to the imports from `modules.types`.
  - Type `run_response_pipeline(self, trigger_event: Any | None = None)` → `run_response_pipeline(self, trigger_event: InboundEvent | None = None)`.
  - Update Orchestrator test fakes in `tests/test_orchestrator.py`: the fake state manager must implement `store_coaching`, `store_intelligence`, `set_game_state`, `store_adversarial_read`, and `mark_coaching_consumed` (simple in-memory implementations that store to lists/dicts). Verify existing Orchestrator tests still pass — the fake methods replace the `sqlite3` fallback paths that tests previously exercised.
  - Run full regression.

- [ ] 12.4 — **Documentation cleanup and regression verification.** Update `ARCHITECTURE.md` coupling notes: remove the "via adapter" note from the existing adapter bullet (already in `src/adapters.py` now) and update the State Manager coupling note to reflect the expanded API. Verify full test suite passes. Update DEVPLAN Phase 12 summary. Append DEVLOG entry. Transition to `state: review`.

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

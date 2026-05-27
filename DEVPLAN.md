---
phase: 16
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

- **Phase** — Phase 16 implementation complete: Deployment Readiness.
- **Focus** — Ready for phase review.
- **Blocked/Broken** — none.

## Phase 16: Deployment Readiness

Regime: Build. Scope: Fix the regression tests broken by smoke test changes, set up two-channel Telegram configuration, add systemd service for long-running operation, and verify full test suite on Pi. No game-specific tuning — this phase makes the system deployable; game rules and faction prompt are configured at deploy time.

**Prerequisites resolved during Phase 15:**
- Toolkit installed in venv on Pi
- `.env.template` and `pipeline_smoke.yaml` exist
- Bot connects to Telegram and responds to commands
- LLM API calls work through ToolkitLLMAdapter

Steps:

- [x] 16.1 — **Fix transport and review gate test coverage.** The smoke test applied three code changes that existing unit tests don't cover:
  - Transport `listen()` now runs `start_polling()` as a background task and continues on `None` updates — update `tests/test_transport.py` fakes and add a test for the background polling behavior.
  - Transport and Review Gate content lookup now includes `message_text` — update test fakes to use `message_text` attribute and verify it's found.
  - Orchestrator `/commands` handler and `/block` acknowledgement — add tests in `tests/test_orchestrator.py`.
  Run full regression on Pi. Target: all 187+ tests pass.

- [x] 16.2 — **Two-channel Telegram setup guide.** Create a deployment section in `diplomat-testing-doc.md` §5b (or a new `DEPLOYMENT.md`) documenting:
  - Create a Telegram group for game messages → use its chat ID as `DIPLOMAT_PUBLIC_CHANNEL_ID`
  - Keep the private bot chat for coaching → use its chat ID as `DIPLOMAT_COACHING_CHANNEL_ID`
  - Add the bot to the game group
  - Map other players' Telegram user IDs to faction names in `pipeline.yaml` `transport.faction_map`
  - Verify game messages route as non-operator (triggering extraction) and coaching messages route as operator

- [x] 16.3 — **Systemd service file.** Create `config/diplomat.service` (a systemd unit file) for running the bot as a background service on the Pi:
  - `ExecStart` pointing to the venv Python + `src/main.py` with `PYTHONPATH=src`
  - `WorkingDirectory` set to project root
  - `EnvironmentFile` pointing to `.env`
  - `Restart=on-failure` with reasonable delay
  - Document install/start/stop/logs commands in `DEPLOYMENT.md` or the testing doc

- [x] 16.4 — **Remove debug prints from transport.** Remove the `[DEBUG transport]` print statements added during smoke test. They were useful for debugging but shouldn't run in production.

- [x] 16.5 — **Documentation and regression.** Run full regression on Pi. Update DEVPLAN Phase 16 summary. Append DEVLOG entry. Transition to `state: review`.

Summary: Restored regression coverage for live-smoke fixes, including background Telegram polling, `message_text` update parsing, `/commands`, and `/block` acknowledgement. Documented two-channel Telegram deployment in `diplomat-testing-doc.md` §5b, added `config/diplomat.service` for Raspberry Pi systemd operation, removed temporary `[DEBUG transport]` prints, and verified the full regression suite: 193 passed. Phase 16 is ready for review.

## Phase 15: Live Smoke Test — Environment Setup

Complete. Created `.env.template` and `config/pipeline_smoke.yaml`. Validated startup on Pi with real toolkit imports. Manual smoke test confirmed: Telegram transport receives messages, operator commands (`/status`, `/state`, `/ledger`, `/commands`) respond correctly, `/preview` triggers LLM generation, review gate (`/approve`, `/block`) works. Five integration fixes applied during smoke test:
1. Transport: added `message_text` to content field lookup (TelegramUpdate compatibility)
2. Transport: changed `start_polling()` from blocking await to background task with race condition fix
3. Review Gate: added `message_text` to content field lookup
4. Orchestrator: added `/commands` handler listing all commands and coaching tags
5. Orchestrator: added `/block` acknowledgement message

All fixes committed. See `DEVLOG.md`.

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

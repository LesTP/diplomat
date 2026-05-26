---
phase: 11
blocked: false
state: execute
steps_remaining: 8
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

## Current Status

- **Phase** — Phase 11: Orchestrator (planning complete, executing).
- **Focus** — Step 11.2: Event loop, operator routing, and command dispatch.
- **Blocked/Broken** — none.

## Phase 11: Orchestrator

Regime: Build. Scope: `pipeline.yaml` wiring config, `registry.py` module lookup, `Orchestrator` class with full event loop, round management, response pipeline, operator command dispatch, and cost governance. Entry point `main.py`. No direct provider SDK imports; all LLM calls behind toolkit-injected fakes in tests.

Steps:
- [x] 11.1 — Config, registry, and Orchestrator init. Create `config/pipeline.yaml` with transport config (type, channel IDs, operator IDs), LLM provider entries (id, model, env var names), module selections, cost section (per_round_budget_usd, session_budget_usd), round_detection (mode: signal|time, pattern or interval_seconds), and feature flags (adversarial.enabled, review_gate.enabled). Implement `src/registry.py` mapping class name strings to importable implementations. Implement `Orchestrator.__init__()`: load+validate pipeline.yaml, build module instances from registry using injected factories (or direct imports for tests), initialize SQLite (WAL), load prompt files (fail fast on missing). Write `tests/test_orchestrator.py` covering: successful instantiation with fakes, bad config path, missing required key, and registry lookup for each module type. Run focused tests.
- [ ] 11.2 — Event loop, operator routing, and command dispatch. Implement `start()` async event loop (listen → dispatch) and `shutdown()` (cancel tasks, close transport). On InboundEvent from source==operator: parse with TaggedCoachingParser; if Command dispatch to command handler; if CoachingEvent route==state_updater run extraction+apply_patch; else store coaching entry as unconsumed. On game message: enqueue for debounced extraction (per-message cooldown via asyncio task cancel+reschedule). Implement all command handlers (/status, /state, /ledger, /intel, /divergences, /edits) — each formats a reply and calls Transport.send() on coaching channel. Tests: operator routing (command, INTEL, coaching), game message routing, debounce task cancel/reschedule, each command handler reply format. Run focused + regression.
- [ ] 11.3 — Round management and response pipeline. Implement round boundary detection: signal mode (scan event content for round_detection.pattern regex and advance round counter + trigger analysis); time mode (asyncio task sleeping interval_seconds). On round boundary: run primary+secondary LLMAnalyst concurrently (asyncio.gather), call divergence.compare(), store intelligence record in state_manager intelligence table, increment round counter (game_state key). Implement response trigger: direct address (faction_id mention in public message), /preview command, scheduled time. Implement full response pipeline with per-step failure handling per ARCH table: get_base_prompt+build_round_context → assemble → generate [retry once] → adversarial read [log+empty on failure] → review_gate.submit → transport.send [3 retries]. Tests: happy-path pipeline with fakes, generation failure+retry, adversarial failure (empty result passed), review gate block (no send), round boundary signal detection, round boundary time mode, primary analyst failure (alert, skip round analysis), secondary analyst failure (proceed with primary only). Run focused + regression.
- [ ] 11.4 — Cost governance, main.py, full regression, and docs. Inject CostAccountant fake into tests; in production Orchestrator create CostBudget per round and check available_budget() before each LLM call — if zero/negative log and alert operator and return early (skip the LLM call). Implement `src/main.py`: load .env (python-dotenv), load pipeline.yaml path from env or default, instantiate Orchestrator, run `asyncio.run(orch.start())` with SIGTERM/SIGINT shutdown hook. Run full regression suite targeting 140+ tests passing. Update DEVPLAN Phase 11 summary, append DEVLOG entry, update ARCHITECTURE.md implementation sequence row 12 → Complete. Transition DEVPLAN to `state: review`.

## Phase 10: Adversarial

Complete. Implemented `AdversarialResult`, `LLMAdversarialReader`, local adversarial JSON/schema validation, prompt/schema artifacts, and 9 focused tests with 121 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG.md`.

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

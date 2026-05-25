---
phase: 6
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
  - Transport tests use dependency-injected toolkit-compatible fakes because `toolkit` may be absent in the local development environment

## Current Status

- **Phase** — Phase 6: Analyst + Divergence, in progress.
- **Focus** — Phase 6 implementation is complete; documentation cleanup and regression verification remain.
- **Blocked/Broken** — None.

## Phase 6: Analyst + Divergence

Regime: Build. Scope: `AnalysisResult` + `Divergence` types, `LLMAnalyst.analyze()`, `compare()` pure function, `config/prompts/analyst.txt`, `config/schemas/intelligence.json`, full test coverage.

Steps:
- [x] 6.1 — Add `AnalysisResult` and `Divergence` dataclasses to `src/modules/types.py`. Implement `LLMAnalyst` in `src/modules/analyst/__init__.py` (constructor: `llm_client`, `llm_config`, `tier`, `prompt_path`, `schema_path`, `provider_id`; `analyze(state: dict) -> AnalysisResult` — calls toolkit/llm_client.complete, parses JSON, validates against intelligence schema, returns AnalysisResult; failures → success=False). Implement `compare(a, b) -> list[Divergence]` in `src/modules/analyst/divergence.py` (pure function; returns empty if either result failed; checks threat_level_steps, missing_leverage_item, coalition_stability_mismatch against configurable thresholds). Create `config/prompts/analyst.txt` (strategic intelligence analysis prompt). Create `config/schemas/intelligence.json` (schema with threat_level, key_leverage_points, coalition_stability fields). Write `tests/test_analyst.py` covering: successful analysis with valid JSON, LLM returns invalid JSON → success=False, LLM exception → success=False, schema validation failure → success=False, provider_id propagated; compare() both failed → empty, one failed → empty, both identical → empty, threat_level_steps divergence detected, threat_level_steps within threshold → no divergence, missing_leverage_item divergence, coalition_stability_mismatch divergence. Run full suite (68 + new tests pass).
- [ ] 6.2 — Update DEVPLAN Current Status → Phase 6 complete, append DEVLOG entry, update ARCHITECTURE.md Implementation Sequence status to Phase 6 complete. Run full regression.

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

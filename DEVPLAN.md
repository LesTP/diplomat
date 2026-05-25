---
phase: 2
blocked: false
state: execute
steps_remaining: 0
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before Transport implementation
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop
  - toolkit/llm_client returns plain text — Extraction module needs to handle JSON schema enforcement locally

## Current Status

- **Phase** — Phase 2 (Extraction)
- **Focus** — Phase planned; next action is Step 2.1
- **Blocked/Broken** — None

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

**Regime:** Build

**Scope:** Implement the Extraction module that converts raw game messages and operator INTEL corrections into `StatePatch` objects validated against `config/schemas/state_patch.json`. The module stays stateless; Orchestrator-owned batching/debounce behavior remains out of scope for this phase.

**Outcomes:**
- Public `ExtractionResult`, `OpenAIStructuredExtractor`, and `RuleBasedExtractor` exports from `src/modules/extraction`.
- LLM extractor calls toolkit-compatible `complete()` through dependency injection, builds prompts from `config/prompts/state_updater.txt`, includes schema/current-state context, parses plain-text JSON responses, and validates against the state patch schema.
- Operator `intel_correction` inputs are explicitly marked as high-confidence in the LLM prompt.
- Rule-based fallback returns deterministic valid patches for simple diplomacy facts and an empty valid patch when no pattern matches.
- Focused pytest coverage verifies success, invalid JSON, schema validation failure, trigger handling, and fallback behavior without real provider calls.

**Steps:**
- [ ] 2.1 — Add extraction API/types, prompt/schema loading, response JSON parsing, schema validation helpers, and tests for parser/validator failure modes.
- [ ] 2.2 — Implement `RuleBasedExtractor` with deterministic promise/coalition/inconsistency extraction for simple phrases plus empty-patch fallback, with tests.
- [ ] 2.3 — Implement `OpenAIStructuredExtractor` using a fake toolkit LLM dependency in tests; verify prompt content, COMMODITY tier usage, successful patch parsing, invalid JSON, invalid schema, and LLM exception handling.
- [ ] 2.4 — Add `config/prompts/state_updater.txt`, finalize exports, run the module and storage regression tests, and update docs/logs for phase readiness.

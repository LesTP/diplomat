---
phase: 3
blocked: true
state: close
steps_remaining: 0
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before Transport implementation
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop

## Current Status

- **Phase** — Phase 3 complete.
- **Focus** — Phase 4 Transport planning after `/close`.
- **Blocked/Broken** — None.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Complete. Implemented `config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, config validation, tagged/free coaching parsing, slash command parsing, and 11-test coverage with 38 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

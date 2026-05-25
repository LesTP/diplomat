---
phase: 3
blocked: false
state: execute
steps_remaining: 7
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before Transport implementation
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop

## Current Status

- **Phase** — Phase 3 in progress — Coaching.
- **Focus** — Implement config-driven tagged coaching parser and command parsing.
- **Blocked/Broken** — None.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Status: In progress.

Work regime: Build. Coaching is a pure parser with config-loaded routing, so each step should be small, testable, and avoid Orchestrator storage or dispatch behavior.

Scope:
- Add public Coaching dataclasses and `TaggedCoachingParser`.
- Load tag routes and allowed commands from `config/coaching_routes.yaml`.
- Parse tagged coaching input case-insensitively while returning canonical coaching types and configured routes.
- Parse slash commands, including `/edit: ...` and `/edit ...` text arguments.
- Treat unrecognized text, empty input, and malformed tags as free coaching rather than errors.

Out of scope:
- Persisting coaching queue entries.
- Dispatching commands.
- Forwarding INTEL to Extraction.
- Orchestrator integration.

Steps:
- [ ] 3.1 Add `config/coaching_routes.yaml` with the Phase 3 tag and command contract.
- [ ] 3.2 Implement `CoachingEvent`, `Command`, route loading, and parser initialization errors.
- [ ] 3.3 Implement tagged/free coaching parsing with canonical route output.
- [ ] 3.4 Implement slash command parsing, including edit text arguments.
- [ ] 3.5 Add focused unit tests for routing, command parsing, defaults, and malformed input.
- [ ] 3.6 Run the Coaching test set plus existing regression tests and clean up exports/docs.

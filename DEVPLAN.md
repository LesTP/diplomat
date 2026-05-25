---
phase: 4
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

- **Phase** — Phase 4 in progress.
- **Focus** — Transport module implementation.
- **Blocked/Broken** — None.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Complete. Implemented `config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, config validation, tagged/free coaching parsing, slash command parsing, and 11-test coverage with 38 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 4: Transport

Work regime: Build.

Scope: Implement the platform-agnostic Transport contract, a local CLI transport for deterministic testing, and the MVP Telegram bot transport via `toolkit/telegram_client`. Telethon user-account transport remains deferred unless the game moderator confirms bot-to-bot messaging is unavailable.

Outcomes:
- Shared `OutboundMessage`, transport-facing inbound normalization, `TransportError`, and `Transport` protocol are available from `src/modules/transport`.
- `CLITransport` can send to an async writer and yield inbound events from an async reader without network dependencies.
- `TelegramBotTransport` wraps the toolkit Telegram client, maps configured platform updates into `InboundEvent`, maps outbound channels/recipients to chat IDs, applies send jitter, and raises `TransportError` on persistent failures.
- Transport tests cover type validation, CLI send/listen behavior, Telegram send/listen mapping with fake clients, channel routing, retry/error handling, and regression tests for completed modules.

Steps:
- [ ] 4.1 Dependency probe and contract reconciliation: inspect the available `toolkit/telegram_client` surface, reconcile `ARCH_transport.md` with existing `src/modules/types.py`, and add focused tests for the public Transport types/protocol.
- [ ] 4.2 Implement shared Transport exports: add `OutboundMessage`, `TransportError`, `Transport` protocol/base typing, channel validation helpers, and event normalization without changing storage semantics.
- [ ] 4.3 Implement `CLITransport`: async reader/writer implementation with deterministic tests for inbound parsing, outbound formatting, EOF behavior, and error propagation.
- [ ] 4.4 Implement `TelegramBotTransport` send path: dependency-injected toolkit client, channel/recipient routing, configurable jitter, retry handling, and fake-client tests.
- [ ] 4.5 Implement `TelegramBotTransport` listen path: polling/update normalization into `InboundEvent`, faction/operator/system source mapping, metadata preservation, and fake-client tests.
- [ ] 4.6 Phase verification: run full regression tests, tighten docs/contracts if needed, and prepare for review.

# Diplomat — Development Log

<!-- Chronological record of what happened during development.
     Each step gets a structured entry. This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

## Module 1: Event Store + State Manager

### 2026-05-25 — Phase 1 Complete

**Action:** Phase Complete for Event Store + State Manager
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and focused tests for both modules. Detailed Phase 1 development entries were archived to `DEVLOG_archive.md`.

Verification:
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py` — 9 passed

No new gotchas were promoted. No contract changes require propagation beyond the Phase 1 storage interfaces already captured in the ARCH files.

## Module 2: Extraction

Phase 2 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 2 Complete

**Action:** Phase Review and Phase Complete for Extraction
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, extraction validators, rule-based fallback, fake-provider test coverage, and system prompt. Phase Review applied one should-fix: `load_schema` now inlines JSON loading with schema-specific error messages rather than routing through `parse_json_object` (which emitted misleading "LLM response" error text for schema file failures).

All 27 tests pass. Structured output enforcement resolved: local prompt + parse + jsonschema validate is sufficient — no toolkit extension needed.

Verification:
- `python3 -m pytest tests/test_extraction.py tests/test_event_store.py tests/test_state_manager.py` — 27 passed

## Module 3: Coaching

Phase 3 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 3 Complete

**Action:** Phase Complete for Coaching
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed `config/coaching_routes.yaml`, frozen Coaching result dataclasses, `TaggedCoachingParser`, route config validation, case-insensitive tagged coaching parsing, default free coaching fallback, allowlisted slash command parsing, and edit command argument parsing. Phase Review found no must-fix or should-fix items.

All 38 tests pass. Coaching remains a pure parser with no persistence, dispatch, INTEL forwarding, or Orchestrator coupling.

Verification:
- `python3 -m pytest tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 38 passed

No new gotchas were promoted. No contract changes require propagation beyond the Phase 3 Coaching API and route config already captured in `ARCH_coaching.md`.

## Module 4: Transport

### 2026-05-25 — Phase 4 Planned

**Action:** Phase Plan for Transport
**Outcome:** Planned — DEVPLAN moved to execute state

Defined Phase 4 as a Build phase with six testable steps covering toolkit dependency probing, shared Transport API exports, CLI transport, Telegram bot send path, Telegram bot listen path, and phase verification. Telethon user-account support remains deferred pending moderator confirmation that bot-to-bot messaging is unavailable.

No code was changed during planning.

### Step 4.1: Dependency probe and contract reconciliation

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Confirmed `toolkit` is not importable in this development environment, so Transport implementation will rely on dependency injection and fake-client tests until runtime wiring supplies the toolkit client. Reconciled `ARCH_transport.md` to the existing shared `modules.types.InboundEvent` shape used by Event Store instead of introducing a parallel Transport-only inbound event. Added the public Transport API surface: `OutboundMessage`, `TransportError`, and runtime-checkable `Transport` protocol, re-exporting the shared `InboundEvent` from `modules.transport`.

Added `tests/test_transport.py` covering public exports, outbound defaults, protocol conformance, and shared inbound event reuse.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 42 passed

### Step 4.2: Shared Transport exports

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Completed the shared Transport API surface with canonical channel validation, outbound recipient rules, and `normalize_inbound_event()` for adapter code to create the existing shared `InboundEvent` type without altering Event Store semantics. Public exports now include `VALID_CHANNELS`, `validate_channel`, and `normalize_inbound_event` alongside `OutboundMessage`, `TransportError`, `Transport`, and `InboundEvent`.

Expanded `tests/test_transport.py` for channel validation, private-message recipient requirements, public/coaching recipient rejection, and inbound normalization.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 45 passed

### Step 4.3: CLITransport

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `CLITransport` as an async JSON-lines adapter with injectable reader, writer, and clock. Outbound messages are serialized as one JSON object per line. Inbound lines are parsed as JSON objects, validated through the shared channel and event-normalization helpers, and yielded as shared `InboundEvent` instances. Writer, reader, malformed JSON, invalid payload shape, and invalid field values are wrapped in `TransportError`.

Expanded `tests/test_transport.py` with deterministic CLI send/listen coverage, timestamp fallback via injected clock, EOF behavior, writer/reader error propagation, and malformed inbound rejection.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 51 passed

### Step 4.4: TelegramBotTransport send path

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `TelegramBotTransport` send behavior with dependency-injected toolkit-compatible client, public/coaching chat routing, private recipient chat routing, configurable jitter, and bounded retry handling. The class does not import toolkit directly, matching the dependency probe result and keeping tests credential-free. Unconfigured private recipients and persistent send failures raise `TransportError`; invalid send configuration raises `ValueError`.

Expanded fake-client tests for public/private/coaching routing, jitter calls, retry success, persistent failure wrapping, missing private-recipient routes, and constructor validation.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 56 passed

### Step 4.5: TelegramBotTransport listen path

**Mode:** Build
**Outcome:** Complete
**Contract changes:** `ARCH_transport.md`, `src/modules/transport/__init__.py`

Implemented `TelegramBotTransport.listen()` using dependency-injected `start_polling()` and `get_next_update()` client methods. The listener accepts dict-like and object-like updates, maps chat IDs to public/private/coaching channels, maps configured user IDs to factions or operator, falls back private-chat senders to their configured faction, falls back coaching senders to operator, and falls back unmatched public senders to system. Timestamps support ISO strings, `datetime`, epoch seconds, or injected-clock fallback. Telegram message IDs are preserved in the shared `telegram_msg_id` field.

Expanded fake-client tests for public/private/coaching inbound normalization, polling startup, fallback source and timestamp behavior, malformed update wrapping, unknown chat rejection, and polling failure wrapping.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed

### Step 4.6: Phase verification

**Mode:** Build
**Outcome:** Complete — DEVPLAN moved to review state
**Contract changes:** `ARCH_transport.md`

Ran the full current regression suite and Python bytecode compilation. Tightened `ARCH_transport.md` so the usage example matches the implemented dependency-injected `TelegramBotTransport` constructor and toolkit client boundary.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

### 2026-05-25 — Phase 4 Review

**Action:** Phase Review for Transport
**Outcome:** Complete — DEVPLAN moved to close state

Reviewed Transport implementation against `ARCH_transport.md` and the phase plan. No must-fix or should-fix issues were found. The implementation preserves existing Event Store `InboundEvent` semantics, keeps toolkit access dependency-injected, avoids direct Telegram SDK imports, and has focused fake-client coverage for CLI and Telegram paths.

Verification carried forward from Step 4.6:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

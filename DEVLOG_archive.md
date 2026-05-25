# Diplomat — Development Log Archive

## Archived 2026-05-25 — Module 4 Phase 4: Transport

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

---

## Archived 2026-05-25 — Module 3 Phase 3: Coaching

### 2026-05-25 — Phase 3 Plan

**Action:** Phase Plan for Coaching
**Outcome:** Planned — state set to execute

Defined Phase 3 as a Build phase for a stateless, config-driven coaching parser. The plan keeps persistence, command dispatch, INTEL forwarding, and Orchestrator integration out of scope for this module.

Planned steps:
- 3.1 Add `config/coaching_routes.yaml`.
- 3.2 Implement public types, route loading, and initialization errors.
- 3.3 Implement tagged/free coaching parsing.
- 3.4 Implement slash command parsing.
- 3.5 Add focused parser tests.
- 3.6 Run Coaching and regression tests, then clean up exports/docs.

### Step 3.1: Add coaching routes config

**Mode:** Build
**Outcome:** Complete
**Contract changes:** Added `config/coaching_routes.yaml` implementing the Phase 3 route contract from `ARCH_coaching.md`.

Added the coaching tag routes and command allowlist used by `TaggedCoachingParser`. The file keeps routing data out of code: `INTEL` routes to `state_updater`, all other defined coaching tags and default free coaching route to `coaching_queue`, and the MVP slash commands are listed explicitly.

Verification:
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.2: Add coaching public types and route loader

**Mode:** Build
**Outcome:** Complete
**Contract changes:** Implemented the public Coaching API types from `ARCH_coaching.md`.

Added frozen `CoachingEvent` and `Command` dataclasses, a `TaggedCoachingParser` shell, route-rule normalization, YAML config loading, command allowlist normalization, and startup validation for missing or malformed routing config. The parser still returns default free coaching until tag and command parsing are implemented in the next steps.

Verification:
- `python3 - <<'PY' ... TaggedCoachingParser('config/coaching_routes.yaml') ... PY` — loaded expected tags, commands, and default route
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.3: Implement tagged and free coaching parsing

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Implemented case-insensitive tag parsing for configured coaching tags and canonical route output from the YAML route table. Unknown tags, malformed tag-like text, untagged input, and empty input fall back to default `FREE` coaching with the configured default route.

Verification:
- `python3 - <<'PY' ... parser.parse(...) assertions ... PY` — tagged, INTEL, unknown tag, and empty input cases passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.4: Implement slash command parsing

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Implemented config-allowlisted slash command parsing before coaching tag parsing. Command names are returned without the leading slash and are matched case-insensitively. `/edit: ...` and `/edit ...` populate `args["text"]`; other commands return empty args. Unknown slash commands fall back to `FREE` coaching.

Verification:
- `python3 - <<'PY' ... parser.parse(...) command assertions ... PY` — preview, status, edit, unknown slash, and tagged fallback cases passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 27 passed

### Step 3.5: Add focused coaching parser tests

**Mode:** Build
**Outcome:** Complete
**Contract changes:** None.

Added `tests/test_coaching.py` covering public exports, route config loading, configured tag routes, INTEL routing, free-coaching defaults, malformed and unknown input fallback, command parsing, edit command arguments, unknown slash fallback, and config validation errors.

Verification:
- `python3 -m pytest tests/test_coaching.py` — 11 passed
- `python3 -m pytest tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py tests/test_coaching.py` — 38 passed

### Step 3.6: Run full tests and clean up

**Mode:** Build
**Outcome:** Complete — state set to review
**Contract changes:** None.

Ran the full test suite and performed a small cleanup in command parsing: the command regex is wrapped for readability and configured command strings are normalized after trimming. Phase 3 implementation is complete and ready for review.

Verification:
- `python3 -m pytest` — 38 passed
- `python3 -m pytest tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 38 passed

### 2026-05-25 — Phase 3 Review

**Action:** Phase Review — Coaching
**Outcome:** Passed — no must-fix or should-fix items found. State set to close.

Reviewed `src/modules/coaching/__init__.py` and `tests/test_coaching.py` against `ARCH_coaching.md`.

Contract compliance:
- `parse(str) -> CoachingEvent | Command` signature matches exactly.
- No exceptions raised for unrecognized input — returns FREE CoachingEvent.
- `CoachingEvent` and `Command` frozen dataclasses match ARCH types.
- All routing loaded from `config/coaching_routes.yaml`, no hardcoded routing logic.
- YAML structure matches ARCH exactly: 5 tags + default + 10 commands.
- INTEL -> state_updater, all others -> coaching_queue, unknown tag -> FREE.
- `/edit:` and `/edit ` argument variants both handled.
- Pure parsing function — no state, persistence, dispatch, or Orchestrator coupling.
- `__all__` exports `TaggedCoachingParser`, `CoachingEvent`, `Command`, `RouteRule`, `load_routes_config`.
- Phase scope respected — no coaching queue, no INTEL forwarding, no Orchestrator integration.

All 38 tests pass (11 coaching + 27 regression).

---

## Archived 2026-05-25 — Module 1 Phase 1: Event Store + State Manager

### Phase 1: Core Storage

### 2026-05-25 — Phase Plan (1.0)

**Action:** Phase Plan for Phase 1 (Event Store + State Manager)
**Outcome:** Step breakdown written to DEVPLAN.md. 6 steps defined.

Steps planned:
- 1.1 — Shared types module (`src/modules/types.py`): InboundEvent, StoredEvent, EventFilter, StatePatch, PatchSource
- 1.2 — SQLiteEventStore implementation with append/query, WAL mode
- 1.3 — Event Store tests
- 1.4 — State patch JSON schema (`config/schemas/state_patch.json`)
- 1.5 — SQLiteStateManager implementation with all domain tables, schema validation, audit log
- 1.6 — State Manager tests

Key design decisions confirmed from ARCH files: single SQLite file with WAL mode, shared types module to avoid circular imports, apply_patch validates then audits then applies.

**State transition:** plan → execute

### Step 1.1: Shared types module

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/types.py`

Added shared dataclasses for inbound and stored events, event filtering, state
patches, and patch audit sources. These types keep Event Store and State
Manager contracts independent of each other while giving later Transport and
Extraction work a common import surface.

### Step 1.2: SQLiteEventStore implementation

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/event_store/__init__.py`

Implemented the append-only SQLite event store with WAL enabled on every
connection, table/index initialization, UUID event IDs, and parameterized query
filters for round, sender/source, channel, timestamp, and limit.

### Step 1.3: Event Store tests

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** None

Added async pytest coverage for Event Store append/query behavior, including
WAL mode, round/source/channel/since filters, timestamp ordering, limit
handling, and empty result cases.

### Step 1.4: State patch JSON schema

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `config/schemas/state_patch.json`

Added the JSON schema used by State Manager to validate extraction patches for
faction state, promises, coalitions, and inconsistencies before any domain
tables are updated.

### Step 1.5: SQLiteStateManager implementation

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** `src/modules/state_manager/__init__.py`

Implemented the State Manager API with WAL-backed SQLite table ownership,
schema validation at patch application time, audit logging before domain writes,
parameterized get/query operations, and full-state snapshots for Analyst input.

### Step 1.6: State Manager tests

**Mode:** Execute
**Outcome:** Complete
**Contract changes:** None

Added pytest coverage for State Manager initialization, WAL mode, patch
validation, audit logging, domain table upserts, public get/query behavior,
unknown entity errors, and full-state filtering for pending/unspent records.

### 2026-05-25 — Phase 1 Review

**Action:** Architecture contract review for Event Store and State Manager
**Outcome:** Clean — all 9 tests pass, no must-fix or should-fix items

Review checklist:
- Event Store API signatures match ARCH exactly (append, query)
- messages table schema and indices match ARCH
- WAL mode enabled on every connection
- All queries parameterised; no SQL injection surface
- State Manager API signatures match ARCH (get, query, apply_patch, get_full_state)
- All 10 domain tables created at init
- apply_patch validates first, writes audit log, then applies domain changes — in one transaction
- get_full_state returns pending promises and unspent inconsistencies only
- Unknown entity_type and column raise ValueError
- Schema (state_patch.json) enforces required fields, non-empty strings, score range [0,1], promise status enum

No contract drift from ARCH files. No gotchas to promote.

**State transition:** review → close

---

## Archived 2026-05-25 — Module 2 Phase 2: Extraction

### 2026-05-25 — Phase Plan (2.0)

**Action:** Phase Plan for Extraction
**Outcome:** Step breakdown written to DEVPLAN.md. 4 steps defined.

Defined a Build-regime plan for the Extraction module. Scope covers the public extraction API, local JSON/schema enforcement for plain-text LLM responses, deterministic rule-based fallback behavior, prompt configuration, and focused fake-provider tests.

Scope decision: Extraction remains stateless; batching/debounce behavior stays with Orchestrator.

**State transition:** plan → execute

### Step 2.1: Extraction API and Patch Validation Helpers

**Mode:** Build
**Outcome:** Complete — extraction result type, prompt/schema loading, JSON parsing, and state patch validation helpers added with focused tests.
**Contract changes:** None

Added the public `ExtractionResult` type and reusable helper functions for loading prompts, loading JSON schemas, parsing plain-text LLM responses as JSON objects, and validating decoded patch data against the state patch schema before wrapping it in `StatePatch`.

### Step 2.2: Rule-Based Extraction Fallback

**Mode:** Build
**Outcome:** Complete — deterministic fallback extraction added for simple promises, coalitions, inconsistencies, and no-match empty patches.
**Contract changes:** `config/schemas/state_patch.json` now permits an empty root object so fallback extraction can return a valid no-op patch.

Implemented `RuleBasedExtractor` as a stateless async fallback with deterministic IDs and schema validation for every returned patch. The root schema now accepts `{}` while preserving validation for entity objects when they are present.

### Step 2.3: OpenAI Structured Extractor

**Mode:** Build
**Outcome:** Complete — LLM-backed extractor added with injected toolkit-compatible client, prompt assembly, COMMODITY tier usage, JSON parsing, schema validation, and failure reporting.
**Contract changes:** None

Implemented `OpenAIStructuredExtractor` without direct provider SDK imports. The extractor builds system/user messages from the configured prompt, schema, current state, trigger type, and input text, marks `intel_correction` inputs as high-confidence operator intel, and returns failed `ExtractionResult` values for LLM exceptions, invalid JSON, invalid schema, and non-text responses.

### Step 2.4: Extraction Prompt and Phase Readiness

**Mode:** Build
**Outcome:** Complete — state updater prompt added, public exports verified, and phase regression tests passed.
**Contract changes:** None

Added `config/prompts/state_updater.txt` with JSON-only state patch guidance for the LLM extractor. Added tests that verify the configured prompt loads and the public module exports include both primary and fallback extractors. Phase 2 is ready for review.

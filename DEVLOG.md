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

Phase 4 development entries archived to `DEVLOG_archive.md` (2026-05-25).

### 2026-05-25 — Phase 4 Complete

**Action:** Phase Complete for Transport
**Outcome:** Complete — human audit gate set in DEVPLAN frontmatter

Completed shared `OutboundMessage`, `TransportError`, `Transport`, channel validation, inbound normalization helpers, `CLITransport`, and dependency-injected `TelegramBotTransport` send/listen behavior. Phase Review found no must-fix or should-fix items.

All 59 tests pass. Transport remains toolkit-bound at the adapter boundary without direct Telegram SDK imports; local tests use fake toolkit-compatible clients because `toolkit` may be absent in the development environment.

Verification:
- `python3 -m pytest tests/test_transport.py tests/test_coaching.py tests/test_event_store.py tests/test_state_manager.py tests/test_extraction.py` — 59 passed
- `python3 -m compileall -q src` — passed

Promoted gotchas:
- Bot vs. user account question remains a deployment decision; implement `TelethonUserTransport` only if the moderator confirms bot-to-bot messaging is unavailable.
- Transport tests use dependency-injected toolkit-compatible fakes when `toolkit` is not installed locally.

No contract changes require propagation beyond `ARCH_transport.md`, `ARCHITECTURE.md`, and the existing `PROJECT.md` risk wording updated during close.

## Module 5: Persona

### Step 5.1: FileBasedPersona implementation

**Mode:** Build
**Outcome:** Complete — implemented Persona public API and focused tests
**Contract changes:** None

Implemented frozen `CoachingContext` and `FileBasedPersona` in `src/modules/persona/__init__.py`. `get_base_prompt` now reads `config/faction_prompt.txt`-style files, strips the `## CURRENT ROUND CONTEXT` section, raises `FileNotFoundError` naturally when the prompt is absent, and caches by `st_mtime_ns` for hot-reload behavior. `build_round_context` formats round metadata and all coaching context buckets with explicit empty-state bullets.

Added `tests/test_persona.py` covering public exports, missing file handling, fresh read, mtime reload, unchanged-mtime cache reuse, marker stripping, complete context formatting, empty fields, and unknown rounds remaining.

Verification:
- `.venv/bin/python -m pytest` — 68 passed

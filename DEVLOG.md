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

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

### 2026-05-25 — Phase 2 Plan

**Action:** Phase Plan for Extraction
**Outcome:** Planned — DEVPLAN moved to `state: execute`

Defined a Build-regime plan for the Extraction module. Scope covers the public extraction API, local JSON/schema enforcement for plain-text LLM responses, deterministic rule-based fallback behavior, prompt configuration, and focused fake-provider tests.

Scope decision:
- Extraction remains stateless; batching/debounce behavior stays with Orchestrator.

### Step 2.1: Extraction API and Patch Validation Helpers

**Mode:** Build
**Outcome:** Complete — extraction result type, prompt/schema loading, JSON parsing, and state patch validation helpers added with focused tests.
**Contract changes:** None

Added the public `ExtractionResult` type and reusable helper functions for loading prompts, loading JSON schemas, parsing plain-text LLM responses as JSON objects, and validating decoded patch data against the state patch schema before wrapping it in `StatePatch`.

Verification:
- `python3 -m pytest tests/test_extraction.py` — 6 passed

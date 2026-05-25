# Diplomat — Development Log Archive

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

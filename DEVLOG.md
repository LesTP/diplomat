# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->


### Step 20.1: Phase 18 path test skeleton

Mode: Build
Outcome: Added `tests/integration/test_phase18_paths.py` with a reusable Phase 18 integration harness, reconciler-shaped fake LLM responses, reconciliation payload helpers, and transcript-burst injection helpers. Included a fixture smoke test so the scaffold is collected immediately.
Contract changes: None.

Verified with `.venv/bin/python -m pytest tests/integration/test_phase18_paths.py -q` and `.venv/bin/python -m pytest tests/ -q` (285 passed). System `python3` still lacks editable `toolkit`, matching the existing project gotcha; the workspace `.venv` path is the valid test runner here.

### Step 20.2: Burst extraction no-drop coverage

Mode: Build
Outcome: Added `test_burst_extraction_no_drops` to inject five public game events without waiting between sends, then assert all five events persist and all five message extractions create state-change rows. The Phase 18 harness now disables direct-address auto-response so the test isolates the debounce/extraction task set.
Contract changes: None.

Verified with `.venv/bin/python -m pytest tests/integration/test_phase18_paths.py -q` and `.venv/bin/python -m pytest tests/ -q` (286 passed).

### Step 20.3: Reconciler dedup and fulfillment coverage

Mode: Build
Outcome: Added `test_reconciler_dedup` and `test_reconciler_fulfillment`, driving the production round-boundary reconciliation hook with fake structured responses. The shared fake LLM now recognizes toolkit `structured_call(messages=...)` prompts, so reconciler responses exercise the same adapter path used in production.
Contract changes: None.

Verified with `.venv/bin/python -m pytest tests/integration/test_phase18_paths.py -q` and `.venv/bin/python -m pytest tests/ -q` (288 passed).

### Step 20.4: Reconciler inconsistency and missed-proposal coverage

Mode: Build
Outcome: Added `test_reconciler_inconsistency` and `test_reconciler_missed_proposal`, covering reconciliation-created inconsistency patches and reconciliation-created promise patches for proposals missed by per-message extraction. Replaced the burst test's fixed wait with polling on state-change count to avoid scheduler-sensitive debounce timing.
Contract changes: None.

Verified with `.venv/bin/python -m pytest tests/integration/test_phase18_paths.py -q` and `.venv/bin/python -m pytest tests/ -q` (290 passed).

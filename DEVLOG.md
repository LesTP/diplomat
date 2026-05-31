# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

<!-- Entries above archived from Phase 20, 2026-05-31 -->

### Phase 20 close — 2026-05-31

Phase: Build. 6 steps, ~$0.30 iteration cost.

Built: `tests/integration/test_phase18_paths.py` — 6 deterministic integration tests covering the Phase 18 production paths not previously tested: burst extraction without dropped events, reconciler duplicate merge, promise fulfillment, inconsistency detection, and missed-proposal insertion.

Tests: 290 passing (DoD: 288+). Each new test runs under 2s with fake LLM.

Docs updated: `ASSESSMENT.md` (Block A reconciliation path coverage → closed debt), `diplomat-testing-doc.md` (Layer 3 count updated to 23 tests / 290 total).

No new gotchas beyond what is already in DEVPLAN. Key technique: `wait_for_state_change_count` polling preferred over fixed `asyncio.sleep` for debounce-adjacent assertions.

Phase 21 is next.

### Phase 21 plan — 2026-05-31

Phase: Build. Scope is module-boundary cleanup across Orchestrator/self-play and LLM adapter attribution plumbing.

Planned steps: 9 executable steps plus loop-managed review/close. The Phase 21 checklist now uses state-machine checkboxes and frontmatter is set to `phase: 21`, `state: execute`.

No implementation changes in this planning action. Existing dirty worktree changes outside `DEVPLAN.md`, `DEVLOG.md`, and `DECISIONS.md` were left untouched.

### Step 21.1: Public round advancement

Mode: Build
Outcome: Added `Orchestrator.advance_to_round(round_number)` and updated `GameEnvironment.run_round()` to use it instead of assigning `current_round` and calling `_reset_round_budget()` directly.
Contract changes: Public Orchestrator API added; `ARCH_orchestrator.md` is queued for the Phase 21 doc-update step.

The new method validates positive integer round numbers, sets `current_round`, and resets the per-round budget through the existing budget lifecycle. Added focused tests for successful advancement and invalid round rejection.

Tests: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/integration/test_phase18_paths.py -q` (58 passed); `.venv/bin/python -m pytest -q` (292 passed).

Next step: 21.2 extracts `OrchestrationOptions` for `auto_response_enabled` and `total_rounds`.

### Step 21.2: Orchestration options

Mode: Build
Outcome: Added `OrchestrationOptions` and moved `auto_response_enabled` / `total_rounds` behind `orchestrator.options`. Updated production `main.py`, integration fixtures, and self-play construction to pass options explicitly.
Contract changes: Public Orchestrator construction shape changed; `ARCH_orchestrator.md` is queued for the Phase 21 doc-update step.

Production still reads `game.total_rounds` from `pipeline.yaml` through `OrchestrationOptions.from_config_path()`. Self-play constructs orchestrators with auto-response disabled and updates `options.total_rounds` before the seed message using `dataclasses.replace()`.

Tests: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/integration/test_phase18_paths.py tests/test_main.py -q` (63 passed); `.venv/bin/python -m pytest -q` (293 passed).

Next step: 21.3 resolves the `StubAnalyst` registry leak.

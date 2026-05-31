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

<!-- Entries above archived from Phase 21, 2026-05-31 -->

### Phase 21 close — 2026-05-31

Phase: Build. 9 steps.

Built: Module boundary cleanup across Orchestrator, self-play harness, and LLM adapter.
- `OrchestrationOptions` dataclass extracts `auto_response_enabled` and `total_rounds` off `Orchestrator.__init__`
- Public `Orchestrator.advance_to_round(n)` replaces direct attribute pokes from self-play
- `_TaggedLLMClient` deleted; `LoggingLLMClient` reads `attribution` kwarg; all `getattr(_inner)` peeks removed
- `attribution`/`purpose` kwargs threaded through `ToolkitLLMAdapter`, toolkit `complete_with_retry`, `CostAccountant`
- `DryRunLLMClient` classifies calls via `purpose` kwarg instead of regex on prompt body
- `build_reconciler` + `subsystem_llm_config` factories eliminate 4× duplicated provider-config dict
- `StubAnalyst` removed from production registry; injected via `module_overrides` only
- Four silent `except Exception: pass` blocks in reconciler replaced with contextual log messages

Tests: 296 passing (DoD: 288+).

Docs updated: `ARCH_orchestrator.md`, `ARCH_reconciliation.md`, `ARCHITECTURE.md` (coupling notes), `ASSESSMENT.md` (Block A: orchestration + LLM adapter cleanup → ✓), `diplomat-testing-doc.md` (StubAnalyst location).

No new gotchas. Phase 22 is next.

### Phase 22 plan — 2026-05-31

Phase: Build. Planned 8 executable steps for the Pipeline / Flow split.

Scope: Extract a `Pipeline` capability interface from Orchestrator internals, move production scheduling into `EventDrivenFlow`, move self-play round stepping into `RoundSteppedFlow`, preserve `Orchestrator` as a compatibility shim, add contract tests, and update the named architecture/testing docs.

Plan hygiene: Converted Phase 22 steps to state-machine checkboxes and kept phase review/close outside the executable checklist so `STOP_BEFORE_REVIEW=true` stops at the review gate.

### Step 22.1: Pipeline interface

Mode: Build
Outcome: Added `src/pipeline.py` with a `Pipeline` wrapper exposing lifecycle, event storage, extraction, operator dispatch, round advancement, reconciliation/analysis, response generation, and query methods that delegate to the existing Orchestrator surface.
Contract changes: New public `Pipeline` interface; tests added in `tests/test_pipeline.py`.

The implementation is deliberately thin for the first split step: it creates the stable call surface that later Flow classes can target while preserving current Orchestrator behavior. Added four focused contract tests and re-ran the existing Orchestrator suite.

Tests: `.venv/bin/python -m pytest tests/test_pipeline.py tests/test_orchestrator.py` — 58 passed.

### Step 22.2: EventDrivenFlow

Mode: Build
Outcome: Added `src/flows/event_driven.py` with `EventDrivenFlow`, `signal_round_detector()`, and `faction_address_detector()`. The flow owns transport listening, per-event extraction task scheduling, round-boundary checks, direct-address response triggers, and shutdown cleanup.
Contract changes: New public Flow class and detector helpers; `src/flows/__init__.py` exports `EventDrivenFlow`.

The flow mirrors the production event ordering: non-operator messages are stored, extraction is scheduled per event, round-boundary handling wins over direct-response triggering, and direct-address messages can still trigger a response. Added five focused flow tests.

Tests: `.venv/bin/python -m pytest tests/test_flows.py tests/test_pipeline.py tests/test_orchestrator.py` — 63 passed; final focused check `.venv/bin/python -m pytest tests/test_flows.py` — 5 passed.

### Step 22.3: Orchestrator compat shim

Mode: Build
Outcome: `Orchestrator(...)` now constructs the old composition core internally and returns `EventDrivenFlow(pipeline=Pipeline(core), transport=core.transport, ...)`. `EventDrivenFlow` delegates unknown attributes and assignments to the core so existing call sites such as `main._attach_reconciler()` and tests keep working.
Contract changes: `Orchestrator` public constructor now returns an `EventDrivenFlow` compatibility object; the internal implementation class is `_OrchestratorCore`.

Signal round detection, direct-address detection, message debounce, and time-based round intervals are wired from the existing config into the flow. The flow also prints the existing startup banner and owns shutdown cleanup.

Tests: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_pipeline.py tests/test_flows.py tests/test_main.py` — 67 passed; `.venv/bin/python -m pytest tests/integration` — 23 passed.

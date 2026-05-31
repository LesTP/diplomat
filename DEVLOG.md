# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

<!-- Entries above archived from Phase 21, 2026-05-31 -->

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

### Step 22.4: RoundSteppedFlow

Mode: Build
Outcome: Added `src/flows/round_stepped.py` and updated `GameEnvironment` to compose a `RoundSteppedFlow` from each agent's `Pipeline`. `GameEnvironment.run_round()` is now a thin delegation wrapper.
Contract changes: New public `RoundSteppedFlow` class exported from `flows`.

The self-play driver now uses `Pipeline.advance_to_round()` and `Pipeline.run_response()`, then calls `Pipeline.reconcile_and_analyze()` directly at round end. `[ROUND END]` is still recorded in the transcript log for continuity, but it is no longer injected back through every agent transport to trigger analysis.

Tests: `.venv/bin/python -m pytest tests/test_flows.py tests/test_self_play.py tests/integration` — 58 passed.

### Step 22.5: Pipeline and Flow contract tests

Mode: Build
Outcome: Expanded `tests/test_pipeline.py` and `tests/test_flows.py` with missing contract cases: `Pipeline.extract_from()` stores an event when no event id is provided, and `EventDrivenFlow` does not trigger a response when the address detector does not match.
Contract changes: None; this step verifies the public Pipeline/Flow contracts added in 22.1-22.4.

The full regression suite now exercises the new Pipeline/Flow split alongside the existing integration and self-play coverage.

Tests: `.venv/bin/python -m pytest` — 308 passed.

### Step 22.6: Pipeline/Flow verification

Mode: Build
Outcome: Verified the Pipeline/Flow split with the local coaching-scope smoke equivalent and a zero-cost self-play dry run.
Contract changes: None.

Production smoke: live Telegram/incus smoke was not run in this worker environment. Local coaching-scope coverage passed: toolkit/reconciler/main imports succeeded, and `.venv/bin/python -m pytest tests/test_main.py tests/test_transport.py tests/test_review_gate.py tests/test_coaching.py` passed 54 tests.

Self-play: ran `.venv/bin/python -m tests.self_play.run_simulation --dry-run --scenario tests/self_play/scenarios/water_rights.md --analysis-json tests/self_play/scenarios/water_rights_compiled/scenario_analysis.json --rounds 4 --output tests/self_play/results/phase22_verify_dryrun.json`, then verified with `.venv/bin/python -m tests.self_play.verify_dryrun --results tests/self_play/results/phase22_verify_dryrun.json --num-factions 3 --rounds 4`. Result: PASS — 12/12 expected transcript agent messages, generation rounds [1,2,3,4], penultimate marker in round 3, final marker in round 4, SCORE call present.

### Step 22.7: Flow architecture docs

Mode: Build
Outcome: Added `ARCH_flow.md` documenting the Pipeline contract, Flow responsibilities, EventDrivenFlow, RoundSteppedFlow, the Orchestrator compatibility shim, and a worked TurnBasedFlow example.
Contract changes: Architecture docs now treat Pipeline and Flow as first-class components.

Updated `ARCHITECTURE.md` Component Map with Pipeline and Flow rows and rewrote the Orchestrator row as a compatibility constructor over EventDrivenFlow.

---

## 2026-05-31 — Phase 22.8: Doc updates for Pipeline/Flow split

Step: 22.8
Mode: Build
Outcome: All doc updates for the Pipeline/Flow split complete. ASSESSMENT.md Block A Pipeline/Flow separation moved from active debt to closed debt (Phase 22). ARCH_orchestrator.md rewritten as a compat-shim pointer doc (canonical architecture now lives in ARCH_flow.md). diplomat-testing-doc.md Layer 3 section intro updated to reference EventDrivenFlow/Pipeline. CLAUDE.md and CODEX.md Tier 2 lookup table and Available Modules updated with Pipeline + Flow entries.

All 308 tests still passing.

## 2026-05-31 — Phase 22 review

Action: REVIEW
Mode: Build
Outcome: Reviewed the Pipeline / Flow split against `ARCH_flow.md`, `ARCH_orchestrator.md`, the `Pipeline`, `EventDrivenFlow`, `RoundSteppedFlow`, Orchestrator compat shim, self-play wrapper, and contract tests. No must-fix or should-fix defects found. The remaining duplicated scheduling helpers on `_OrchestratorCore` are migration scaffolding behind the compat shim and stay out of public Flow callers.

Tests: `.venv/bin/python3 -m pytest tests/test_pipeline.py tests/test_flows.py tests/test_orchestrator.py tests/test_self_play.py` — 95 passed. Full suite: `.venv/bin/python3 -m pytest` — 308 passed.

## 2026-05-31 — Phase 22 close

Action: CLOSE
Mode: Build
Outcome: Closed the Pipeline / Flow split. `Pipeline` is now the public per-agent capability surface; `EventDrivenFlow` owns production event scheduling; `RoundSteppedFlow` owns self-play round scheduling; `Orchestrator(...)` remains as a compatibility factory returning `EventDrivenFlow(Pipeline(core))`; `GameEnvironment` delegates round execution to `RoundSteppedFlow`.

Docs updated during close: `DEVPLAN.md` reduced Phase 22 to a completion summary and set Current Status to the human audit gate before Phase 23; `ARCHITECTURE.md` Implementation Sequence rows for Pipeline and Flow marked Phase 22 complete; `DECISIONS.md` closed D-26 and the stale D-25 status.

DEVLOG learning review: no new gotchas promoted. Contract changes were already propagated in 22.7 and 22.8 (`ARCH_flow.md`, `ARCH_orchestrator.md`, `ARCHITECTURE.md`, `ASSESSMENT.md`, `diplomat-testing-doc.md`, `CLAUDE.md`, `CODEX.md`).

Tests: `.venv/bin/python -m pytest` — 308 passed. Dependency probe: not rerun; Phase 22 introduced no new external dependency surface, and the local smoke-equivalent import/tests passed in 22.6.

## 2026-05-31 — Phase 23 plan

Action: PLAN
Mode: Build
Outcome: Activated Phase 23 as the current Build phase and converted its scoring-expansion scope into state-machine executable steps: Pareto efficiency implementation, Pareto tests, process-signature implementation, process-signature tests, and docs.

Scope decision: Phase 23 is diagnostic-only. It adds post-game scoring/reporting fields for self-play analysis without changing agent behavior or live provider/runtime paths.

### Step 23.1: Pareto efficiency scoring field

Mode: Build
Outcome: `GameEnvironment.score_game()` now post-processes the structured scorer output with aggregate Pareto-efficiency metrics. It reuses the scenario optimum enumerator to find the best Pareto-frontier aggregate score, sums achieved faction scores, and writes `achieved_score_sum`, `max_pareto_sum`, and `pareto_efficiency` into the per-run scoring JSON.
Contract changes: Self-play scoring JSON now includes three deterministic aggregate scoring fields.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 29 passed.

### Step 23.2: Pareto efficiency tests

Mode: Build
Outcome: Added deterministic Pareto-efficiency tests for optimum, BATNA-ratio, and no-deal scoring cases, plus a fake-backed async `score_game()` test that verifies `pareto_efficiency` is present and numeric in scorer output.
Contract changes: None; this step verifies the scoring JSON fields added in 23.1.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 33 passed.

### Step 23.3: Process signatures aggregator

Mode: Build
Outcome: Added `compute_process_signatures()` to the self-play analysis report with deterministic `broken_promise_rate`, `coalition_stability`, `time_to_deal`, and per-faction `opening_gap`. Simulation result JSON now includes `process_signatures`; scenario-backed runs also preserve `scenario_analysis` so opening-gap scoring can use the point tables.
Contract changes: Self-play result JSON now includes `process_signatures`, and scenario-backed results include `scenario_analysis`.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 33 passed. `.venv/bin/python -m tests.self_play.analysis --results tests/self_play/results/phase22_verify_dryrun.json` — passed and printed the process-signatures section.

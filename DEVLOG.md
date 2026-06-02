# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

## 2026-06-02 — Phase 28 Plan

Action: PLAN
Mode: Build
Outcome: Scope and design confirmed for Phase 28 (coached self-play harness + near-miss diagnostic). No code changes in this step.

Design decisions:

**Coached self-play harness (`coached_game.py`):**
- Subclasses `GameEnvironment`, overriding `setup()` to inject `TelegramReviewGate` (real) or `FakeTelegramReviewGate` (dry-run) via `module_overrides["review_gate"]` for the coached faction's Orchestrator. All other factions continue to use `AutoApproveReviewGate` via YAML config.
- `TelegramReviewGate` constructor: `(telegram_client, *, coaching_channel_id, state_manager=None, timeout_seconds=None)` — confirmed in `src/modules/review_gate/__init__.py`.
- `FakeTelegramReviewGate` is a distinct class (not `AutoApproveReviewGate`) so tests can assert wiring via `isinstance` check without requiring Telegram.
- Reuses scenario compilation, persona loading, and LLM client construction from `run_simulation.py` via imports — does NOT fork the file. Only `GameEnvironment` construction differs.
- CLI: `--coach-faction <id>` (required) plus pass-through of standard `run_simulation` flags.
- Fail-fast when Telegram env vars (`TELEGRAM_BOT_TOKEN`, `DIPLOMAT_COACHING_CHANNEL_ID`, `DIPLOMAT_OPERATOR_USER_IDS`) are absent unless `--dry-run`.

**Near-miss diagnostic (`compute_near_miss()` in `analysis.py`):**
- Reuses `_score_position_text()` logic (already in `analysis.py`) to extract per-faction positions from round responses by matching outcome strings from `scenario_analysis['issues'][*]['outcomes']`.
- "Converging" threshold: 2+ factions share the same top-scored outcome on a majority of issues in the final round.
- `defection_event_log`: diffs R(n) → R(n+1) per faction per issue using the same position extraction; emits one entry per issue-level change with `was_contingent` heuristic (substring search for "if"/"contingent on"/"conditional on" in prior round response).
- Insertion point: new "NEAR-MISS DIAGNOSTIC" section in `analyze_results()`, placed after "NO-DEAL-AWARE SCORING".
- Defensive: if `scenario_analysis` is missing, emit `near_miss=None` and skip silently.

Contract changes: None. No source-code changes in this step.

Tests: N/A — analysis-only step.

     Archival rule: When this file exceeds ~500 lines, move completed
     module entries to DEVLOG_archive.md during phase completion cleanup.
     Add a boundary marker: <!-- Entries above archived from Module N, YYYY-MM-DD -->

<!-- Entries above archived from Phase 25, 2026-06-01 -->

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

### Step 23.4: Process signature tests

Mode: Build
Outcome: Added a synthetic self-play result fixture covering duplicated promise records, a dissolved coalition, a round-3 deal marker, and round-1 opening positions. Four focused tests now assert the expected broken-promise rate, coalition-stability ratio, time-to-deal, and per-faction opening gaps.
Contract changes: None; this step verifies the process-signature contract added in 23.3.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 37 passed.

### Step 23.5: Scoring docs

Mode: Build
Outcome: Updated `ASSESSMENT.md` to mark Pareto efficiency and four deterministic process signatures implemented, with code references and Block C debt narrowed to skill premium, transcript-interpretive signatures, reverse scenario builder, and BATNA defaults. Updated `diplomat-testing-doc.md` Layer 4 status and post-game report notes for process signatures and new scoring JSON fields.
Contract changes: Documentation now reflects the self-play result JSON additions from Phase 23.

Tests: `.venv/bin/python -m pytest` — 316 passed.

### Phase 23 review — 2026-05-31

Mode: Review
Outcome: Phase review clean. No must-fix or should-fix items found. Pareto efficiency formula is correct per DEVPLAN spec; `find_pareto_frontier` + max-sum-on-frontier matches the intended denominator. Process signatures cover all 4 deterministic metrics. 316 tests pass (8 new from Phase 23). Committed 5 steps across plan→execute→close arc without regressions.
Contract changes: None — review-only, no code changes.

Tests: `python -m pytest tests/` — 316 passed.

## 2026-05-31 — Phase 23 close

Action: CLOSE
Mode: Build
Outcome: Closed the scoring expansion phase. `_pareto_efficiency_metrics()` in `tests/self_play/game_environment.py` injects three aggregate scoring fields (`achieved_score_sum`, `max_pareto_sum`, `pareto_efficiency`) into every scored game result. `compute_process_signatures()` in `tests/self_play/analysis.py` computes four deterministic per-run signatures (`broken_promise_rate`, `coalition_stability`, `time_to_deal`, `opening_gap`). Both are emitted in the self-play result JSON and rendered in the CLI analysis report.

Docs updated during close: `DEVPLAN.md` reduced Phase 23 to a completion summary and updated Current Status to Phase 24; `ARCHITECTURE.md` regression test count updated to 316; `ASSESSMENT.md` §3.2 and §3.4 marked implemented in step 23.5.

DEVLOG learning review: No trial-and-error patterns observed. Phase 23 ran cleanly across 5 steps with no escalation. No new gotchas to promote.

Contract changes: Self-play result JSON gains `achieved_score_sum`, `max_pareto_sum`, `pareto_efficiency`, `process_signatures`, and `scenario_analysis` fields. No production module contracts changed — all additions are in `tests/self_play/`.

Tests: `python -m pytest tests/` — 316 passed.

## 2026-05-31 — Phase 24 plan

Action: PLAN
Mode: Build
Outcome: Activated Phase 24 as the current Build phase and converted its small-build scope into seven state-machine executable steps: toolkit OpenAI dispatch tests, asymmetric BATNA flags, force-clamped BATNAs, runtime game-mode override, extraction examples JSON config, schema-derived entity types, and named doc updates.

Scope decision: Phase 24 is pure code/test/doc work with no live API requirement. Review and close remain controller-managed actions rather than checklist steps.

## 2026-05-31 - Step 24.1 + toolkit portion of 24.7 (operator-direct)

Action: EXECUTE (out-of-loop)
Mode: Build
Outcome: Iter 62 correctly escalated EXIT 2 on step 24.1 because the step targets `toolkit/tests/llm_client/` which is outside the diplomat worker's permitted project tree (WORKER_SPEC §8). Operator completed step 24.1 directly: added `TestOpenAIProviderTokenParam` to `toolkit/tests/llm_client/test_core.py` with two parametrized tests covering (a) reasoning models (`gpt-5*`, `o1*`, `o3*`, `o4*`) → `max_completion_tokens` and (b) legacy models (`gpt-4*`, `gpt-3.5*`) → `max_tokens`. 10 test cases pass. Toolkit suite total: 55 passed in `tests/llm_client/test_core.py` (was 45).

Also completed the toolkit-side portion of step 24.7 in the same pass: added "Token-parameter dispatch (OpenAIProvider)" subsection to `toolkit/ARCH_llm_client.md` and a short note in `toolkit/API.md`. Diplomat-side docs (CLI_REFERENCE, TUNING, diplomat-testing-doc, ARCH_extraction, ARCH_reconciliation) remain for the worker as part of step 24.7.

DEVPLAN edits: step 24.1 marked `[x]` with a "Completed directly by operator" note; step 24.7 trimmed to diplomat docs only with explicit "do NOT attempt to modify toolkit" guard. The loop can now run steps 24.2–24.6 then 24.7 (diplomat docs only) → REVIEW → CLOSE without hitting the project-tree boundary again.

Audit of remaining queue (Phase 24 was the only active phase): no other steps in 24.2–24.7 touch `../toolkit`. Phase 25+ not yet planned.

### Step 24.2: Asymmetric BATNA fractions

Mode: Build
Outcome: Added `--batna-fractions` JSON parsing for `tools.scenario_compiler` and `tests.self_play.run_simulation`, with scalar `--batna-fraction` retained as the fallback for factions not listed in the map. The compiler prompt now includes per-faction BATNA targets when supplied, and `validate_batna_pressure()` validates each faction against its asymmetric target.
Contract changes: CLI surface gains `--batna-fractions`; `analyze_scenario()` and `validate_batna_pressure()` now accept optional per-faction BATNA target maps.

Tests: `python3 -m pytest tests/test_scenario_compiler.py tests/test_self_play.py` — 66 passed. `python3 -m pytest` — 321 passed.

### Step 24.3: Force BATNA fraction clamp

Mode: Build
Outcome: Added `--force-batna-fraction` to `tools.scenario_compiler`. When set, compiled analysis is post-processed before save/persona generation so every faction BATNA is overwritten to `target_fraction * max_possible_score`, using `--batna-fractions` asymmetric targets when present and the scalar fallback otherwise. Default behavior remains unchanged and preserves narrative-explicit BATNAs.
Contract changes: CLI surface gains `--force-batna-fraction`; `force_batna_targets()` is available as a deterministic helper for compiler tests and future tooling.

Tests: `python3 -m pytest tests/test_scenario_compiler.py` — 32 passed. `python3 -m pytest tests/integration/test_pipeline_flow.py tests/test_scenario_compiler.py` — 38 passed after investigating a transient async integration failure. `python3 -m pytest` — 324 passed.

### Step 24.4: Runtime game-mode override

Mode: Build
Outcome: Added `--game-mode {cooperative,competitive,mixed}` to `tests.self_play.run_simulation`. Scenario-backed runs now apply the override to a copied analysis object before temporary persona generation, so source `scenario_analysis.json` remains unchanged while the run-time persona text receives the selected game-mode layer.
Contract changes: Self-play runner CLI gains `--game-mode`; scenario-backed result JSON reflects the runtime override in its copied `scenario_analysis`.

Tests: `python3 -m pytest tests/test_self_play.py` — 39 passed. `python3 -m pytest` — 326 passed.

### Step 24.5: Extraction examples JSON

Mode: Build
Outcome: Moved the extraction few-shot examples out of Python into `config/examples/extraction_examples.json`. `OpenAIStructuredExtractor` now loads examples from JSON at construction time, and `Orchestrator` resolves `paths.examples.extraction` with a default of `config/examples/extraction_examples.json`. Added the explicit path to `pipeline.yaml` and `pipeline_smoke.yaml`.
Contract changes: Extraction examples are now config data; `OpenAIStructuredExtractor` accepts an `examples_path` constructor argument, and pipeline config supports `paths.examples.extraction`.

Tests: `python3 -m pytest tests/test_extraction.py tests/test_orchestrator.py tests/integration/test_pipeline_flow.py` — 80 passed. `python3 -m pytest` — 328 passed.

### Step 24.6: Schema-derived entity type references

Mode: Build
Outcome: Reconciliation now derives tracked entity type names from `config/schemas/state_patch.json` and uses that list in both the system prompt and user prompt context. The self-play analysis report also derives its per-agent entity count rows from the same schema shape. Tests add a synthetic `treaties` schema key and verify it appears in both reconciliation prompts and analysis output without code changes.
Contract changes: `StateReconciler` accepts an optional `state_patch_schema_path`; reconciliation and self-play analysis now treat state patch root properties as the source of truth for report/prompt entity lists.

Tests: `python3 -m pytest tests/test_reconciliation.py tests/test_self_play.py` — 47 passed. `python3 -m pytest` — 330 passed.

## 2026-05-31 - Step 24.7 doc update (operator-direct)

Action: EXECUTE (out-of-loop)
Mode: Build
Outcome: All 5 diplomat docs from step 24.7 updated.
- `CLI_REFERENCE.md`: added rows for `--batna-fractions`, `--force-batna-fraction`, `--game-mode` in both the `run_simulation` and `scenario_compiler` flag tables; updated `--batna-fraction` description to note scalar-fallback role; added a four-example block to `scenario_compiler` showing the new flags in use.
- `TUNING.md` §1: added new subsections "Asymmetric BATNAs (`--batna-fractions`)", "Force-clamp narrative BATNAs (`--force-batna-fraction`)", "Game-mode runtime override (`--game-mode`)"; extended the Workflows list with two new entries pointing into the new subsections.
- `diplomat-testing-doc.md` §4 Layer 2: callout under the section heading noting the extraction examples now live at `config/examples/extraction_examples.json`.
- `ARCH_extraction.md`: new paragraph in the OpenAIStructuredExtractor implementation note covering `examples_path`, the default config location, and the `paths.examples.extraction` pipeline.yaml key.
- `ARCH_reconciliation.md`: new "Schema-driven entity types (Phase 24.6)" subsection in the Solution section explaining the reconciler and self-play `analysis.py` now derive entity keys from `state_patch.json`.

Done out-of-loop because the worker had already EXIT-2'd Phase 24 once on a project-boundary issue (24.1); operator finished off the remaining doc obligations in a single sweep rather than re-dispatching for one step. Phase 24 is now fully checked off (24.1-24.7) and the loop can transition to REVIEW on the next dispatch.

## 2026-06-01 - Phase 24 execute verification + state_machine.sh bugfix

Action: EXECUTE (worker iteration)
Mode: Build
Outcome: Phase 24 definition of done verified. 330 tests passing.

Bug fixed: `tools/state_machine.sh` `count_unchecked()` used `|| echo "0"` as a fallback, but `grep -c` already prints "0" to stdout before exiting 1 on no matches — producing "0\n0" which failed `[: integer expression expected` on every comparison, preventing the automatic execute→review state transition. Fixed to `|| true` so grep's "0" output is the sole return value. DEVPLAN state manually advanced to `review` with steps_remaining cleared.

## 2026-06-01 - Phase 24 review

Action: REVIEW
Mode: Build
Outcome: Phase 24 code review passed — no must-fix or should-fix items. 330 tests passing.

Review findings:
- 24.2/24.3: `--batna-fractions` + `--force-batna-fraction` in scenario_compiler.py. Validation delegated to `_validate_batna_fraction` consistently. `force_batna_targets` uses `copy.deepcopy` — no mutation. Correct.
- 24.4: `--game-mode` validates against `_GAME_MODE_CHOICES` before applying; uses deepcopy. Correct.
- 24.5: `load_examples()` validates array + per-item types. `_EXTRACTION_EXAMPLES` constant fully removed from Python; 5 examples load cleanly from JSON. Config path wired in both `pipeline.yaml` and `pipeline_smoke.yaml`. Correct.
- 24.6: `state_patch_entity_types()` function reads schema keys dynamically. Both `LLMReconciler.__init__` and `analysis.py` `score_game()` call it — no hardcoded `["promises", "coalitions", "inconsistencies"]` list remains in either module. Residual hardcoded strings in `state_manager` and `extraction` examples are domain-specific (not the prompt-builder path targeted by 24.6). Correct.
- CRLF artifacts: several files show line-ending-only diffs vs working tree (persona, service.sh, pipeline_smoke.yaml, self-play results). Not code changes; NTFS drive artifact. No action needed.

State advanced to `close`.

## 2026-06-01 — Phase 24 close

Action: CLOSE
Mode: Build
Outcome: Phase 24 governance cleanup complete. 330 tests passing.

Summary of what was built:
- **24.2/24.3**: Asymmetric per-faction BATNA pressure via `--batna-fractions` JSON map; `--force-batna-fraction` post-clamp override. Both flags wired into `scenario_compiler.py` and `run_simulation.py`.
- **24.4**: `--game-mode` runtime override for self-play runs; `_apply_game_mode_override()` validates against the canonical game-mode list and deep-copies the analysis dict.
- **24.5**: `_EXTRACTION_EXAMPLES` extracted from Python to `config/examples/extraction_examples.json`. `load_examples()` validates input types. Path configurable via `pipeline.yaml` `paths.examples.extraction`.
- **24.6**: `state_patch_entity_types()` reads entity keys from `state_patch.json` schema. Both `LLMReconciler` and `analysis.py` use it — no hardcoded entity type list remains in prompt-builder paths.
- **24.7**: Doc updates: `CLI_REFERENCE.md`, `TUNING.md`, `diplomat-testing-doc.md`, `ARCH_extraction.md`, `ARCH_reconciliation.md`.
- **Infra**: Fixed `state_machine.sh` `count_unchecked()` double-echo bug (`grep -c` + `|| echo "0"` → `|| true`).

Gotchas review: No new prescriptive one-liners to add. The state_machine.sh bugfix is self-contained and documented in the commit message. The CRLF artifact behavior on NTFS is already in Cold Start Summary.

Contract changes: None. Phase 24 made no cross-module API changes. `state_patch_entity_types()` is a new public function exported from `reconciliation/__init__.py` — it's a helper, not a contract.

Governance: DEVPLAN Phase 24 section reduced to one-line summary; Current Status updated to reflect close + audit gate. ARCHITECTURE.md testing status updated (316 → 330). DECISIONS.md D-28 closed.

DEVLOG archival: Skipped — file is 283 lines, under 500 threshold.

## 2026-06-01 — Phase 26 plan

Action: PLAN
Mode: Build
Outcome: Activated Phase 26 as the current Build phase. The existing structured per-event logging plan remains the executable checklist: scope/design, startup logging config, transport instrumentation, pipeline/flow/orchestrator instrumentation, config/env wiring, logging tests, and named doc updates.

Scope decision: logging should be diagnostic-first and operator-visible through the existing service log path. Runtime code should use module loggers, fixed event-type strings, stdout/stderr stream handling captured by `tools/service.sh`, default INFO verbosity, and `DIPLOMAT_LOG_LEVEL` for temporary DEBUG escalation without config edits.

Contract changes: None yet. The phase is expected to add operator-facing logging configuration and documented log event names, but no module API changes are planned.

Tests: Not run; planning-only action.

### Step 26.1: Structured logging scope and design

Mode: Build
Outcome: Confirmed there is no existing `logging` usage under `src`; production diagnostics currently rely on `print()` in `EventDrivenFlow` and legacy `_OrchestratorCore` paths, including the startup banner, extraction failure notices, and reconciliation messages.
Contract changes: None.

Design decisions for implementation: use module-local loggers with stable `diplomat.*` names derived from `__name__`, configure stream output only so `tools/service.sh` continues to own log file capture via `tee`, default to format `%(asctime)s %(levelname)s %(name)s %(message)s`, read `logging.level` / optional `logging.format` from pipeline config with `DIPLOMAT_LOG_LEVEL` overriding the level, and emit fixed event names for grep-able diagnosis: `startup.online`, `event.received`, `event.routed`, `event.sent`, `extraction.scheduled`, `extraction.start`, `extraction.complete`, `extraction.skip`, `round.boundary`, `pipeline.trigger`, `pipeline.complete`, and `reconciliation.*`.

Notes: Transport instrumentation should prioritize Telegram sender/faction/operator classification because that was the Phase 19 smoke failure mode. Flow/pipeline instrumentation should make event routing, extraction task scheduling, round-boundary handling, and response pipeline completion visible without adding a second log-file writer.

Tests: Not run; scope/design-only step. Validation was source inspection plus `grep -RIn "import logging\\|logging\\.\\|print(" src tests config`.

### Step 26.2: Logging configuration and startup banner

Mode: Build
Outcome: Added `src/logging_config.py` with `configure_logging(config_path)` and `get_logger(name)`. `main.run()` now configures the `diplomat` logger before building toolkit adapters or the orchestrator. `EventDrivenFlow._print_online_banner()` now emits `startup.online DIPLOMAT ONLINE ...` through `diplomat.flows.event_driven` instead of `print()`.
Contract changes: New operator-facing logging configuration path exists internally: `logging.level` and `logging.format` are read when present, and `DIPLOMAT_LOG_LEVEL` overrides the level. The config files and docs are intentionally left for 26.5/26.7.

Notes: The logger uses a single stream handler on the `diplomat` namespace, with default format `%(asctime)s %(levelname)s %(name)s %(message)s`, so `tools/service.sh` continues to capture output via `tee` without a second file writer.

Tests: `.venv/bin/python -m pytest tests/test_main.py tests/test_flows.py` — 13 passed.

### Step 26.3: Telegram transport instrumentation

Mode: Build
Outcome: Instrumented `TelegramBotTransport` with `event.sent`, `event.received`, and `event.tagged` records through `diplomat.modules.transport`. Successful outbound sends now log channel, recipient, chat ID, and content length. Valid inbound updates now log chat ID, mapped channel, sender ID, a normalized 60-character text preview, sender faction, and the classification path (`operator_user_id`, `faction_map`, `coaching_channel_default`, `private_chat_default`, or `public_unmapped`).
Contract changes: None. Transport APIs and normalized event shapes are unchanged.

Notes: The classification log directly exposes the Phase 19 smoke failure mode where Telegram sender IDs mapped unexpectedly and messages appeared as operator traffic.

Tests: `.venv/bin/python -m pytest tests/test_transport.py` — 26 passed.

### Step 26.4: Pipeline, flow, and orchestrator instrumentation

Mode: Build
Outcome: Added structured records across `diplomat.pipeline`, `diplomat.flows.event_driven`, and `diplomat.orchestrator`. Event-driven flow now logs `event.routed` for operator, faction-extraction, and system paths, `extraction.scheduled` for per-event debounce tasks, `round.boundary` when the signal detector fires, and direct-address `pipeline.trigger` / `pipeline.complete`. The orchestrator core now logs `extraction.start`, `extraction.skip`, `extraction.complete` with patch summaries, round-boundary reconciliation/analyst stages, preview-command triggers, and response pipeline success/failure reasons through generation, adversarial, review, and send stages. `Pipeline` emits DEBUG-level delegation/storage records.
Contract changes: None. Public Pipeline, Flow, and Orchestrator APIs are unchanged.

Notes: `signal_round_detector()` now attaches the configured regex pattern to the detector callable so `round.boundary` logs can include the pattern without changing the Flow contract.

Tests: `.venv/bin/python -m pytest tests/test_pipeline.py tests/test_flows.py tests/test_orchestrator.py` — 67 passed. Additional focused rerun after the system-route label change: `.venv/bin/python -m pytest tests/test_flows.py` — 8 passed.

### Step 26.5: Logging config and env override

Mode: Build
Outcome: Added `logging.level: INFO` and the standard log format to both `config/pipeline.yaml` and `config/pipeline_smoke.yaml`. The existing `configure_logging(config_path)` path now reads those values at startup, while `DIPLOMAT_LOG_LEVEL` overrides the configured level for temporary DEBUG/diagnostic runs. `CLI_REFERENCE.md` documents the new env var for direct `src/main.py` invocation and `tools/service.sh`.
Contract changes: Operator-facing config/env surface now includes `logging.level`, `logging.format`, and `DIPLOMAT_LOG_LEVEL`.

Notes: `config/pipeline_smoke.yaml` had pre-existing CRLF-only dirty state; the commit stages only the semantic logging block for that file and leaves unrelated line-ending churn uncommitted.

Tests: `.venv/bin/python -m pytest tests/test_main.py` — 5 passed. YAML validation confirmed both pipeline configs contain the logging block and parse successfully.

### Step 26.6: Logging tests and default test noise suppression

Mode: Build
Outcome: Added focused logging assertions for the flow and Layer 3 paths. `tests/test_flows.py` now asserts faction traffic emits `event.routed` and `extraction.scheduled`. `tests/integration/test_phase18_paths.py` now asserts a real fixture event leaves `event.routed`, `extraction.scheduled`, and `extraction.complete` records in `caplog`, which gives future smoke debugging a tested log surface. Added root `tests/conftest.py` to keep `diplomat.*` loggers at WARNING with no handlers by default, while allowing logging tests to opt into INFO via `caplog`.
Contract changes: None. Test infrastructure now controls default `diplomat.*` logging noise.

Notes: Existing transport log tests from 26.3 already cover `event.sent`, `event.received`, and `event.tagged`; this step adds the flow/integration assertions required by the phase checklist.

Tests: `.venv/bin/python -m pytest tests/test_flows.py tests/test_transport.py tests/integration/test_phase18_paths.py` — 42 passed.

### Step 26.7: Logging docs

Mode: Build
Outcome: Updated `ARCH_orchestrator.md`, `ARCH_transport.md`, `ARCH_extraction.md`, and `ARCH_reconciliation.md` with logging sections that name logger namespaces and stable event strings. Updated `SMOKE_RUNBOOK.md` §3 with a structured-log verification command and event strings to look for in `logs/diplomat.log`. Updated `diplomat-testing-doc.md` to document logging config, `DIPLOMAT_LOG_LEVEL`, default test log suppression, and the new Layer 3 log assertions.
Contract changes: Documentation now defines the operator-facing logging configuration and expected diagnostic event names.

Notes: `ARCH_reconciliation.md` documents current round-boundary reconciliation dispatch logs and explicitly calls out that lower-level `reconciliation.*` records are a possible later cleanup, since this phase logs reconciliation through `round.boundary` stages.

Tests: Not run; documentation-only step.

### Step 26.8: Pre-review readiness

Mode: Build
Outcome: Completed the final Phase 26 checklist item and verified the phase is ready for formal review. Structured logging code, config defaults, logging tests, CLI/env docs, ARCH docs, smoke runbook, and testing guide updates are in place.
Contract changes: None beyond the logging config/env and documented event-name surface already captured in 26.5 and 26.7.

Notes: Live bot-log verification (`incus exec ... cat logs/diplomat.log`) remains a smoke/deployment activity, not something this local test run can perform.

Tests: `.venv/bin/python -m pytest` — 337 passed.

### Phase Review 26: Structured per-event logging

Mode: Review
Outcome: No must-fix or should-fix items found. All Phase 26 definition-of-done criteria met: 337 tests pass (≥ 330), structured logging implemented across transport and flow layers, `DIPLOMAT_LOG_LEVEL` env override and yaml config wired, caplog unit + integration tests added, all four ARCH docs and SMOKE_RUNBOOK and diplomat-testing-doc updated. State advanced to close.
Contract changes: None.

Tests: 337 passed.

## 2026-06-01 — Phase 27 plan

Action: PLAN
Mode: Build
Outcome: Confirmed Phase 27 as a metric-only Build phase. The existing five-step checklist is the execution plan: insertion-point analysis, baseline-normalized metric implementation, report rendering, historical backfill tooling, and doc/retro-score updates.
Contract changes: None yet. The planned result will extend self-play scoring output and reporting fields without changing scorer prompt semantics, provider routing, or agent behavior.

Notes: Partial-consensus scoring remains explicitly out of scope for Phase 27 and should stay a separate Phase 28 candidate.

Tests: Not run; planning-only action.

### Step 27.1: Design + scope confirmation

Mode: Build
Outcome: Confirmed the insertion and test points for Phase 27 no-deal-aware metrics. `_pareto_efficiency_metrics()` in `tests/self_play/game_environment.py` is the correct calculation point because `GameEnvironment.score_game()` already merges its returned fields into the `scores` payload. `tests/self_play/analysis.py` currently renders process signatures but no explicit score block, so Step 27.3 should add a score/no-deal-aware section near the existing post-game diagnostics. `tests/test_self_play.py` is the right test home: it already contains focused `_pareto_efficiency_metrics()` tests and the `analyze_results()` render test pattern.
Contract changes: None.

Notes: Step 27.2 can extend the existing helper in place; no scorer prompt or partial-consensus behavior needs to change.

Tests: Not run; analysis-only step per checklist.

### Step 27.2: Add baseline-normalized scoring fields

Mode: Build
Outcome: Extended `_pareto_efficiency_metrics()` with BATNA-normalized companion fields while preserving the existing `achieved_score_sum`, `max_pareto_sum`, and `pareto_efficiency` outputs. New fields are `sum_batnas`, `faction_deltas`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, and `negotiated_surplus_share`.
Contract changes: Self-play `scores` payloads now include the new baseline-normalized scoring fields when scenario analysis is available.

Notes: Added focused tests for at-BATNA, at-Pareto, below-BATNA, and zero-surplus-denominator cases. Population standard deviation is computed over faction deltas.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 42 passed.

### Step 27.3: Render new fields in the analysis report

Mode: Build
Outcome: Added a `NO-DEAL-AWARE SCORING` section to `tests/self_play/analysis.py` report output. The section renders `pareto_efficiency`, `negotiated_surplus_share`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, and sorted per-faction `faction_deltas`.
Contract changes: Self-play analysis reports now expose the baseline-normalized scoring fields when `results["scores"]` is present.

Notes: Added a capsys render test using the existing synthetic process-signature fixture so the section is covered without live LLM calls.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 43 passed.

### Step 27.4: Backfill tool for historical runs

Mode: Build
Outcome: Added `tools/backfill_scoring_metrics.py`, a CLI that reads `--results` and matching `--analysis`, computes Phase 27 metrics through the shared `_pareto_efficiency_metrics()` helper, prints all fields, and supports `--write-back` to patch `results.scores`.
Contract changes: New CLI utility for historical self-play scoring backfills.

Captured backfill values for Step 27.5 docs:

| Run | pareto_efficiency | negotiated_surplus_share | min_faction_delta |
|---|---:|---:|---:|
| Run 9 symmetric live | 0.593 | 0.000 | 0.000 |
| Run 9 alpha squeezed live | 0.630 | 0.000 | 0.000 |
| Run 9 beta squeezed live | 1.019 | 1.053 | 3.000 |
| Run 8 water rights 3-provider v3 | 0.537 | 0.000 | 0.000 |

Notes: The commands were run without `--write-back` so historical result JSON files were not modified in this step. Run 7 was skipped because it lacks a matching compiled scenario analysis, per the phase checklist. The Run 9 beta-squeezed historical scorer output exceeds the enumerated Pareto sum for its matching analysis, so both legacy `pareto_efficiency` and normalized surplus share are above 1.0; Step 27.5 should report the computed value rather than clamp it.

Tests: `.venv/bin/python tools/backfill_scoring_metrics.py ...` — completed for Run 9 symmetric, Run 9 alpha squeezed, Run 9 beta squeezed, and Run 8 compiled backfill.

### Step 27.5: Doc updates + Run 9 retro-scores

Mode: Build
Outcome: Updated `ASSESSMENT.md` §3.2 with the baseline-normalized surplus formula and companion scoring fields, updated `diplomat-testing-doc.md` Layer 4 with the new self-play JSON/report fields, and added a `Retro-scored with Phase 27 metrics (2026-06-01)` subsection to the Run 9 entry in `TUNING_LOG.md`.
Contract changes: Documentation now treats `negotiated_surplus_share`, `faction_deltas`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, and `sum_batnas` as part of scenario-backed self-play scoring output.

Notes: Closed the TUNING_LOG open item for no-deal `pareto_efficiency` being confounded with BATNA height. Partial-consensus scoring remains open and out of Phase 27 scope.

Tests: `.venv/bin/python -m pytest` — 340 passed.

### Phase 27 Review

Mode: Review
Outcome: No must-fix or should-fix items found.
- `_pareto_efficiency_metrics()`: correct BATNA-normalized logic, zero-denominator guard, negative delta propagation. Return type `dict[str, Any]` appropriate.
- `analyze_results()`: new NO-DEAL-AWARE SCORING section renders all 6 fields; missing `faction_deltas` handled gracefully.
- 4 new focused tests (at-BATNA, below-BATNA, zero-denominator, render) pass cleanly.
- `tools/backfill_scoring_metrics.py`: clean CLI reusing `_pareto_efficiency_metrics()` directly.
- 340 tests passing (≥ 337 criterion met). Pre-existing `test_pipeline_flow.py` transient ordering issue not introduced by Phase 27.
Contract changes: None.

## 2026-06-01 — Phase 27 close

Action: CLOSE
Mode: Build
Outcome: Phase 27 governance cleanup complete. 340 tests passing.

Summary of what was built: `_pareto_efficiency_metrics()` in `tests/self_play/game_environment.py` now returns six BATNA-normalized companion fields alongside the existing Pareto efficiency fields — `sum_batnas`, `faction_deltas`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`, and `negotiated_surplus_share`. These flow into `GameEnvironment.score_game()` output automatically. `tests/self_play/analysis.py` renders them in a new `NO-DEAL-AWARE SCORING` subsection. `tools/backfill_scoring_metrics.py` recomputes all Phase 27 fields for historical runs given a results JSON and matching scenario_analysis JSON. Four focused unit tests cover the at-BATNA, below-BATNA, zero-denominator, and render cases.

Docs updated: `ASSESSMENT.md` §3.2 (baseline-normalized surplus formula + field reference), `diplomat-testing-doc.md` Layer 4 (new self-play result JSON fields), `TUNING_LOG.md` Run 9 entry (retro-scores table for all four Run 9 variants + Run 8 backfill). `ARCHITECTURE.md` test count updated to 340. DEVPLAN Phase 27 reduced to history summary.

DEVLOG learning review: No new gotchas. The backfill pattern (reuse `_pareto_efficiency_metrics()` directly without an LLM, parse results JSON, optionally write back) is clean and follows the same approach as `tools/backfill_pareto.py` — already an established pattern in this project.

Contract changes: Self-play `scores` payloads now include the six Phase 27 fields when scenario analysis is available. These are documented in `diplomat-testing-doc.md` Layer 4. No changes to scorer prompt semantics, provider routing, or runtime agent behavior.

Tests: `.venv/bin/python -m pytest` — 340 passed.

DEVLOG archival: Archived Phase 26 entries to `DEVLOG_archive.md`; Phase 27 entries remain in `DEVLOG.md` for immediate audit.

## 2026-06-02 — Phase 28 Step 28.1

Mode: Execute
Outcome: Confirmed the coached-game harness can stay layered on top of `tests/self_play/game_environment.py` rather than forking `run_simulation.py`. `run_simulation.py` already centralizes scenario compile/load, cost-accountant wiring, and `GameEnvironment` construction, so the new harness can reuse its scenario/persona/bootstrap flow and swap in a coached review gate at the per-faction config boundary. Also confirmed `TelegramReviewGate` lives in `src/modules/review_gate/__init__.py` and its constructor takes `telegram_client`, `coaching_channel_id`, optional `state_manager`, and optional `timeout_seconds`.

Analysis findings:
- The coached-game path is best implemented as a wrapper around `GameEnvironment` setup, not a fork of the self-play runner.
- Per-faction review-gate customization belongs in the generated pipeline config or module overrides, since `GameEnvironment._generate_faction_config()` is already the single place where review gates are declared.
- `tests/self_play/analysis.py` has a clean insertion point for the near-miss block immediately after `NO-DEAL-AWARE SCORING` and before `PROCESS SIGNATURES`.

Tests: Not run; analysis-only step per checklist.

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

## 2026-06-01 — Phase 25 plan

Action: PLAN
Mode: Build
Outcome: Activated Phase 25 as the current Build phase and converted the `tools/service.sh` tmux rewrite into six executable steps: scope/design confirmation, `start()` rewrite, `stop()` rewrite, `status()`/`restart()` rewrite, shell-driven service smoke test, and named doc updates.

Scope decision: `tools/service.sh` will use tmux as the source of truth, with default session `bot`, `BOT_TMUX_SESSION` override for tests/parallel deployments, user-aware sudo behavior, and an explicit missing-session error rather than auto-creating a session. Review and close remain state-machine actions, not executable checklist steps.

### Step 25.1: Service tmux scope analysis

Mode: Build
Outcome: Confirmed the existing `tools/service.sh` still uses `.diplomat.pid` plus `nohup`, while the operational docs identify the surviving Pi launch pattern as a tmux window in the long-lived `bot` session. Settled the replacement design for the remaining implementation steps.
Contract changes: None.

Design decisions for implementation: `BOT_TMUX_SESSION` overrides the default `bot` session, tmux commands run through `sudo -u claude` unless the current user is already `claude`, and a missing tmux session fails with `session '<name>' not found; create with: sudo -u claude tmux new-session -d -s <name>` rather than auto-creating.

Tests: Not run; analysis-only step.

### Step 25.2: Rewrite service start

Mode: Build
Outcome: Replaced the `start()` path in `tools/service.sh` with tmux-window launch. The script now defines `BOT_TMUX_SESSION`/`TMUX_WINDOW`, checks that the configured tmux session exists, skips `sudo -u claude` when already running as user `claude`, starts `.venv/bin/python -u src/main.py` in a foreground tmux pane, pipes output through `tee -a logs/diplomat.log`, and removes the legacy PID file after launch.
Contract changes: `tools/service.sh start` no longer writes `.diplomat.pid`; tmux is now the start-path source of truth.

Notes: Normalized `tools/service.sh` to LF because the pre-existing CRLF-only dirty state produced mixed endings after the patch and failed shell parsing. `stop()` and `status()` still use the old PID path and are intentionally left for 25.3/25.4.

Tests: `bash -n tools/service.sh`; `BOT_TMUX_SESSION=__diplomat_missing_test bash tools/service.sh start` exits 1 with the expected missing-session message.

### Step 25.3: Rewrite service stop

Mode: Build
Outcome: Replaced the PID-backed `stop()` path with tmux window cleanup. `stop()` now checks for the configured `diplomat` tmux window, kills `"$BOT_TMUX_SESSION":diplomat` when present, and exits successfully with "Diplomat is not running" when the window is absent.
Contract changes: `tools/service.sh stop` no longer reads, kills, or cleans up `.diplomat.pid`.

Tests: `bash -n tools/service.sh`; temporary tmux session smoke (`__diplomat_stop_test`) verified `stop` kills only the `diplomat` window and is idempotent on a second call.

### Step 25.4: Rewrite service status and restart

Mode: Build
Outcome: Replaced the remaining PID-backed `status()` path with tmux window detection and removed the obsolete PID helper/variable. `status` now reports `Diplomat is running (tmux window <session>:diplomat)` when the configured window exists and `Diplomat is not running` otherwise. `restart` remains the existing compositional `stop; start` case, now using tmux-backed subcommands.
Contract changes: `tools/service.sh status` no longer reads or removes `.diplomat.pid`; the lifecycle surface is now tmux-backed for `start`, `stop`, `status`, and `restart`.

Tests: `bash -n tools/service.sh`; temporary tmux session smoke (`__diplomat_status_test`) verified not-running and running status outputs. Confirmed `restart)` remains `stop; start`.

### Step 25.5: Service shell smoke test

Mode: Build
Outcome: Added `tests/test_service_sh.py`, a shell-driven pytest smoke test for `tools/service.sh`. The test skips when `tmux` is unavailable, creates a temporary tmux session named `_test_diplomat_session`, copies the service script into a temporary project skeleton with a fake `.venv/bin/python`, drives `start`, polls `status` until the `diplomat` window is running, calls `stop`, verifies not-running status, and tears down the tmux session.
Contract changes: None; this step verifies the lifecycle contract added in 25.2-25.4.

Tests: `.venv/bin/python -m pytest tests/test_service_sh.py` — 1 passed.

### Step 25.6: Service lifecycle docs

Mode: Build
Outcome: Updated the service lifecycle docs now that `tools/service.sh` is tmux-backed. `CLI_REFERENCE.md` makes the script the canonical Pi interface again and documents `BOT_TMUX_SESSION`; `SMOKE_RUNBOOK.md` §2 uses `service.sh start/status/logs`; `diplomat-testing-doc.md` §5b promotes service.sh commands and removes the obsolete broken-nohup row; DEVPLAN's Pi deployment gotcha now points at `service.sh start`.
Contract changes: CLI/operator docs now define `tools/service.sh` as the canonical lifecycle interface over the underlying tmux window.

Tests: `.venv/bin/python -m pytest tests/test_service_sh.py` — 1 passed.

### Phase 25 review

Mode: Review
Date: 2026-06-01
Outcome: Phase review passed. Reviewed `tools/service.sh` (tmux-backed lifecycle), `tests/test_service_sh.py` (shell smoke test), and all four updated docs (CLI_REFERENCE.md, SMOKE_RUNBOOK.md, diplomat-testing-doc.md, DEVPLAN gotcha). No must-fix or should-fix items found. All 331 tests pass. State advanced to close.

## 2026-06-01 — Phase 25 close

Action: CLOSE
Mode: Build
Outcome: Phase 25 governance cleanup complete. 331 tests passing.

Summary of what was built: `tools/service.sh` now uses tmux as the service supervisor instead of `.diplomat.pid` + `nohup`. `start` launches a foreground `src/main.py` process in a `diplomat` tmux window and tees output to `logs/diplomat.log`; `stop`, `status`, and `restart` are tmux-backed and idempotent where appropriate. The default supervising session is `bot`, with `BOT_TMUX_SESSION` for tests and parallel deployments, and missing sessions fail with a clear create-session command.

Docs updated during the phase: `CLI_REFERENCE.md`, `SMOKE_RUNBOOK.md`, `diplomat-testing-doc.md`, and the DEVPLAN Pi deployment gotcha now make `tools/service.sh start` the canonical Pi lifecycle command. Close cleanup reduced Phase 25 to a DEVPLAN history summary, marked the audit gate before Phase 26, updated `ARCHITECTURE.md` test count to 331, and closed `DECISIONS.md` D-29.

DEVLOG learning review: No new gotchas promoted. The useful operational rule was already captured in the Cold Start Summary: use `service.sh` as the operator-facing interface; tmux is the underlying survival mechanism.

Contract changes: No runtime module contracts changed. The operator-facing service lifecycle contract changed from PID/nohup-backed to tmux-backed and is documented in `CLI_REFERENCE.md`.

Tests: `.venv/bin/python -m pytest tests/test_service_sh.py` — 1 passed. `.venv/bin/python -m pytest` — 331 passed.

DEVLOG archival: Skipped — file is 371 lines before this entry, under the ~500-line rotation threshold.

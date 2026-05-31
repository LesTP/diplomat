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

### Step 21.3: Stub analyst registry cleanup

Mode: Build
Outcome: Removed the test-only `StubAnalyst` entry from `src/registry.py` and updated `config/pipeline_test.yaml` to name `LLMAnalyst`. Integration tests continue to inject `tests.helpers.stub_analyst.StubAnalyst` through `module_overrides`.
Contract changes: Production registry no longer resolves test helpers; `diplomat-testing-doc.md` is queued for the Phase 21 doc-update step because it documents the StubAnalyst location/config pattern.

This keeps the production registry free of test-package imports while preserving fake-backed Layer 3 coverage.

Tests: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/integration -q` (76 passed); `.venv/bin/python -m pytest -q` (293 passed).

Next step: 21.4 logs reconciler exceptions instead of swallowing them.

### Step 21.4: Reconciler exception logging

Mode: Build
Outcome: Replaced four silent `except Exception: pass` blocks in `_reconcile_state()` with contextual log messages for promise deletes, status updates, inconsistency inserts, and missed-proposal inserts.
Contract changes: None.

Added a focused test that forces each apply path to fail and asserts the failure is visible in captured output while reconciliation continues.

Tests: `.venv/bin/python -m pytest tests/test_orchestrator.py tests/integration/test_phase18_paths.py -q` (60 passed); `.venv/bin/python -m pytest -q` (294 passed).

Next step: 21.5 adds `attribution` and `purpose` kwargs to the LLM adapter interface.

### Step 21.5: LLM call metadata kwargs

Mode: Build
Outcome: Added optional `attribution` and `purpose` kwargs to `ToolkitLLMAdapter.complete()` and forwarded them through both direct and cost-accounted paths. Updated toolkit `llm_client.complete()`, `complete_with_retry()`, and `CostAccountant.complete()` to accept/forward the same metadata.
Contract changes: LLM adapter/toolkit completion interface now accepts optional call metadata; downstream docs are queued for the Phase 21 doc-update step.

Added Diplomat adapter tests for direct/accounted forwarding plus toolkit tests for retry and cost-accountant forwarding.

Tests: `.venv/bin/python -m pytest tests/test_adapters.py tests/test_orchestrator.py -q` (56 passed); `.venv/bin/python -m pytest ../toolkit/tests/llm_client/test_core.py -q` (45 passed); `.venv/bin/python -m pytest ../toolkit/tests/cost_accountant/test_core.py -q` (44 passed); `.venv/bin/python -m pytest -q` (296 passed).

Next step: 21.6 removes `_TaggedLLMClient` and switches logging attribution to the new kwarg.

### Step 21.6: Attribution-based self-play logging

Mode: Build
Outcome: Deleted `_TaggedLLMClient`, removed the `_inner` unwraps in self-play/scenario compilation paths, and switched RECON/SCORE logging tags to `attribution` metadata. `LoggingLLMClient` now prefers `kwargs["attribution"]` over the current faction tag.
Contract changes: `toolkit.structured_llm.structured_call()` now accepts optional `attribution` and `purpose` kwargs and forwards them to the injected LLM client. `StateReconciler` accepts optional attribution and passes `purpose="reconciliation"`.

Updated self-play logging tests from wrapper-client assertions to attribution assertions, and updated dry-run verification comments.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py tests/test_reconciliation.py tests/self_play/verify_dryrun.py ../toolkit/tests/structured_llm/test_core.py -q` (54 passed); `.venv/bin/python -m pytest -q` (296 passed); toolkit targeted tests: structured_llm (19 passed), llm_client (45 passed), cost_accountant (44 passed).

Next step: 21.7 switches `DryRunLLMClient.classify_call()` to read `purpose`.

## 2026-05-31 — Phase 21.7: DryRunLLMClient purpose-based classification

Added `_PURPOSE_TO_CALL_TYPE` dict to `fake_llm_client.py` mapping semantic purpose strings ("generation", "adversarial", "extraction", "analysis", "reconciliation", "compilation", "scoring", "judge") to the internal call-type tokens (GEN, ADV, EXTRACT, ANALYST, RECON, COMPILE, SCORE, JUDGE). Updated `DryRunLLMClient.complete()` to read the `purpose` kwarg from its kwargs dict and resolve call type via that mapping instead of regex-matching the system prompt body.

Added `purpose=` to six `structured_call` / `complete()` invocations that previously lacked it:
- `src/modules/adversarial/__init__.py` → `"adversarial"`
- `src/modules/analyst/__init__.py` → `"analysis"`
- `src/modules/extraction/__init__.py` → `"extraction"`
- `src/modules/generation/__init__.py` (both JSON and plain paths) → `"generation"`
- `src/tools/scenario_compiler.py` → `"compilation"`
Existing sites (`reconciliation` → `"reconciliation"`, `game_environment` → `"scoring"`) were already correct from prior steps.

`classify_call(sys_prompt)` function retained in `fake_llm_client.py` — still used by `verify_dryrun.py` and `inspect_dryrun.py` to re-classify calls from saved JSON result files. Only `DryRunLLMClient` stops using it.

Tests: 296 passed; integration: 23 passed.

Next step: 21.8 — extract `build_reconciler` factory and `subsystem_llm_config` helper.

## 2026-05-31 — Phase 21.8: build_reconciler factory + subsystem_llm_config helper

Added two factory functions to `src/modules/reconciliation/__init__.py`:

`subsystem_llm_config(primary, tier="commodity")`: builds the minimal LLM config dict `{provider, models: {tier: model}, api_key}` from a pipeline.yaml-format primary provider config (which uses `api_key_env` rather than `api_key` directly). Eliminates the pattern duplicated 4 times across the codebase.

`build_reconciler(llm_client, llm_providers_config, tier, attribution)`: factory that reads `llm_providers_config["primary"]`, calls `subsystem_llm_config`, and returns a `StateReconciler` (or `None` if primary is missing).

Updated call sites:
- `src/main.py` `_attach_reconciler`: replaced manual dict construction + `StateReconciler(...)` with `build_reconciler(llm_client, config.get("llm_providers", {}))`. The "silently skip" path is now `if reconciler is None: return`.
- `tests/self_play/game_environment.py` `setup()`: added `_SELF_PLAY_PRIMARY` module-level dict constant; reconciler attachment uses `build_reconciler(recon_llm_client, {"primary": _SELF_PLAY_PRIMARY}, ..., attribution=...)`.
- `tests/self_play/game_environment.py` `score_game()`: scorer config uses `subsystem_llm_config(_SELF_PLAY_PRIMARY)`.
- `tests/self_play/run_simulation.py` `_compile_scenario()`: compilation config uses `subsystem_llm_config(...)` with a local `_compile_primary` dict.

Both helpers exported in `__all__`.

Tests: 296 passed; integration: 23 passed.

Next step: 21.9 doc update.

## 2026-05-31 — Phase 21.9: Doc update

Updated five reference docs to reflect Phase 21 changes:

- `ARCH_reconciliation.md` (§Interface): added `subsystem_llm_config` and `build_reconciler` factory to the public interface listing.
- `ARCH_orchestrator.md` (§State → §Construction): renamed to "Construction — OrchestrationOptions"; documented `OrchestrationOptions` dataclass (`auto_response_enabled`, `total_rounds`); documented `advance_to_round(n)` public method; updated State section to reference `options.auto_response_enabled` / `options.total_rounds` instead of top-level Orchestrator attributes.
- `ARCHITECTURE.md` (§Coupling Notes): added reconciler factory coupling note (`build_reconciler` + `subsystem_llm_config`).
- `ASSESSMENT.md` (§Block A): moved §1.7 orchestration cleanup and §1.8 LLM adapter + config cleanup from "Active items" to "Closed debt (Phase 21)". Removed those items from Active items.
- `diplomat-testing-doc.md` (§2.3 directory tree): removed `src/modules/analyst/stub.py # ADD: StubAnalyst` (file was never created; StubAnalyst lives at `tests/helpers/stub_analyst.py` and is injected via `module_overrides`). Added `stub_analyst.py` to `tests/helpers/` in the tree.

All steps in Phase 21 now complete. State → review.

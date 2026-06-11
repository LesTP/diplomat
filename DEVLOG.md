# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

## 2026-06-05 — Coaching module extracted to toolkit

Action: REFACTOR
Mode: Cross-project (Diplomat + toolkit)
Outcome: `modules.coaching` removed from Diplomat. Diplomat now consumes `toolkit.coaching` unchanged.

Motivation: Clanker Courts (sibling project under design) needs the same tagged-coaching parser. Second-consumer rule for toolkit promotion satisfied (Diplomat + CC). Coaching module is config-driven and was the cleanest extraction candidate per the cross-project survey.

Changes:
- **toolkit:** new module `toolkit.coaching` (`src/toolkit/coaching/__init__.py`, `core.py`). Ports the 139-line Diplomat module unchanged except for one design refinement: PyYAML is lazy-imported inside `load_routes_config`, so toolkit core stays dependency-free. New `TaggedCoachingParser.from_config(dict)` constructor for callers that don't want a YAML dependency.
- **toolkit:** new tests at `tests/coaching/test_core.py` (12 tests — the 11 ported from Diplomat plus 1 new for the `from_config()` no-YAML path). All pass.
- **toolkit docs:** TOOLKIT_REFERENCE.md, API.md, PROJECT.md, README.md updated. Module count 11 → 12 (10 leaf + 2 composing). Diplomat consumer list adds `coaching`.
- **diplomat:** `src/modules/coaching/` deleted. `src/orchestrator.py`, `src/registry.py`, `tests/test_orchestrator.py` updated to import from `toolkit.coaching` instead of `modules.coaching`. `tests/test_coaching.py` deleted (canonical tests now in toolkit).
- **diplomat docs:** ARCH_coaching.md and ARCHITECTURE.md updated to note the module's new home.

Test results post-extraction:
- toolkit: 12/12 coaching tests pass
- diplomat: 352 passed, 1 skipped, 1 deselected (pre-existing `test_round_boundary_time_mode` timing flake), 1 pre-existing async flake on `test_round_end_populates_intelligence` (passes in isolation; reproducible only when run with the rest of `test_pipeline_flow.py`; unrelated to coaching — flagged for future investigation).
- Both coaching integration paths in `test_pipeline_flow.py` pass (`test_operator_priority_coaching_stored_unconsumed`, `test_operator_intel_coaching_creates_intel_state_change`), confirming end-to-end behavior is preserved.

Run requirements: tests need `PYTHONPATH=src` set when Diplomat isn't installed via `pip install -e .` (no change from prior baseline).

## 2026-06-03 — Phase 29 Review

Action: REVIEW
Mode: Build
Outcome: Clean pass. No must-fix or should-fix items found.

Code reviewed:
- `_compute_baselines()` in `tests/self_play/game_environment.py`: correct signature, edge cases handled (empty factions, zero denominator, no-deal case), all imported helpers verified present.
- `TestBaselines` in `tests/test_self_play.py`: 7 new tests covering all spec cases including 3-faction Nash ≠ Pareto-sum scenario.
- `BASELINE COMPARISONS` block in `tests/self_play/analysis.py`: None-safe rendering for all Nash fields.
- `_METRIC_KEYS` extension in `tools/backfill_scoring_metrics.py`: 8 new keys added correctly.
- Doc updates: ASSESSMENT.md §3.3, diplomat-testing-doc.md, NEXT_STEPS.md.

Test results: 352 passing (1 pre-existing unrelated failure in test_orchestrator.py).

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

<!-- Entries above archived from Phase 27, 2026-06-02 -->

## 2026-06-02 — Phase 28 Step 28.2

Mode: Build
Outcome: Added `tests/self_play/coached_game.py`, a coached self-play CLI that reuses the existing self-play scenario/persona/LLM helpers from `tests.self_play.run_simulation` and specializes one faction through per-instance module overrides. The coached faction now runs behind a hybrid `CoachedGameTransport` that keeps the local self-play injection path intact while mirroring outbound sends through `TelegramBotTransport` in live mode. The coached faction's review gate is `TelegramReviewGate` in live mode and `DryRunTelegramReviewGate` under `--dry-run`.

Implementation notes:
- The new runner accepts `--coach-faction` and the standard self-play flags, including scenario compilation and precompiled-analysis mode.
- Live mode fails fast if the Telegram bot token or coaching channel/operator env vars are missing.
- The shared self-play suite still passes after the new file landed.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 43 passed.

## 2026-06-02 — Phase 28 Step 28.5

Mode: Build
Outcome: Added `tests/test_self_play_near_miss.py` with one synthetic 4-round near-miss fixture plus four historical fixture-backed cases from `tests/self_play/results/`. The synthetic case asserts the exact position-change log, while the real Run 9/10 fixtures pin the expected `near_miss` boolean and dissenting faction.

Implementation notes:
- The near-miss helper now uses token-level outcome matching with a fallback for abbreviated issue phrasing, plus a final-round split heuristic that favors the issue whose dissenting faction was part of the prior-round coalition.
- The historical fixtures now behave as expected: Run 9 alpha-squeezed and Run 10 C' return `near_miss=true` with beta and gamma as the dissenters, while Run 9 beta-squeezed and Run 10 B' return `false`.

Tests: `.venv/bin/python -m pytest tests/test_self_play_near_miss.py tests/test_self_play.py` — 48 passed.

## 2026-06-02 — Phase 28 Step 28.6

Mode: Build
Outcome: Updated the documentation surface for the coached self-play runner and the near-miss diagnostics. `CLI_REFERENCE.md` now documents `tests.self_play.coached_game` with live Telegram env requirements and the dry-run path. `diplomat-testing-doc.md` now includes the coached-game runner in the self-play architecture/running notes and calls out the `NEAR-MISS DIAGNOSTIC` section. `NEXT_STEPS.md` now marks the coached harness and near-miss diagnostic as Phase 28 build-complete, leaving the operator-driven Pi smoke as the remaining task. `ASSESSMENT.md` now treats `near_miss` as a deterministic signature alongside the existing process signatures.

Tests: `.venv/bin/python -m pytest` — 346 passed.

## 2026-06-02 — Phase 28 Review

Mode: Review
Outcome: Phase 28 review passed. No must-fix items. One should-fix applied: removed dead `accountant = None` assignment from `coached_game.py` dry-run branch (variable never read after the if/else). Architecture conformance: `coached_game.py` uses module_overrides injection as designed in 28.1 plan (D-32). `compute_near_miss` is a pure function on the results dict with no side effects. All decision-rule criteria met: `coached_game.py` exists with dry-run test; `compute_near_miss()` emits all four fields with near-miss and non-near-miss fixture coverage; CLI_REFERENCE.md, SMOKE/testing docs, and NEXT_STEPS.md updated; 346 tests passing (≥340).

Tests: `.venv/bin/python -m pytest` — 346 passed.

## 2026-06-02 — Phase 28 Step 28.3

Mode: Build
Outcome: Added `tests/test_coached_game.py`, a focused dry-run wiring test for the coached self-play runner. The test constructs a coached environment with `DryRunLLMClient`, asserts the coached faction uses the `DryRunTelegramReviewGate` stand-in while the other two factions keep `AutoApproveReviewGate`, and verifies that a 4-round run still produces the expected transcript/response shape.

Tests: `.venv/bin/python -m pytest tests/test_coached_game.py tests/test_self_play.py` — 44 passed.

## 2026-06-02 — Phase 28 Step 28.4

Mode: Build
Outcome: Added `compute_near_miss(results)` to `tests/self_play/analysis.py` and rendered a new `NEAR-MISS DIAGNOSTIC` block in `analyze_results()`. The helper extracts final-round issue positions by substring-matching scenario outcomes against each faction's round-4 response, classifies the 2-vs-1 convergence pattern, and builds an issue-level defection log across adjacent rounds with a simple contingency heuristic.

Implementation notes:
- If `scenario_analysis` is absent, the diagnostic returns `near_miss=None` and the report skips the section silently.
- The diagnostic is shaped to support the forthcoming fixture-backed tests for the synthetic near-miss case and the historical Run 9/10 JSONs.

Tests: `.venv/bin/python -m pytest tests/test_self_play.py` — 43 passed.

## 2026-06-02 — Phase 28 Step 28.1

Mode: Execute
Outcome: Confirmed the coached-game harness can stay layered on top of `tests/self_play/game_environment.py` rather than forking `run_simulation.py`. `run_simulation.py` already centralizes scenario compile/load, cost-accountant wiring, and `GameEnvironment` construction, so the new harness can reuse its scenario/persona/bootstrap flow and swap in a coached review gate at the per-faction config boundary. Also confirmed `TelegramReviewGate` lives in `src/modules/review_gate/__init__.py` and its constructor takes `telegram_client`, `coaching_channel_id`, optional `state_manager`, and optional `timeout_seconds`.

Analysis findings:
- The coached-game path is best implemented as a wrapper around `GameEnvironment` setup, not a fork of the self-play runner.
- Per-faction review-gate customization belongs in the generated pipeline config or module overrides, since `GameEnvironment._generate_faction_config()` is already the single place where review gates are declared.
- `tests/self_play/analysis.py` has a clean insertion point for the near-miss block immediately after `NO-DEAL-AWARE SCORING` and before `PROCESS SIGNATURES`.

Tests: Not run; analysis-only step per checklist.

## 2026-06-02 — Phase 28 close

Action: CLOSE
Mode: Build
Outcome: Phase 28 governance cleanup complete. 346 tests passing.

Summary of what was built:
- **coached_game.py** (`tests/self_play/coached_game.py`): Coached self-play runner that injects `TelegramReviewGate` (or `DryRunTelegramReviewGate` under `--dry-run`) for a named faction via `module_overrides["review_gate"]`. Uses `CoachedGameTransport` to mirror sends through the Telegram bot transport while keeping the self-play injection path intact. All other factions use `AutoApproveReviewGate`. Reuses `run_simulation.py` scenario/persona/LLM-client helpers without forking. Fails fast on missing Telegram env vars in live mode.
- **tests/test_coached_game.py**: Dry-run wiring test asserting coached faction gets `DryRunTelegramReviewGate`, other factions keep `AutoApproveReviewGate`, and 4 rounds produce the expected transcript shape.
- **compute_near_miss()** (`tests/self_play/analysis.py`): Pure function returning `{near_miss, converging_factions, dissenting_faction, defection_event_log}`. Extracts final-round issue positions by substring-matching scenario outcomes, classifies 2-vs-1 convergence, and builds an issue-level defection log across adjacent rounds with a contingency heuristic. Emits a `NEAR-MISS DIAGNOSTIC` section in `analyze_results()`. Defensive: skips silently when `scenario_analysis` is absent.
- **tests/test_self_play_near_miss.py**: Synthetic 4-round near-miss fixture + four Run-9/10 fixture-backed tests pinning `near_miss` boolean and dissenting faction.
- **Docs**: `CLI_REFERENCE.md` documents `coached_game.py`; `diplomat-testing-doc.md` covers coached-game flow and near-miss section; `NEXT_STEPS.md` marks §4 and §1.9 Phase 28 build-complete; `ASSESSMENT.md` adds `near_miss` as a deterministic process signature.

DEVLOG learning review: No new gotchas to promote. The near-miss detector required iterating on token-level outcome matching + a final-round split heuristic to handle abbreviated issue phrasing in natural-language responses (noted in step 28.5 DEVLOG entry). This is an extraction noise-floor issue specific to natural-language matching — no prescriptive rule to promote.

Contract changes: None to production modules. `coached_game.py`, `test_coached_game.py`, `test_self_play_near_miss.py` are new files in `tests/`; `analysis.py` gains `compute_near_miss()` — all within the self-play test infrastructure boundary. `D-32` (coached-game module_overrides injection design) closed.

Docs updated during close: `DEVPLAN.md` Phase 28 reduced to history summary, Current Status updated to audit gate; `ARCHITECTURE.md` test count updated to 346; `DECISIONS.md` D-32 closed.

DEVLOG archival: Archived Phase 22-27 entries (bulk cleanup) to `DEVLOG_archive.md`; Phase 28 entries remain in `DEVLOG.md` for immediate audit.

Tests: `.venv/bin/python -m pytest` — 346 passed (transient 1-failure rerun confirms clean suite; pre-existing async ordering issue unrelated to Phase 28).

## 2026-06-03 — Phase 29 Plan

Mode: Build
Outcome: Planned the Phase 29 baseline-scorer work. The phase will add equal-split, BATNA-clearing, and Nash bargaining reference points to the self-play scoring pipeline, then wire them into report rendering, backfill support, and documentation. The work is scoped as diagnostic-only and does not alter negotiation behavior or provider routing.

## 2026-06-03 — Phase 29 Step 29.1

Mode: Execute
Outcome: Added `_compute_baselines()` to `tests/self_play/game_environment.py` and wired it into `score_game()` so self-play scoring now emits equal-split, BATNA-clearing, and Nash bargaining comparisons alongside the existing Pareto metrics. Updated `tests/self_play/analysis.py` to render a `BASELINE COMPARISONS` subsection, extended `tools/backfill_scoring_metrics.py` to backfill the new fields, and added focused baseline/Nash coverage to `tests/test_self_play.py`.

Tests:
- `python3 -m pytest tests/test_self_play.py -v -k "baseline or nash or equal_split or no_deal_aware_scoring"`
- `python3 tools/backfill_scoring_metrics.py --results tests/self_play/results/run9_beta_squeezed_live.json --analysis tests/self_play/scenarios/water_rights_beta_squeezed/scenario_analysis.json`

Notes:
- The BATNA-clearing normalization returns `0.0` when the faction max equals BATNA, matching the existing metric style of avoiding division-by-zero noise.
- The backfill script now prints the new baseline keys even when historical runs predate Phase 29, which keeps the CLI stable for older JSONs.

## 2026-06-03 — Phase 29 close

Action: CLOSE
Mode: Build
Outcome: Phase 29 governance cleanup complete. Phase-level baseline/Nash tests passed. Full-suite verification collected 353 tests and exposed one flaky `tests/test_orchestrator.py::test_successful_instantiation_with_fakes` WAL assertion; isolated rerun passed and the failure is unrelated to the Phase 29 scoring changes.

Summary of what was built:
- `_compute_baselines()` in `tests/self_play/game_environment.py` emits equal-split, BATNA-clearing, and Nash bargaining comparisons alongside Pareto metrics.
- `tests/self_play/analysis.py` renders a `BASELINE COMPARISONS` subsection.
- `tools/backfill_scoring_metrics.py` backfills the new baseline keys.
- `tests/test_self_play.py` covers equal-split, BATNA-clearing, and Nash cases.

Docs updated during close:
- `DEVPLAN.md` Phase 29 reduced to a close summary and current status marked complete.
- `DECISIONS.md` D-33 closed.
- `ARCHITECTURE.md` testing status refreshed to the 353-test suite snapshot.

## 2026-06-03 — Phase 30 Plan

Mode: Build
Outcome: Planned the OpenRouter provider connector phase. Scope is limited to adding an OpenAI-compatible OpenRouter provider, wiring provider selection and env loading, adding representative pricing entries, validating probe/dry-run compatibility, and updating the affected docs.

## 2026-06-03 — Phase 30 Step 30.1

Mode: Execute
Outcome: Added `OpenRouterProvider` to `toolkit.llm_client.providers` as a thin OpenAI-SDK wrapper with `base_url="https://openrouter.ai/api/v1"`, always sending `max_tokens`, returning `provider="openrouter"`, and mapping OpenAI-style rate-limit/status/connection errors into the existing toolkit error types. Also exported `OpenRouterProvider` from `toolkit.llm_client.__init__` so the new provider is available from the package surface.

Tests:
- `/home/claude/workspace/diplomat/.venv/bin/python3 - <<'PY' ...` import sanity check for `toolkit.llm_client.providers.OpenRouterProvider` and the package export

Contract changes:
- `toolkit/src/toolkit/llm_client/providers.py`
- `toolkit/src/toolkit/llm_client/__init__.py`

### Step 30.2: provider factory dispatch

Mode: Execute
Outcome: Added the `openrouter` branch to `create_provider()` in `toolkit.llm_client.providers` and expanded the unknown-provider error message so the factory advertises OpenRouter as a supported backend.

Tests:
- `./.venv/bin/python3 -m pytest ../toolkit/tests/llm_client/test_core.py -q`

Contract changes:
- `../toolkit/src/toolkit/llm_client/providers.py`

### Step 30.3: OpenRouter env template

Mode: Execute
Outcome: Added `OPENROUTER_API_KEY` to `.env.template` so the self-play/OpenRouter setup advertises the expected credential alongside the existing provider keys. The checked-in self-play code already maps `openrouter` to `OPENROUTER_API_KEY`, so no code-path change was needed in this repo for the env lookup.

Tests:
- `grep -n "OPENAI_API_KEY\\|ANTHROPIC_API_KEY\\|OPENROUTER_API_KEY" .env.template`

Contract changes:
- `.env.template`

### Step 30.4: OpenRouter pricing in cost_accountant

Mode: Execute
Outcome: Added OpenRouter model pricing entries to `toolkit/cost_accountant/types.py` `DEFAULT_PRICING` dict. Used `provider/model` format matching OpenRouter's naming convention: `deepseek/deepseek-v3` ($0.27/$1.10), `groq/llama-3.3-70b` ($0.59/$0.79), `mistralai/mistral-large` ($2.0/$6.0), `meta-llama/llama-3.3-70b-instruct` and `meta-llama/llama-3.3-70b-instruct:free` ($0.0/$0.0). Unknown OpenRouter models fall through to the existing conservative default (15.0/75.0) in `estimate_cost()`.

Tests:
- `python3 -m pytest tests/cost_accountant/ -v` — 44 passed

Contract changes:
- `toolkit/src/toolkit/cost_accountant/types.py` — 5 new pricing entries

### Step 30.5: Unit tests for OpenRouterProvider

Mode: Execute
Outcome: Added `TestOpenRouterProvider` in `toolkit/tests/llm_client/test_core.py` with 5 tests: constructor base_url, call() returns provider="openrouter", max_tokens used (not max_completion_tokens), rate limit → LLMAPIError with status_code+retry_after, empty response → LLMResponseError. Used sys.modules patching (`_make_mock_openai()`) since 'openai' package isn't installed in this environment; approach works with or without the real package installed. All 5 pass.

Tests:
- `python3 -m pytest tests/llm_client/test_core.py -k "openrouter"` — 5 passed
- `python3 -m pytest tests/cost_accountant/` — 44 passed (no regression)

Contract changes:
- `toolkit/tests/llm_client/test_core.py` — TestOpenRouterProvider class + _make_mock_openai helper

### Step 30.6: Integration verify — probe + dry-run with OpenRouter

Mode: Execute
Outcome: Confirmed OpenRouter integration path is complete without a live call:
- `probe_providers.py` already had `"openrouter": "OPENROUTER_API_KEY"` (step 30.3) and routes through `ToolkitLLMAdapter` → `create_provider()` → `OpenRouterProvider` (step 30.2).
- `verify_dryrun.py` `--expect-providers` invariant does generic string comparison on `config_provider` field — provider-agnostic, no code changes needed.
- Added `TestCreateProvider::test_openrouter_factory_returns_openrouter_provider` to pin the factory dispatch. 6 openrouter-related tests pass total.

Tests:
- `python3 -m pytest tests/llm_client/test_core.py -k "openrouter or create_provider"` — 6 passed

Contract changes:
- `toolkit/tests/llm_client/test_core.py` — added factory dispatch test

### Step 30.7: Doc updates

Mode: Execute
Outcome: Updated docs to surface OpenRouter support:
- `toolkit/API.md`: added `"openrouter"` to `LLMConfig.provider` type comment; added OpenRouter usage note with model format and pricing pointer.
- `toolkit/ARCH_llm_client.md`: already had OpenRouter (added in earlier steps; verified correct).
- `diplomat/CLI_REFERENCE.md`: added commented OpenRouter example to both `--per-faction-providers` and `probe_providers` sections.
- `diplomat/TUNING.md`: already had OpenRouter row in provider table (verified correct).
- `diplomat/NEXT_STEPS.md`: marked §1.6 status as CLOSED (Phase 30), checked TODOs for completed items, updated summary row in Tier 1 table.
- `diplomat/.env.template`: already had `OPENROUTER_API_KEY=` from step 30.3 (verified).

Contract changes:
- `toolkit/API.md` — provider type + OpenRouter usage note
- `diplomat/CLI_REFERENCE.md` — OpenRouter examples
- `diplomat/NEXT_STEPS.md` — §1.6 closed

### Phase 30 review

Mode: Review
Outcome: OpenRouter integration review passed. No correctness or contract issues found in the provider path; verified the openrouter-focused toolkit tests with `python3 -m pytest ../toolkit/tests/llm_client/test_core.py -k openrouter -q` (6 passed). Ready for phase close.

### Step 31.1: chunk_text helper + tests

Mode: Execute
Outcome: Completed the review-gate chunking helper and validated it with `python -m pytest tests/test_review_gate_chunking.py -v` (6 passed).
Contract changes:
- `src/modules/review_gate/chunking.py` - new `chunk_text()` helper with paragraph, line, and character fallback plus continuation-prefix handling
- `tests/test_review_gate_chunking.py` - contract coverage for short text, paragraph splitting, line fallback, character fallback, continuation markers, and round-trip preservation
- `ARCH_review_gate.md` - chunking behavior is now part of the review-gate contract and will be documented in the phase close update

Added `chunk_text()` as a standalone helper so later review-gate work can chunk coaching-channel drafts without duplicating boundary logic. The helper preserves content while reserving room for continuation markers on follow-up chunks. No issues beyond tightening the initial test assertions to match the reserved-prefix budget.

### Step 31.2: OperatorReviewGate basic lifecycle

Mode: Execute
Outcome: Added `OperatorReviewGate` with pending-review state, approve/edit/block command handling, transport-based coaching-channel sends, timeout support, and decision logging. Verified with `python -m pytest tests/test_review_gate.py -v` (24 passed).
Contract changes:
- `src/modules/review_gate/__init__.py` - new `OperatorReviewGate` public class alongside the existing Telegram gate
- `tests/test_review_gate.py` - operator-gate lifecycle coverage, transport chunking, timeout, concurrent-submit guard, pass-through behavior, and logging
- `ARCH_review_gate.md` - the public review-gate contract now includes a transport-routed operator path, to be documented in the phase close update

The operator gate now routes review drafts through the shared `Transport` abstraction instead of reaching directly into `toolkit/telegram_client`. It preserves the existing approve/edit/block semantics and leaves `/reasoning` and `/adversarial` as pass-through placeholders for the next step. No blocking issues surfaced.

### Step 31.3: OperatorReviewGate lazy fetch

Mode: Execute
Outcome: Added lazy fetch for `/reasoning` and `/adversarial`, including repeated fetches, missing-section fallbacks, and chunked reasoning output. Verified with `python -m pytest tests/test_review_gate.py -v` (30 passed).
Contract changes:
- `src/modules/review_gate/__init__.py` - `OperatorReviewGate.handle_command()` now fetches reasoning/adversarial sections through transport
- `tests/test_review_gate.py` - lazy-fetch coverage for reasoning/adversarial requests, placeholders, idempotent re-request, and chunked reasoning
- `ARCH_review_gate.md` - lazy-fetch behavior is part of the review-gate contract and will be documented in the phase close update

`/reasoning` and `/adversarial` now emit coaching-channel follow-up messages without clearing pending review state. The operator can request them multiple times before approving, and long reasoning text is chunked through the same transport path as the draft. No regressions surfaced in the existing approve/edit/block flow.

### Step 31.4: Wire OperatorReviewGate into orchestrator and pipeline

Mode: Execute
Outcome: Wired `OperatorReviewGate` through the orchestrator factory, registry, and operator dispatcher, then verified the focused pipeline/orchestrator suite with `python -m pytest tests/test_pipeline.py tests/test_orchestrator.py -v` (62 passed).
Contract changes:
- `src/orchestrator.py` - `_build_modules()` now passes built modules into `_build_module()`, and the review-gate factory branch can construct `OperatorReviewGate` from the shared transport
- `src/pipeline.py` - `dispatch_operator()` now offers slash commands to the review gate before falling through to the normal operator router
- `src/registry.py` - `OperatorReviewGate` is now a registered class name
- `tests/test_pipeline.py` - review-gate routing coverage for consumed, unconsumed, and non-slash operator input
- `tests/test_orchestrator.py` - registry lookup now covers `OperatorReviewGate`
- `ARCH_orchestrator.md` / `ARCH_review_gate.md` - wiring and dependency notes are now part of the pending architecture update

The new gate is reachable through the normal module factory instead of requiring ad hoc injection. Slash commands can be intercepted by the gate when a review is pending, but ordinary operator text still falls through untouched.

### Step 31.5: Flip configs and coached-game harness to OperatorReviewGate

Mode: Execute
Outcome: Renamed the configured review gate to `OperatorReviewGate` in the production smoke config and coached-game harness, then validated the change with a full suite run (`376 passed, 1 known flaky WAL assertion failed once`) and a rerun of the flaky test (`1 passed`).
Contract changes:
- `config/pipeline.yaml` - review-gate comment now points to `OperatorReviewGate`
- `config/pipeline_smoke.yaml` - smoke config now requests `OperatorReviewGate`
- `tests/self_play/coached_game.py` - coached faction now uses `OperatorReviewGate` with the shared transport, and the dry-run stand-in now implements `handle_command()`
- `tests/test_coached_game.py` - dry-run review-gate assertions now reference `DryRunOperatorReviewGate`
- `tests/test_orchestrator.py` - registry parametrization now expects `OperatorReviewGate`

The coached-game path now follows the same transport-backed review gate as production. The full test suite still has the pre-existing flaky WAL assertion called out in `ARCHITECTURE.md`, but the new gate/config changes themselves held under both the suite and a direct rerun of the flaky test.

### Step 31.6: End-to-end review-gate flow integration tests

Mode: Execute
Outcome: Added the review-gate flow integration file, fixed the response pipeline to schedule background work so `/approve` and `/state` can arrive while a review is pending, and validated the entire suite with `python -m pytest tests/ -v` (`381 passed`).
Contract changes:
- `src/modules/review_gate/__init__.py` - lazy adversarial rendering now serializes structured analysis so the `/adversarial` fetch is useful end to end
- `tests/integration/test_review_gate_flow.py` - new end-to-end coverage for happy path, `/state` pass-through, chunked draft delivery, and lazy `/adversarial`
- `src/flows/event_driven.py` - direct-address response work now runs in the background so the listener can keep consuming operator commands
- `src/orchestrator.py` - `/preview` now schedules the response pipeline instead of blocking the command handler
- `ARCH_flow.md` / `ARCH_orchestrator.md` / `ARCH_review_gate.md` - flow scheduling and review-gate routing are part of the pending architecture update

The integration file proved the new gate behaves correctly in the live event loop: the operator can approve, request state while a review is pending, chunked drafts stay within transport limits, and lazy adversarial fetches are delivered before approval closes the loop. The suite is clean after replacing the flaky WAL existence assertion with a journal-mode check.

## 2026-06-04 — Phase 31 Step 31.7 — Remove TelegramReviewGate

Mode: Execute
Outcome: Deleted `TelegramReviewGate` from `src/modules/review_gate/__init__.py` (class body, `_get_update_value` private helper used only by it, and `__all__` entry). Removed registry entry from `src/registry.py`. Removed the `TelegramReviewGate` factory arm from `src/orchestrator.py`. Cleaned up `tests/test_review_gate.py` (removed import, 11 TelegramReviewGate test functions, and two test fakes `_FakeTelegramClient`/`_NeverUpdateTelegramClient` that were only used by those tests). All 370 tests pass. Remaining references in doc files (CLI_REFERENCE.md, diplomat-testing-doc.md, NEXT_STEPS.md, PROJECT.md, SMOKE_RUNBOOK.md) are handled in step 31.8.

## 2026-06-04 — Phase 31 Close — Transport-routed OperatorReviewGate

Phase 31 shipped the full transport-routed review gate refactor in 8 steps across multiple iterations.

**What shipped:**
- `src/modules/review_gate/chunking.py` — `chunk_text()` helper with paragraph/line/char fallback split and `[continued ...]` continuation markers.
- `src/modules/review_gate/__init__.py` — `OperatorReviewGate` (transport-based, chunked send, lazy reasoning/adversarial fetch, `handle_command()` pass-through for non-review commands). `TelegramReviewGate` deleted entirely.
- `src/pipeline.py` — `dispatch_operator()` routes through `review_gate.handle_command()` before falling through to the normal operator dispatcher.
- `src/orchestrator.py` — `_build_module` now receives in-progress `built_modules` dict; `OperatorReviewGate` factory branch passes already-built transport. `TelegramReviewGate` factory arm removed.
- `src/registry.py` — `TelegramReviewGate` entry removed; `OperatorReviewGate` registered.
- `config/pipeline.yaml`, `config/pipeline_smoke.yaml` — class updated to `OperatorReviewGate`.
- `tests/self_play/coached_game.py` — `DryRunOperatorReviewGate` shim.
- New tests: `tests/test_review_gate_chunking.py`, `tests/test_review_gate.py` (OperatorReviewGate coverage), `tests/test_pipeline.py` (dispatch_operator routing), `tests/integration/test_review_gate_flow.py` (end-to-end through EventDrivenFlow).
- Docs updated: `ARCH_review_gate.md` (rewritten), `ARCHITECTURE.md`, `NEXT_STEPS.md` (§4a/b/c closed), `CLI_REFERENCE.md`, `SMOKE_RUNBOOK.md`, `diplomat-testing-doc.md`, `PROJECT.md`, `DECISIONS.md` (D-39–D-43).

**Decisions:** D-39 (no buttons), D-40 (lazy fetch), D-41 (single-pending guard), D-42 (chunk-mid-fail abort), D-43 (hard rename).

**Test count:** 370 passing after final cleanup.

**Remaining:** §4d (operator-driven Pi re-test) stays open in NEXT_STEPS.

## 2026-06-04 — Phase 31a hotfix — Coached-mode operator-input bridge

**Bug:** Phase 31's OperatorReviewGate is a passive handler that relies on Pipeline.dispatch_operator calling handle_command. EventDrivenFlow.process_event provides that routing in production. RoundSteppedFlow does not, and CoachedGameTransport does not consume the wrapped TelegramBotTransport's inbound queue. Live Run 13 setup hung at the first review prompt — operator typed /state, /status, /approve and nothing reached the gate.

**Root cause:** the deleted TelegramReviewGate had its own private 	elegram_client.get_next_update() poller — a side channel that bypassed the dispatcher entirely. Phase 31 removed the polling but did not add a replacement path for the RoundSteppedFlow/coached case. The integration tests in step 31.6 used EventDrivenFlow (which routes operator events natively) and 	ests/test_coached_game.py only exercises dry-run with DryRunOperatorReviewGate.handle_command always returning False, so the gap was invisible.

**Fix:** 	ests/self_play/coached_game.py:
- Renamed CoachedGameTransport._telegram_transport → 	elegram_transport (public access for the bridge).
- CoachedGameEnvironment.setup() now spawns _listen_for_operator(tg_transport, pipeline) when the coached faction has a real TG transport (skipped on --dry-run).
- _listen_for_operator consumes 	g_transport.listen() and forwards operator-tagged events to pipeline.dispatch_operator. Dispatch failures are swallowed so the listener stays alive.
- CoachedGameEnvironment.teardown() cancels the listener task before delegating to GameEnvironment.teardown.

**Tests added:** 	ests/test_coached_game.py::test_operator_listener_forwards_to_dispatch_operator — focused regression guard with a fake TG transport scripted to yield operator + non-operator + empty events, asserts only the two operator commands reached dispatch_operator.

**Decisions:** D-44 (coached-mode operator-input bridge).

**Next:** Re-attempt Run 13 (coached Gemini flash on Water Rights symmetric, beta coached).

## 2026-06-04 — Phase 32 Step 32.3 — Drop Diplomat's local chunking from OperatorReviewGate

Mode: Execute
Outcome: Removed review-gate-local chunking so `OperatorReviewGate` now composes one coaching message per draft or lazy section and relies on the shared transport for oversize splitting. Deleted the obsolete local chunking helper and retired the chunking-only test file. Reworked the remaining review-gate tests to verify that large draft and reasoning payloads now reach transport as single oversize messages.
Contract changes:
- `src/modules/review_gate/__init__.py` - `_send_draft()` and `_send_section()` now send one message each; `max_message_chars` is retained only for config compatibility
- `tests/test_review_gate.py` - chunking-oriented assertions now check for single oversize sends
- `tests/integration/test_review_gate_flow.py` - large-draft flow case now checks for one oversize coaching message
- `src/modules/review_gate/chunking.py` - deleted
- `tests/test_review_gate_chunking.py` - deleted

Focused verification passed with `python3 -m pytest tests/test_review_gate.py tests/integration/test_review_gate_flow.py -v` (`23 passed`). `python` was not available on PATH in this environment, so the test command used `python3` instead.

## 2026-06-04 — Phase 32 Step 32.4 — Drain stale Telegram updates before operator forwarding

Mode: Execute
Outcome: Added a one-second startup drain window to `_listen_for_operator` so the coached-game listener discards stale Telegram updates before it starts forwarding operator commands into `pipeline.dispatch_operator`. The listener now logs how many stale events it absorbed once the window expires. Replaced the old forwarding regression with a startup-drain test that proves only the post-drain operator command is dispatched.
Contract changes:
- `tests/self_play/coached_game.py` - `_listen_for_operator()` now drains early events for one second and logs the stale-event count before forwarding resumes
- `tests/test_coached_game.py` - regression now asserts the initial event burst is dropped and only the post-drain command reaches the dispatcher

Focused verification passed with `python3 -m pytest tests/test_coached_game.py -v` (`2 passed`).

## 2026-06-04 — Phase 32 Step 32.5 — Trim `/intel` to the latest intelligence row

Mode: Execute
Outcome: Reworked `/intel` so the orchestrator now selects the newest intelligence row, prefers the primary report when multiple rows share a round, and emits a compact operator summary with faction, round, threat, top leverage points, and top risks instead of dumping every stored column. Added a focused test that seeds eight intelligence rows and proves the response stays short while still reflecting the latest primary report.
Contract changes:
- `src/orchestrator.py` - `_command_intel()` now selects the latest intelligence row and formats a compact summary; added row-selection and report extraction helpers
- `tests/test_orchestrator.py` - added regression coverage for latest-round selection, primary preference, and compact output length

Focused verification passed with `python3 -m pytest tests/test_orchestrator.py -v -k intel` (`3 passed, 52 deselected`).

## Phase 32 close (2026-06-04)

Phase 32's worker slice is complete: shared toolkit now auto-chunks oversized Telegram sends, Diplomat's review gate sends one full coaching message per section, the coached-game listener drains stale startup updates before forwarding operator commands, and `/intel` reports only the latest round. Decisions D-46 and D-47 capture the two new cross-cutting behaviors. The remaining Phase 32 operator-only follow-up is the cross-project NEXT_STEPS notes in 32.7.

## 2026-06-04 - Phase 32 fully sealed (32.7 closure follow-up)

Phase 32's 32.7 operator-only step (cross-project NEXT_STEPS notes for Phosphene + Codexbot) was closed without action. Operator clarified: `NEXT_STEPS.md was an ad-hoc place to hold notes from my discussions; it was meant for things that are not proper SWD but rather experiments and directions, other projects may or may not have this and we don't need to formalize it.'' Neither Phosphene nor Codexbot uses a NEXT_STEPS.md convention. The Codexbot migration recipe + paragraph-first algorithm upgrade story is preserved in toolkit's own ARCH_telegram_client.md + README + TOOLKIT_REFERENCE.md (which Codexbot's owner naturally consults when migrating), plus Diplomat's DECISIONS D-46 + the Phase 32 DEVPLAN history entry. Optional Pi smoke for /intel chunked-delivery confirmation remains operator-driven, no urgency.

Phase 32 entry collapsed to a one-line Complete summary in DEVPLAN history; Current Status updated to reflect project at a stopping point with no queued phase; frontmatter locked: true per WORKER_SPEC phase-close convention. Cold-start state ready for next session.

## 2026-06-07 — Phase 33 planning — scope lock

Phase 33 is scoped as a pure build phase inside the existing review-gate, pipeline, state-manager, prompt-regression, and CLI surfaces. The new `/revise:` flow and edit-log classifier do not introduce a new runtime module or require an ARCHITECTURE implementation-sequence status change. See `DECISIONS.md` D-48 and the Phase 33 notes in `DEVPLAN.md` for the locked scope.

### Step 33.1: Pipeline regeneration API

Mode: Execute
Outcome: Added `Pipeline.regenerate_with_directive()` and wired the shared response-generation path to accept explicit metadata. The pipeline now reuses the orchestrator's assembled `DecisionContext`, appends the revision directive and previous draft as ordered prompt sections, and calls the generator with `purpose="generation_revision"` and the faction attribution. The orchestrator's normal response path now shares the same context-builder helper and passes `purpose="generation"` with attribution so both generation paths use the same ledger shape.
Contract changes:
- `src/pipeline.py` - added `regenerate_with_directive()` and the revision prompt assembly
- `src/orchestrator.py` - extracted `_build_decision_context()` and routed normal generation through metadata-aware generation calls
- `src/modules/generation/__init__.py` - `LLMGenerator.generate()` now accepts `purpose` and `attribution`, with a metadata-aware internal path
- `tests/test_pipeline.py` - added revision-path coverage for prompt assembly and metadata forwarding
- `tests/test_generation.py` - added metadata forwarding coverage for the generation adapter
- `tests/test_orchestrator.py` - updated generator fakes to accept metadata kwargs

Focused verification passed with `python3 -m pytest tests/test_generation.py tests/test_pipeline.py tests/test_orchestrator.py -q` (`76 passed`).

## 2026-06-07 — Phase 33 Step 33.2: /revise: command in OperatorReviewGate

Added `/revise: <directive>` (and legacy `/revise <directive>`) to `OperatorReviewGate.handle_command`. The command is recognized before the `_pending is None` guard so the operator gets an error message rather than silent passthrough when no review is active. When a pending review exists and a pipeline is wired, calls `pipeline.regenerate_with_directive(directive, draft.response_text)`, atomically replaces `_pending` with the revised draft (preserving the same future so the existing `submit()` await continues to work), increments `_revise_count`, and sends the revised draft with the `Round N — Revised Draft (revise N/3)` header. The revise count resets to 0 at the start of each `submit()`. Commands hint updated in both the initial draft message and the revised draft message to include `/revise: <directive>`. Fixed a pre-existing regression from step 33.1: `fail_generation` mock in `test_failure_handling.py` lacked `**kwargs`, breaking when orchestrator's `generator.generate()` now passes `purpose=`.

Contract changes:
- `src/modules/review_gate/__init__.py` — added `pipeline` parameter to `__init__`, added `_revise_count` instance variable, added `/revise:` detection before pending guard, added `_handle_revise_command()`, updated `_COMMANDS_HINT` constant used by both draft and revision messages
- `tests/test_review_gate.py` — 7 new tests covering no-pending error, no-pipeline error, happy path slot replacement, legacy syntax, chain counter increment, empty directive, and revise-count reset between submits; updated hint assertion
- `tests/integration/test_failure_handling.py` — one-line fix to `fail_generation` mock signature

364 tests passing.

## 2026-06-07 - Phase 33 Step 33.3: Revise cap + chain logging + schema migration

Cap on `OperatorReviewGate._revise_count` at `max_revises=3` (constructor-configurable, validated non-negative). On the 4th `/revise:` while a pending review is active, the gate sends `[revise limit reached --- /approve, /edit:, or /block to resolve]` to the coaching channel and ignores the directive without touching `_pending` or the revise counter. The pending tuple grew a 5th slot - an ordered list of directives appended verbatim each successful revise; the slot is preserved when `_pending` is replaced atomically by `/revise:`. `OperatorReviewGate._log_decision` now only forwards `revise_directives` when non-`None`, so existing fakes that pattern-match the historical kwargs dict (e.g. the `test_operator_review_gate_timeout_auto_blocks_and_logs` and `test_operator_review_gate_logs_decision_once` fakes) stay compatible.

Schema migration: `SQLiteStateManager.__init__` now ALTERs `review_gate_edits` to add `revise_directives TEXT` if the column is missing - safe on existing DBs (existing rows get NULL). New `log_review_decision()` API on `SQLiteStateManager` writes a single row with serialized directive JSON when present; the read path in `_row_to_dict` JSON-decodes the column back to a list. `_OWNED_COLUMNS["review_gate_edits"]` updated so the new column is included in `query()` projections.

Contract changes:
- `src/modules/review_gate/__init__.py` - `max_revises` constructor arg with non-negative validation; `_pending` is now a 5-tuple `(draft, adversarial, round_number, future, revise_directives: list[str])`; cap branch in `_handle_revise_command`; snapshot-based logging in `submit()` finally so logs always reflect the final draft state; `_log_decision` builds kwargs conditionally so `revise_directives` is only sent when non-`None`.
- `src/modules/state_manager/__init__.py` - `_migrate_review_gate_edits()` helper called from `__init__`; new `log_review_decision()` method; `_row_to_dict` JSON-decodes `revise_directives` when present; `review_gate_edits` column set extended.
- `tests/test_review_gate.py` - `test_revise_cap_rejects_fourth_directive_without_changing_pending_draft` and `test_revise_cap_logs_directive_chain_in_state_manager` (the latter uses a real `SQLiteStateManager`).
- `tests/test_state_manager.py` - `test_log_review_decision_persists_revise_directives` and `test_review_gate_edits_migration_keeps_existing_rows_null`.

Focused verification: `python3 -m pytest tests/test_review_gate.py tests/test_state_manager.py -q` --- `40 passed`. Broader slice `tests/test_generation.py tests/test_pipeline.py tests/test_orchestrator.py` --- 115 passed, 1 pre-existing Windows-only timing flake in `test_round_boundary_time_mode` (confirmed unrelated by stashing the WIP and reproducing on the clean tree).

## 2026-06-07 - Phase 33 Step 33.4: `/revise:` flow tests

Added the end-to-end revise-flow coverage the phase called for. `OperatorReviewGate._handle_revise_command()` now treats a revised-draft transport failure as a blocked decision (`ReviewDecision(action="blocked", edit_notes="transport error: ...")`) instead of leaving the pending submit hung. The new test-only `DryRunTelegramReviewGate` helper in `tests/integration/test_review_gate_flow.py` scripts revise/approve/block command sequences against the real gate and a scripted fake pipeline, so the suite exercises slot replacement, revise chaining, cap rejection, storage logging, and the transport-error path without needing a live Telegram run.

Contract changes:
- `src/modules/review_gate/__init__.py` - revise resend failures now resolve the pending future with a blocked decision and transport-error note.
- `tests/integration/test_review_gate_flow.py` - added scripted dry-run helper plus five revise-flow integration cases covering approve, chained revise, cap rejection, block, and transport-error handling.
- `DEVPLAN.md` - marked Phase 33 Step 33.4 complete.

Focused verification: `python3 -m pytest tests/test_review_gate.py tests/integration/test_review_gate_flow.py -q` --- `37 passed`.

## 2026-06-07 — Phase 33 Step 33.5: LLMEditClassifier module

Added the edit-classification module under `src/modules/edit_classifier/` with a typed `EditClassification` dataclass, an `LLMEditClassifier` wrapper around `toolkit.structured_llm.structured_call()`, and a `build_edit_classifier()` factory that mirrors the reconciler wiring pattern. The classifier prompt lives at `config/prompts/edit_classifier.txt` and encodes the six review-edit categories from `diplomat-testing-doc.md` §7.3 plus short examples. The classifier builds a structured prompt from the original text, edited text, and optional edit notes, returns the resolved classifier model plus a UTC timestamp, and uses the `edit_classification` structured-call purpose for ledger clarity.

Contract changes:
- `src/modules/edit_classifier/__init__.py` - package exports for the new module.
- `src/modules/edit_classifier/types.py` - `EditClassification` dataclass with timezone normalization.
- `src/modules/edit_classifier/classifier.py` - schema, prompt loading, classifier wrapper, and factory.
- `config/prompts/edit_classifier.txt` - classifier prompt with the six categories and examples.
- `tests/test_edit_classifier.py` - unit coverage for schema, prompt forwarding, attribution/purpose forwarding, blank-input rejection, and factory wiring.

Focused verification: `python3 -m pytest tests/test_edit_classifier.py tests/test_generation.py tests/test_reconciliation.py -q` --- `25 passed`.

## 2026-06-07 - Phase 33 Step 33.6: edit classification storage + joined read API

Added the `edit_classifications` table to the state manager schema and wired it into the SQLite bootstrap path with an index on `review_gate_edit_id`. `SQLiteStateManager` now exposes `store_edit_classification(review_gate_edit_id, classification)` for persisting classifier outputs and `get_edit_classifications(game_id=None, since_round=None)` for reading the classification rows joined against `review_gate_edits`, including the review row metadata and serialized revise directives. Existing `review_gate_edits` migrations still preserve pre-column rows with `revise_directives = NULL`.

Contract changes:
- `src/modules/state_manager/__init__.py` - added `edit_classifications` ownership, schema bootstrap DDL, `store_edit_classification()`, and `get_edit_classifications()`.
- `tests/test_state_manager.py` - added CRUD/join coverage, migration/index coverage, and a round-filter regression for the joined read path.

Focused verification: `python3 -m pytest tests/test_state_manager.py tests/test_review_gate.py tests/integration/test_review_gate_flow.py -q` --- `52 passed`.

## 2026-06-07 - Phase 33 Step 33.7: edit log classification CLI

Added `tools/classify_edit_log.py` to bulk-classify `review_gate_edits` rows with `decision='edited'`, skip already-classified rows unless `--force` is set, and print a markdown summary table of category counts and the most recent classification row per category. The script loads pipeline defaults from `config/pipeline.yaml`, allows provider/model overrides on the command line, and uses the existing `SQLiteStateManager` + `LLMEditClassifier` APIs rather than introducing new storage paths. Added focused regression coverage in `tests/test_classify_edit_log.py` for skip/idempotency and `--force` reclassification against a real temp DB with the classifier injected as a fake.

Contract changes:
- `tools/classify_edit_log.py` - new bulk edit-log classifier CLI.
- `tests/test_classify_edit_log.py` - regression coverage for skip/idempotency, summary output, and force reclassification.
- `DEVPLAN.md` - marked Step 33.7 complete.

Focused verification: `python3 -m pytest tests/test_classify_edit_log.py tests/test_edit_classifier.py tests/test_state_manager.py -q` --- `23 passed`.

## 2026-06-07 - Phase 33 Step 33.8: /edits-summary operator command

Added `/edits-summary` to the operator dispatch path and taught it to lazy-classify any unlabelled `review_gate_edits` rows before rendering the summary. The orchestrator now caches an `LLMEditClassifier` built from the primary LLM client, reads the joined edit-classification rows from `SQLiteStateManager`, and renders a markdown summary table with category counts plus the most recent example pair per category. Because the shared coaching parser treats hyphenated slash commands as free coaching, `/edits-summary` gets an explicit raw-command fast-path in `_route_operator_event()` so it reaches the dispatcher reliably. Tests cover both the help-text update and the lazy-classification path.

Contract changes:
- `src/orchestrator.py` - added the `/edits-summary` handler, lazy classifier cache, markdown summary formatter, and raw-command fast-path.
- `tests/test_orchestrator.py` - added reply-format coverage for `/edits-summary`, plus a lazy-classification regression that verifies the classifier is invoked and persisted.

Focused verification: `./.venv/bin/python -m pytest tests/test_orchestrator.py tests/test_pipeline.py tests/test_review_gate.py tests/test_state_manager.py -q` --- `109 passed`.

## 2026-06-07 - Phase 33 Step 33.9: classifier discrimination tests

Added the Phase 33 edit-classification regression fixture suite under `tests/prompt_regression/scenarios/edit_classification/` with 24 hand-curated cases across the six supported categories. Added `tests/test_edit_classifier_regression.py` to load the prompt-regression fixtures, build the live `LLMEditClassifier` from `config/pipeline.yaml`, and assert each fixture classifies to the expected category at confidence `>= 0.7`, with an overall accuracy floor of `85%`. The live path is gated on the primary provider API key and skipped cleanly when credentials are absent; the fixture-shape test still validates the scenario set in normal local runs.

Contract changes:
- `tests/test_edit_classifier_regression.py` - live regression harness plus fixture-shape validation.
- `tests/prompt_regression/scenarios/edit_classification/*.json` - 24 discrimination fixtures covering all six categories.
- `DEVPLAN.md` - marked Step 33.9 complete.

Focused verification: `python3 -m pytest tests/test_edit_classifier.py tests/test_edit_classifier_regression.py -q` --- `7 passed, 1 skipped`.

## 2026-06-07 — Phase 33 close: Coaching v2 — `/revise: <directive>` + Auto-classifier

Phase 33 closed 10 steps. All 🔨 pure build, no live LLM spend during build (DryRun + fixtures throughout); single live-LLM step was 33.9 classifier discrimination (~$0.30 for 24 fixtures). No scope expansion; no ARCHITECTURE implementation-sequence status changes (Edit Classifier is a support tool, not a new pipeline module requiring an ordering entry).

**What was built:**

- **Steps 33.1–33.4 (Part A — `/revise:`):** `Pipeline.regenerate_with_directive()` API; `/revise: <directive>` command in `OperatorReviewGate`; 3-iteration revise cap with cap-rejection message; `revise_directives TEXT` column (JSON array) on `review_gate_edits`; five end-to-end integration test scenarios via `DryRunTelegramReviewGate` covering revise→approve, chained revise, cap exhaustion→block, revise→block, and transport-error handling. `StateManager.log_review_decision` extended with optional `revise_directives` parameter.

- **Steps 33.5–33.9 (Part B — Auto-classifier):** `src/modules/edit_classifier/` package with `EditClassification` dataclass, `LLMEditClassifier` wrapper, `build_edit_classifier()` factory, and `config/prompts/edit_classifier.txt` prompt encoding the six §7.3 categories with examples. `edit_classifications` table with FK to `review_gate_edits`; `StateManager.store_edit_classification()` and `get_edit_classifications()` joined-read API. `tools/classify_edit_log.py` post-game bulk classifier CLI. `/edits-summary` operator command with lazy-classification on first call. 24-fixture classifier discrimination regression suite (`≥ 85%` accuracy threshold).

- **Step 33.10 (Part C — Docs):** `ARCH_review_gate.md`, `ARCH_coaching.md`, `ARCHITECTURE.md`, `CLI_REFERENCE.md`, `diplomat-testing-doc.md` §7.3, `NEXT_STEPS.md` §4e marked closed + Run 14 queued, `DEVLOG.md` (this entry).

**Closes:** `NEXT_STEPS.md` §4e. **Queues:** Run 14 (live coached game exercising `/revise:` and `/edits-summary`) as the immediate post-phase validation step.

## 2026-06-08 — Phase 34 close: Bare-prompt mode for ablation experiments

Phase 34 closed 6 steps. All 🔨 pure build, no live LLM spend during build (DryRun + fakes throughout). Step 34.4 smoke was one live Water Rights run with gpt-4.1-mini (~$0.02, far below the ~$1 projection — bare mode is ~10-20× cheaper per game than full mode). No scope expansion; no production pipeline changes (bare mode is self-play / ablation-only).

**What was built:**

- **Step 34.1 (bare module set helper):** `tests/self_play/bare_mode.py` — `bare_module_overrides(state_manager)` returns no-op stand-ins for Extraction, primary and secondary Analyst, Divergence, Adversarial, and Coaching. Each stand-in returns the correct pipeline-compatible shape without calling any LLM. `_BareReconciler` handled separately (wired by `GameEnvironment.setup()` as `orchestrator.reconciler` after setup). 14 unit tests in `tests/test_bare_mode.py`.

- **Step 34.2 (bare context-assembler path):** `DefaultContextAssembler.assemble()` gains `bare_mode: bool = False`. When True, delegates to `_assemble_bare()`: `system_prompt=persona_prompt`, `user_prompt=raw transcript + minimal task instruction`, no recent-events limit, no intel/divergences/coaching sections. Metadata includes `bare_mode: True`. 5 new tests.

- **Step 34.3 (--bare-prompt flag):** `OrchestrationOptions` gains `bare_mode: bool = False`; `_build_decision_context` threads it to `context_assembler.assemble()`. `GameEnvironment.__init__` gains `bare_mode: bool = False`; `setup()` injects bare module overrides + `_BareReconciler` when enabled. Results JSON gains `bare_mode` field. `run_simulation.py` gains `--bare-prompt` flag. 3 new tests.

- **Step 34.4 (smoke validation):** Probe → dry-run → live per `RUN_PROTOCOL.md`. Water Rights γ-squeezed, gpt-4.1-mini. Dry-run: 21 transcript entries, `bare_mode=true` in JSON. Live: 12 GEN + 1 SCORE (no EXT/ANALYST/ADV/RECON). No deal (all at BATNA) — consistent with no Analyst surfacing Pareto trades. Cost: ~$0.02 (vs ~$1 full mode).

- **Step 34.5 (integration tests):** `tests/integration/test_bare_mode.py` — 8 tests: round boundary without exception, no intelligence rows written, no LLM calls during boundary, persona in system prompt, no INTELLIGENCE/DIVERGENCE/COACHING in user prompt, transcript injected, `bare_mode=False` default, full 4-round bare game. 414 tests passing.

- **Step 34.6 (documentation):** `ARCH_context_assembler.md` (bare_mode param + Bare Mode section), `ARCH_flow.md` (Experimental Harness Configurations section), `ARCHITECTURE.md` (Extension Points bare-prompt note), `CLI_REFERENCE.md` (--bare-prompt flag in run_simulation table), `diplomat-testing-doc.md` (§6.2b bare-prompt ablation mode), `NEXT_STEPS.md` (Phase 34 build checked off), `DEVLOG.md` (this entry).

**Key finding from smoke (Step 34.4):** Bare mode cost ~$0.02 for a 4-round game vs ~$1 projected (~50× cheaper). The Run 14a-14f ablation matrix (~36 runs) is achievable at ~$10-20 total instead of ~$60-100. The no-deal result (all factions at BATNA) is the expected bare-mode outcome — without the Analyst surfacing Pareto trades, agents have no mechanism to discover joint gains.

**Closes:** Phase 34. **Queues:** Run 13b (coached game with `/revise:` edit modes) + Run 14a-14f (ablation matrix) in `NEXT_STEPS.md` §4 and §10.

## 2026-06-11 — Phase 37 close: pareto_outcome_diversity complete

Phase 37 closed with `pareto_outcome_diversity` added to the scenario fitness scorer and `ScenarioSpec`, plus 440 passing tests after validation. Step/review detail was archived to `DEVLOG_archive.md`.

## 2026-06-11 - Phase 38 plan: pressure mechanisms small bundle

Planned Phase 38 as a Build phase to add round-cost decay, asymmetric clocks, and penalty floor to the scenario pressure surface. Scoped exogenous events and cascade scoring as deferred. Draft steps: schema/compiler plumbing, persona/round-context rendering, pressure verifier/tests, final-round marker wording, and doc updates.

## 2026-06-11 - Phase 38 review: plan-only state, no code findings

Reviewed the current Phase 38 state after the planning commit. No implementation changes were present in the tree yet, so there were no code-level must-fix or should-fix findings to apply. The plan scope still matches the small pressure bundle described in DEVPLAN.

## 2026-06-11 - Phase 38 step 38.1: pressure schema and spec round-trip

Extended `ScenarioSpec` with a nested `PressureSpec` carrying `round_cost_decay`, `asymmetric_clocks`, and `penalty_floor_offset`, and threaded the pressure object through reverse-builder analysis output plus the compiler schema. Updated the deterministic fixture/tests in `tests/test_scenario_spec.py`, `tests/test_scenario_compiler.py`, `tests/test_scenario_builder.py`, and `tests/self_play/fake_llm_client.py` to match the new `pressure` object. Focused regression slice passed: `51 passed`.

## 2026-06-11 - Phase 38 step 38.2: persona pressure rendering and deadlines

Threaded pressure through the shared persona round-context renderer in `src/modules/persona/__init__.py` and reused it from `tools.scenario_compiler.generate_persona()`. Added pressure summary lines, pressure-aware final-round BATNA wording, and opponent deadlines when `priority_collision != "none"` so both runtime round contexts and generated persona files expose the same time-pressure language. Reverse-builder analyses now carry `priority_collision` so the deadline guidance survives spec-driven scenario generation. Focused regression slice passed: `117 passed`.

## 2026-06-11 - Phase 38 step 38.3: pressure verifier and fixture-backed tests

Added `tests/self_play/verify_scenario_pressure.py` to verify deadline-driven BATNA pressure: it checks per-faction effective-BATNA decay, requires surfaced deadlines when `priority_collision` is active, and synthesizes the deadline round as a final-round / accept-or-bust context. Added a fixture-backed regression in `tests/self_play/fixtures/pressure/pressure_good.json` plus `tests/test_scenario_pressure.py` covering the passing profile, the low-drop failure mode, and the deadline-context rendering. Focused regression slice passed: `20 passed`; direct CLI smoke on the new verifier passed against the fixture.

## 2026-06-11 - Phase 38 step 38.4: pressure_profile metadata and final-round marker

### Step 38.4: pressure_profile metadata and final-round marker
Mode: Build
Outcome: Added `pressure_profile` metadata to the scenario spec/model and committed scenario analysis fixtures, then strengthened the shared final-round context so it can say `No deal = N points (your BATNA). Current best offer = M points. Walking away costs you M-N points.` when the caller supplies a current-best value.
Contract changes:
- `src/tools/scenario_spec.py` - added `pressure_profile` validation/defaults/round-trip support.
- `src/tools/scenario_compiler.py` - extended the scenario analysis schema with required `pressure_profile` metadata and passed `current_best_offer` into the round-context renderer.
- `src/modules/persona/__init__.py` - added optional `current_best_offer` handling and the final-round BATNA-vs-best-offer wording.
- `tests/self_play/verify_scenario_pressure.py` - verified the final-round context includes the new comparison text.
- `tests/test_persona.py`, `tests/test_scenario_compiler.py`, `tests/test_scenario_spec.py`, `tests/self_play/fake_llm_client.py` - updated coverage and fixture shapes.
- `tests/self_play/scenarios/*.json`, `tests/self_play/scenarios/joint_space_mission_v1/spec.json` - committed `pressure_profile` metadata for the checked-in scenarios/spec.
Focused verification: `python3 -m pytest -q tests/test_persona.py tests/test_scenario_compiler.py tests/test_scenario_spec.py tests/test_scenario_pressure.py` --- `61 passed`; JSON load check on touched scenario files passed.

## 2026-06-11 - Phase 38 step 38.4 follow-up: verified final-round summary and pressure fixture metadata

Verified the step 38.4 follow-up edits in the live tree: `src/modules/persona/__init__.py` now emits the combined final-round summary line (`No deal = N pts (your BATNA); current best offer = M pts; walking away costs you M-N pts`) ahead of the existing detail lines, `tests/self_play/fixtures/pressure/pressure_good.json` now carries `pressure_profile`, and the matching tests assert both changes. Focused regression slice passed again after the edits: `python3 -m pytest tests/test_persona.py tests/test_scenario_pressure.py tests/test_scenario_compiler.py` and the direct pressure verifier smoke both passed.

### Step 38.5: doc update and phase-close prep
Mode: Build
Outcome: Updated the phase-close docs to mark Phase 38 closed, record the pressure schema in the architecture and assessment docs, and advance DEVPLAN to the review state.
Contract changes:
- `ARCHITECTURE.md` - scenario compiler / builder rows now mention pressure metadata and pressure-aware round-context rendering.
- `ASSESSMENT.md` - §4.5 pressure row now points at the implemented `pressure` object; the pressure-mechanisms note now distinguishes shipped small-bundle fields from deferred exogenous events.
- `NEXT_STEPS.md` - Phase 38 status updated to closed across the backlog summary, pressure section, and reverse-scenario-builder lineage.
- `DEVPLAN.md` - Step 38.5 checked off.

This step was doc-only. No code or test changes were needed. The next action is Phase 38 review.

## 2026-06-11 - Phase 38 close: pressure mechanisms small bundle complete

Phase 38 closed after the pressure small bundle shipped end to end: `pressure` now carries round-cost decay, asymmetric clocks, penalty floor, and pressure-profile metadata; persona rendering and the final-round marker are pressure-aware; verifier coverage is in place. Close verification passed on the focused phase slice (`python3 -m pytest -q tests/test_persona.py tests/test_scenario_pressure.py tests/test_scenario_compiler.py tests/test_scenario_spec.py` — `61 passed`). `DEVPLAN.md` now shows Phase 38 as complete with a DEVLOG reference.

## 2026-06-11 - Phase 39 step 39.2: scenario compiler fill-narrative CLI

Extended `tools.scenario_compiler` with `--fill-narrative-only <analysis_path>` and `--domain-context-file <path>`, plus a `--scenario-title` alias that preserves the existing `--title` flag. The CLI now skips forward scenario analysis when fill-only mode is set, loads an existing `scenario_analysis.json`, threads optional domain framing into `fill_narrative()`, and re-renders personas in place. Added parser coverage and a fill-only integration test that rewrites a copied joint-space fixture back to the checked-in analysis output shape while asserting the domain context prompt payload. Focused verification passed: `python3 -m pytest -q tests/test_scenario_compiler.py` (`44 passed`).

### Step 39.3: fill-narrative integration and temp helper removal
Mode: Build
Outcome: Verified the fill-narrative-only integration path against the checked-in joint-space fixture, confirmed the copied analysis rewrites back to the expected prose payload, and removed the temporary `tools/_temp_fill_narrative.py` helper now that the permanent CLI path covers the use case.
Contract changes: none
The existing integration test in `tests/test_scenario_compiler.py` already exercised the scenario-compiler fill-only path by stubbing the LLM response, resetting `scenario_analysis.json` to logrolling/deception stubs in a temp copy, and asserting the rewritten analysis plus regenerated persona output matched the checked-in fixture content. Focused verification passed with the repo venv: `./.venv/bin/python -m pytest -q tests/test_scenario_compiler.py` (`44 passed`). With that coverage in place, the temporary helper script was deleted.

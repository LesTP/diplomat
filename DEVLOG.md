# Diplomat — Development Log

<!-- Reverse-chronological record of what happened during development.
     Newest entries at the top. Each step or milestone gets a structured entry.
     This is the audit trail.

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

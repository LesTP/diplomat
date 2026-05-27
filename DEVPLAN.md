---
phase: 17
blocked: false
state: review
steps_remaining: 1
---

# Diplomat — Development Plan

## Cold Start Summary

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - Bot vs. user account question must be resolved with game moderator before deployment; implement `TelethonUserTransport` only if bot-to-bot messaging is unavailable
  - Round structure (signal vs. time-based) must be confirmed before Orchestrator event loop
  - `toolkit` lives at `../toolkit` and must be installed editable into the diplomat venv (`<venv>/bin/python3 -m pip install -e ../toolkit`). It is not declared in `pyproject.toml` to avoid a misleading install contract — fresh `pip install -e .` cannot resolve `toolkit` from PyPI, so the editable install is a one-time per-host setup step. Module-level tests use dependency-injected fakes for isolation; that pattern is fine and should continue, but integration paths in Orchestrator must exercise real `toolkit` imports
  - Debounce strategy resolved (11.2): per-message cooldown — each new message cancels and reschedules the extraction timer; avoids redundant LLM calls under burst traffic
  - Cost governance resolved (11.4): CostBudget resets per round (strict per-round cap); session totals tracked in cost_ledger.jsonl by CostAccountant
  - CostAccountant is a thin wrapper around the module-level llm_client call: Orchestrator checks budget before dispatching each LLM call and alerts operator on over-budget
  - Before deployment, install `../toolkit` editable and run live probes for `llm_client`, `telegram_client`, and `cost_accountant`; this environment cannot import `toolkit`, so Phase 11 close recorded probe specs rather than live matches

## Current Status

- **Phase** — Phase 17: Layer 2 prompt regression infrastructure.
- **Focus** — Build the scenario runner, LLM-as-judge, and initial scenario library for prompt quality validation.
- **Blocked/Broken** — none.

## Phase 17: Layer 2 — Prompt Regression Infrastructure

Regime: Build. Scope: Create the prompt regression testing framework — scenario JSON format, scenario runner, LLM-as-judge evaluator, and a starter set of scenarios for Extraction and Generation modules. This infrastructure validates that prompt changes don’t break expected behavior. Reference: `diplomat-testing-doc.md` §4.

**Design constraints:**
- Scenarios are JSON files with structural assertions (`json_path_exists`, `json_path_equals`) and/or LLM-as-judge qualitative evaluations
- The LLM-as-judge uses the same adapter interface as all Diplomat modules (injected `llm_client`, plain dicts in, plain str out) — no direct toolkit imports
- The scenario runner calls real LLM APIs for the module under test and (optionally) for judge evaluations — **this costs money**. Use `commodity` tier models for judging.
- Scenarios target individual modules (extraction, generation, analyst, adversarial), not the full pipeline
- All existing 193 unit/integration tests must continue to pass
- Runner must work on the Pi where toolkit is installed; scenarios can be authored anywhere

Steps:

- [x] 17.1 — **Scenario format and result types.** Create `tests/prompt_regression/__init__.py` and `tests/prompt_regression/types.py` with:
  - `PropertyCheck` dataclass: `type` (json_path_exists | json_path_equals | llm_judge), `path`/`value`/`criteria`/`pass_instruction`/`fail_instruction`, `description`
  - `PropertyResult` dataclass: `passed`, `description`, `expected`, `actual`, `judge_explanation`
  - `ScenarioResult` dataclass: `scenario_id`, `description`, `properties: list[PropertyResult]`, `passed`
  - `RunReport` dataclass: `results: list[ScenarioResult]`, `total`, `passed`
  - `load_scenario(path) -> dict` and `load_scenarios(directory) -> list[dict]` helpers that read and validate scenario JSON files
  - `json_path_exists(data, path) -> bool` and `json_path_get(data, path) -> Any` helpers for dotted-bracket path navigation (e.g., `patch.data.promises[0].status`)
  Add unit tests for the path helpers in `tests/test_prompt_regression_types.py`. Run full regression.

- [x] 17.2 — **LLM-as-judge module.** Create `tests/prompt_regression/judge.py` with:
  - `JudgeResult` dataclass: `verdict` (PASS/FAIL), `explanation`, `criteria`
  - `LLMJudge` class: constructor accepts `llm_client` and `llm_config: dict` and `tier: str = "commodity"`; `async evaluate(response_text, criteria, pass_instruction, fail_instruction, context="") -> JudgeResult`
  - The evaluate prompt asks the LLM to return `PASS|explanation` or `FAIL|explanation`; parser splits on `|`
  - Add a unit test with a fake LLM client that returns canned `PASS|reason` and `FAIL|reason` to verify parsing
  Run full regression.

- [x] 17.3 — **Scenario runner.** Create `tests/prompt_regression/runner.py` with:
  - `ScenarioRunner` class: constructor accepts `llm_client`, `llm_config: dict`, and module builder callables
  - `async run_scenario(scenario: dict) -> ScenarioResult`: calls the appropriate module (extraction/generation/analyst/adversarial) with the scenario input, then evaluates each `expected_properties` entry using structural checks or LLM-as-judge
  - `async run_all(scenario_dir: str) -> RunReport`: loads all scenarios, runs each, prints per-scenario PASS/FAIL, prints summary
  - CLI entry point: `python -m tests.prompt_regression.runner --scenarios <dir>` with optional `--module <name>` filter
  Add a smoke test with a fake LLM client and one inline scenario dict to verify the runner produces a `RunReport`. Run full regression.

- [x] 17.4 — **Starter scenarios: extraction.** Create `tests/prompt_regression/scenarios/extraction/` with 4 JSON scenarios:
  1. `promise_explicit.json` — explicit promise creates pending promise entry (structural: `json_path_exists` on `patch.data.promises[0]`, `json_path_equals` on status=pending)
  2. `promise_vague.json` — vague offer does NOT create promise (structural: promises array empty or absent)
  3. `coalition_formation.json` — alliance announcement creates coalition entry
  4. `inconsistency_detection.json` — contradiction creates inconsistency entry
  These scenarios use `RuleBasedExtractor` (free, no API calls) so they double as structural validation. Run full regression.

- [x] 17.5 — **Starter scenarios: generation.** Create `tests/prompt_regression/scenarios/generation/` with 2 JSON scenarios:
  1. `constraint_respect.json` — CONSTRAINT coaching must be respected (llm_judge: response does not accept forbidden alliance)
  2. `persona_consistency.json` — response matches faction persona tone (llm_judge: response uses appropriate diplomatic framing)
  These require real LLM calls for both generation and judging. Document expected cost per run. Run full regression.

- [x] 17.6 — **Documentation and regression.** Verify full test suite (193 existing + new type/runner tests). Update DEVPLAN Phase 17 summary. Update `diplomat-testing-doc.md` Layer 2 status. Append DEVLOG entry. Transition to `state: review`.

Summary: Implemented Layer 2 prompt regression infrastructure: scenario/result dataclasses, scenario JSON validation, dotted/bracket JSON-path helpers, LLM-as-judge evaluation, a module-builder based scenario runner with CLI, 15 focused prompt-regression unit tests, 4 free Extraction scenarios, 2 LLM-backed Generation scenarios, and cost documentation for paid generation runs. Free extraction scenario suite passes 4/4 locally; full regression passes 207 tests. Generation scenarios are authored but require a live injected LLM client on the Pi to execute.

## Phase 16: Deployment Readiness

Complete. Restored regression coverage for live-smoke fixes, documented two-channel Telegram deployment, added `config/diplomat.service`, removed temporary transport debug prints, fixed the CostAccountant adapter construction found during review, and verified 193 passing tests. See `DEVLOG.md`.

## Phase 15: Live Smoke Test — Environment Setup

Complete. Created `.env.template` and `config/pipeline_smoke.yaml`. Validated startup on Pi with real toolkit imports. Manual smoke test confirmed: Telegram transport receives messages, operator commands (`/status`, `/state`, `/ledger`, `/commands`) respond correctly, `/preview` triggers LLM generation, review gate (`/approve`, `/block`) works. Five integration fixes applied during smoke test:
1. Transport: added `message_text` to content field lookup (TelegramUpdate compatibility)
2. Transport: changed `start_polling()` from blocking await to background task with race condition fix
3. Review Gate: added `message_text` to content field lookup
4. Orchestrator: added `/commands` handler listing all commands and coaching tags
5. Orchestrator: added `/block` acknowledgement message

All fixes committed. See `DEVLOG_archive.md`.

## Phase 14: Layer 3 — Transcript Replay Tests

Complete. Two JSON transcript fixtures (`cooperative_3round.json`, `betrayal_arc.json`) and five replay integration tests verify multi-round promise, coalition, inconsistency, and intelligence persistence through the fake-backed Orchestrator pipeline. Full regression: 187 passed. See `DEVLOG.md`.

## Phase 13: Layer 3 — Pipeline Integration Tests

Complete. Implemented fake-backed Layer 3 integration infrastructure and 12 tests covering fixture startup, core Orchestrator flow, and failure handling. Full regression: 182 passed. See `DEVLOG.md`.

## Phase 12: Orchestrator Refactor

Complete. Extracted `ToolkitLLMAdapter` and `DiplomatCostGate` to `src/adapters.py`, expanded State Manager with 5 persistence APIs, removed Orchestrator sqlite3 fallbacks, typed `InboundEvent` on public event/pipeline methods, and verified 170 regression tests. See `DEVLOG.md`.

## Phase 11: Orchestrator

Complete. Implemented `pipeline.yaml`, registry lookup, Orchestrator startup/event-loop/round-management/response-pipeline/cost-governance wiring, `src/main.py`, and 44 focused Orchestrator tests with 165 total regression tests passing. Phase Review applied three should-fix items and no must-fix items. Post-phase toolkit integration probes found 3 mismatches; adapters (`ToolkitLLMAdapter`, `DiplomatCostGate`) applied and verified on Pi. See `DEVLOG.md`.

## Phase 10: Adversarial

Complete. Implemented `AdversarialResult`, `LLMAdversarialReader`, local adversarial JSON/schema validation, prompt/schema artifacts, and 9 focused tests with 121 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG_archive.md`.

## Phase 9: Review Gate

Complete. Implemented review decisions, auto-approve mode, Telegram approve/edit/block workflow, optional timeout auto-block, and 14 focused tests with 112 total regression tests passing. Phase Review applied two should-fix items. See `DEVLOG_archive.md`.

## Phase 8: Generation

Regime: Build. Scope: `GenerationResult` dataclass, `LLMGenerator.generate()`, review-gate JSON response parsing, plain-text mode, generation prompt/config artifacts, and full regression coverage. No direct provider SDK imports; all LLM calls stay behind toolkit-compatible dependency injection.

Steps:
- [x] 8.1 — Implement `GenerationResult` and `LLMGenerator` in `src/modules/generation/__init__.py`. Constructor accepts toolkit-compatible LLM config/client dependency, tier, max_tokens, and `review_gate_enabled`; `generate(context)` calls the injected completion client with `DecisionContext.system_prompt` and `DecisionContext.user_prompt`, returns `success=False` for client exceptions, and preserves provider/debug response data where available. Add `tests/test_generation.py` coverage for successful plain-text generation, client exception failure, prompt forwarding, tier/max token forwarding, and provider/raw response propagation. Run focused tests.
- [x] 8.2 — Add review-gate JSON handling and generation prompt/config artifacts. When `review_gate_enabled=True`, require JSON containing `response` and `reasoning`; reject malformed JSON, missing/blank response, and schema-shaped failures through `GenerationResult.success=False`. When disabled, treat nonblank plain text as `response_text` with `reasoning=None`. Create `config/prompts/generation.txt` with JSON/plain output instructions aligned to `ARCH_generation.md`. Run focused tests plus full regression.
- [x] 8.3 — Documentation cleanup and regression verification. Verify the full suite, update Phase 8 summary/status, mark implementation sequence row 9 as pending review, and transition DEVPLAN to `state: review`.

Summary: Implemented `GenerationResult`, `LLMGenerator`, review-gate JSON parsing (`response`, `reasoning`), plain-text mode, raw response preservation, `config/prompts/generation.txt`, and 11 focused Generation tests. Full regression: 98 passed. Phase Review found and fixed one must-fix: Context Assembler was instructing the LLM to use `draft_message`/`rationale` keys while Generation expected `response`/`reasoning` — fixed in both `_format_output_instruction` and its test. Phase complete.

## Phase 7: Context Assembler

Complete. Implemented `CoachingEntry`, `DecisionContext`, `DefaultContextAssembler` (pure composition, no external deps), 7-test coverage with 87 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG.md`.

## Phase 6: Analyst + Divergence

Complete. Implemented shared intelligence result types, `LLMAnalyst`, pure divergence comparison, analyst prompt/schema, and 12-test coverage with 80 total regression tests passing. See `DEVLOG.md`.

## Phase 5: Persona

Regime: Build. Scope: `CoachingContext` dataclass, `FileBasedPersona` (both public methods), hot-reload, `config/faction_prompt.txt` sample, full test coverage.

Steps:
- [x] 5.1 — Implement `CoachingContext` + `FileBasedPersona` (`get_base_prompt`, `build_round_context`) in `src/modules/persona/__init__.py`. Write `tests/test_persona.py` covering: FileNotFoundError, fresh read, hot-reload on mtime change, no-reload when unchanged, CURRENT ROUND CONTEXT section stripping, `build_round_context` formatting with all fields, empty fields, `rounds_remaining=None`. Run full suite.
- [x] 5.2 — Create `config/faction_prompt.txt` with sample faction persona including `## CURRENT ROUND CONTEXT` marker. Run full regression (59 + new persona tests pass). Update DEVPLAN summary, DEVLOG, ARCHITECTURE.md status.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Complete. Implemented `config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, config validation, tagged/free coaching parsing, slash command parsing, and 11-test coverage with 38 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 4: Transport

Complete. Implemented shared Transport API exports, `CLITransport`, dependency-injected `TelegramBotTransport` send/listen paths, and 21 focused Transport tests with 59 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

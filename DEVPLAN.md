---
phase: 15
blocked: false
state: execute
steps_remaining: 0
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

- **Phase** — Phase 15: Live smoke test — environment setup and real Telegram + LLM validation.
- **Focus** — Prepare deployment config, .env template, and cheap pipeline config for manual smoke testing on Pi.
- **Blocked/Broken** — none.

## Phase 15: Live Smoke Test — Environment Setup

Regime: Build (steps 1–3) + Explore (step 4 — manual testing, fix what breaks). Scope: Create the deployment environment artifacts needed to run `python src/main.py` on the Pi with a real Telegram bot and real LLM provider, then validate the full pipeline end-to-end. Reference: `diplomat-testing-doc.md` §5b.

**Key difference from prior phases:** Step 4 is manual and interactive. The worker prepares the environment and validates that the system starts; the human operator runs the actual Telegram smoke test. The worker fixes any issues found during startup or the initial import/config validation.

**Cost strategy:** Use the cheapest viable model for all LLM roles. `RuleBasedExtractor` is already config'd (free). Set tight budgets (`per_round_budget_usd: 0.50`, `session_budget_usd: 2.00`). If Claude API tokens are depleted, use OpenAI for all providers.

Steps:

- [x] 15.1 — **Create `.env.template` and `config/pipeline_smoke.yaml`.** Create `.env.template` listing all required environment variables with placeholder values and comments:
  - `TELEGRAM_BOT_TOKEN` — from @BotFather
  - `DIPLOMAT_PUBLIC_CHANNEL_ID` — numeric Telegram chat ID for game messages
  - `DIPLOMAT_COACHING_CHANNEL_ID` — numeric Telegram chat ID for operator commands
  - `DIPLOMAT_OPERATOR_USER_IDS` — comma-separated operator Telegram user IDs
  - `OPENAI_API_KEY` — OpenAI API key
  - `ANTHROPIC_API_KEY` — Anthropic API key (optional if using OpenAI only)

  Create `config/pipeline_smoke.yaml` copied from `pipeline.yaml` with these modifications:
  - Both `primary` and `secondary` providers set to `openai` with `gpt-4.1-mini` for all tiers (cheapest config, single API key needed)
  - `cost.per_round_budget_usd: 0.50`
  - `cost.session_budget_usd: 2.00`
  - `modules.extractor.class: RuleBasedExtractor` (already the case)
  - `modules.review_gate.class: TelegramReviewGate` (live review gate, not auto-approve)
  - `feature_flags.review_gate.enabled: true`
  - `feature_flags.adversarial.enabled: false` (skip adversarial to reduce LLM calls during smoke test)

  Run `python3 -m py_compile src/main.py` and full regression to confirm nothing broken.

- [ ] 15.2 — **Validate startup on Pi.** On the Pi (inside the Incus container where toolkit is installed), copy `.env.template` to `.env` and fill in real values (bot token, channel IDs, operator user IDs, API key). Run:
  ```
  cd /home/claude/workspace/diplomat
  DIPLOMAT_PIPELINE_CONFIG=config/pipeline_smoke.yaml .venv/bin/python src/main.py
  ```
  Verify:
  - No import errors (`toolkit.llm_client`, `toolkit.telegram_client`, `toolkit.cost_accountant` all resolve)
  - Config validation passes (no `PipelineConfigError`)
  - Bot prints `DIPLOMAT ONLINE - Round 1 - england - session budget $2.00`
  - Bot connects to Telegram (no `TelegramClient` connection errors)

  If startup fails, fix the issue and re-run. Document any adapter or config fixes in DEVLOG. Run full regression after any code changes.

- [ ] 15.3 — **Manual smoke test (human-driven).** With the bot running, the human operator performs the smoke test checklist from `diplomat-testing-doc.md` §5b:
  1. Game message → extraction → `/state` shows promise
  2. Operator coaching (`PRIORITY:`, `INTEL:`) → `/status` shows coaching
  3. Round boundary → `/intel` shows analysis
  4. Direct address or `/preview` → review gate sends draft → `/approve` posts response
  5. `/ledger` shows cost tracking

  The worker’s role during this step: monitor console output, fix any runtime errors (Telegram update parsing, channel routing, LLM response parsing), and document findings. Each fix gets a test + DEVLOG entry.

- [ ] 15.4 — **Documentation and regression.** Document smoke test results in DEVLOG: what worked, what broke, what was fixed. Update DEVPLAN Phase 15 summary. If any code changed, run full regression. Transition to `state: review`.

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

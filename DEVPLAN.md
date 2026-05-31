---
phase: 19
blocked: false
state: execute
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
  - Debounce strategy: **rewritten in Phase 18** from per-message cancel-and-replace to per-event task set. Each game message gets its own extraction task; no cancellation between different messages. The original design (11.2) silently dropped messages in multi-message bursts.
  - Cost governance: CostAccountant is now wired through `ToolkitLLMAdapter` — every LLM call routes through `accountant.complete()` for budget-check + ledger write. The `DiplomatCostGate` check-before-call pattern remains for round-level budget control. Both share the same accountant instance.
  - All four LLM modules (extraction, analyst, adversarial, generation) now use `toolkit.structured_llm.structured_call()` for schema-enforced JSON output with automatic retry on validation failure.
  - Self-play cost ledger uses a local temp path (`%TEMP%/diplomat_selfplay/`) to avoid UNC path issues on network shares.
  - Before deployment, install `../toolkit` editable and run live probes for `llm_client`, `telegram_client`, and `cost_accountant`; this environment cannot import `toolkit`, so Phase 11 close recorded probe specs rather than live matches
  - Prompt regression runner: `_judge_response_text()` JSON path extraction must be wrapped in try-catch — if a scenario's `path` does not exist in module output, the raw KeyError propagates and crashes the runner. Fixed in Phase 17 review; always validate extraction paths before production scenario runs.
  - **Cross-provider JSON formatting (Run 8 fix).** Anthropic and Google wrap JSON output in ` ```json ... ``` ` Markdown fences regardless of explicit "return raw JSON" instructions. OpenAI returns raw JSON. Toolkit's `parse_json_response` (in `structured_llm/core.py`) now strips a single surrounding code fence before parsing. Without this, structured_call's retries silently exhaust and downstream modules see "no error" but receive nothing.
  - **Self-play env loading (Run 8 fix).** `tests/self_play/run_simulation.py` calls `load_dotenv()` at module top. Previously only env vars in the parent shell were visible to subprocess SDKs — typically only `OPENAI_API_KEY` was reliable; Anthropic and Google calls silently failed auth.
  - **Per-faction provider routing (Run 8).** Use `--per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},...}'` to vary only the Generator per faction. Other modules stay on shared primary/secondary. Verify with `verify_dryrun --expect-providers '{"alpha":"openai",...}'`.
  - **Pre-compiled analysis loader (Run 8).** Use `--analysis-json <path>` to skip live LLM compilation and load a pre-edited analysis JSON (preserves hand-tuned BATNAs, scoring tables, deception tactics). Requires `--scenario` for the seed-message text. Personas are regenerated from the loaded analysis at startup.
  - ~~**Compiler BATNA anchor (Run 8 surfaced).**~~ **FIXED in Phase 19** (2026-05-30). `tools/scenario_compiler.py` system prompt hardcoded "typically 4-8 total" BATNAs regardless of narrative. Now replaced with a fraction-of-max formula; `--batna-fraction` CLI flag (default 0.50) on both `tools.scenario_compiler` and `tests.self_play.run_simulation`. `validate_batna_pressure()` warns post-hoc if LLM under-sets. See `TUNING.md` §1 BATNA section for semantics; `DEVLOG.md` for the fix.
  - **Run live probe before multi-provider games.** `python -m tests.self_play.probe_providers --providers '<same JSON as --per-faction-providers>'` hits each provider once with a trivial JSON request and verifies auth + roundtrip + parse. ~$0.001 total. Catches integration bugs (missing API keys, fence wrapping, model name typos) that `DryRunLLMClient` cannot catch by design (DryRun replaces the LLM client entirely with canned responses, so no real auth/parse path runs). Run this before every multi-provider simulation. For Gemini 2.5 *flash* and *pro*, **set `--max-tokens 500` or higher** — their thinking-mode consumes output tokens before producing visible content; default `--max-tokens 50` returns only the opening ` ``` ` fence. `gemini-2.5-flash-lite` has no thinking mode and is unaffected; that's the tuning default.
  - ~~**Google Gemini free-tier quota on this project: 20 requests/day**~~ **RESOLVED 2026-05-30**. Operator enabled billing on the GCP project + bought $10 credits; now on paid Tier 1 with ~1000+ RPM, hundreds of thousands RPD. Every call billed; at flash-lite rates ($0.10 in / $0.40 out per MTok), $10 buys ~5000 games. No quota concern for normal experimentation. See `TUNING.md` §1 Google defaults.
  - **Follow `RUN_PROTOCOL.md` for any live multi-agent run.** The doc formalizes the pre-flight sequence: define inputs → verify scenario → probe providers → dry-run plumbing → run live → verify output → document. Skip rules and abort conditions are spelled out. Read it once before the first live run of a session.
  - **Phase 18 retroactively reclassified Build → Explore.** Started Build-regime (steps 18.1–18.5), morphed into Explore as work shifted to "run sims and tune." Self-time-boxed by spending. Future cold-start sessions should not be surprised that a planned 6-step phase grew to 16 steps + two named runs (Run 7 Prep, Run 8). See `DEVLOG.md` Phase 18 Close entry for full explanation.
  - **Phase 19 is operating ad-hoc** — driven by `NEXT_STEPS.md` rather than formal step plan. Multiple shipped items already (retry-with-backoff, LoggingLLMClient SCORE/RECON fix, scenario compiler BATNA fix, dated-pricing fix, production reconciler wiring, production endgame-markers config, SMOKE_RUNBOOK). Each lives in its own `DEVLOG.md` Phase 19 entry. No formal step boundaries; close-out happens when `NEXT_STEPS.md` sequencing position #1 is completed and we decide to formalize Phase 20.
  - **New canonical docs added Phase 19:** `CLI_REFERENCE.md` (every CLI entry point with flags, defaults, examples), `SMOKE_RUNBOOK.md` (operator-side Pi smoke procedure mapping each Phase 18+19 change to a verification step). Both at project root.
  - **Toolkit Phase 19 surface required on Pi:** `from toolkit.llm_client import complete_with_retry` and `from toolkit.cost_accountant import normalize_model_name`. Both must import successfully — if they raise ImportError on the Pi, reinstall editable: `incus exec claude-code -- bash -c 'cd /home/claude/workspace/diplomat && .venv/bin/python -m pip install -e ../toolkit'`. See `SMOKE_RUNBOOK.md` §1.3.
  - **Real Pi deployment mechanism:** `tools/service.sh start` (nohup-based) inside `incus exec claude-code`, default config `pipeline_smoke.yaml` (which already has `TelegramReviewGate`). Not systemd — the unit file at `config/diplomat.service` was never installed. See `SMOKE_RUNBOOK.md` §2 and `CLI_REFERENCE.md`.
  - **Production reconciler now wired** (Phase 19, 2026-05-30). `src/main.py` attaches a `StateReconciler` using the primary provider's commodity tier; fires at every round boundary before analysts. Closes Phase 18 gap. Self-play harness's per-faction wiring still wins via last-write-overrides.
  - **`game.total_rounds` optional config** (Phase 19, 2026-05-30). When set in `pipeline.yaml`, `Orchestrator.__init__` reads it and the persona's PENULTIMATE/FINAL ROUND markers fire. Unset means production stays endgame-blind — fine for games where the round count is unknown.

## Current Status

- **Phase** — Phase 19 (Execute, ad-hoc per `NEXT_STEPS.md`). Phase 18 closed 2026-05-30 with regime-shift acknowledgment.
- **Focus** — `NEXT_STEPS.md` sequencing position #1: **live Telegram re-smoke on Pi**. Operator runs `SMOKE_RUNBOOK.md` end-to-end on the Pi container, then logs outcomes in DEVLOG. All Phase 18+19 changes (debounce fix, structured_call, cost wiring + dated-pricing normalization, retry-with-backoff, production reconciler, production endgame-markers config, SMOKE_RUNBOOK) are in place ready to be exercised by the smoke.
- **Shipped in Phase 19 so far** (each has its own `DEVLOG.md` entry):
  - `toolkit/llm_client.complete_with_retry` (exponential backoff on 429/5xx/empty)
  - `toolkit/cost_accountant.normalize_model_name` + refreshed gpt-5.x / Gemini 2.5 prices (fixes ~41× cost-ledger overestimate from dated-ID lookup miss)
  - LoggingLLMClient SCORE/RECON visibility (`_TaggedLLMClient` wrapper for self-play call attribution)
  - Scenario compiler BATNA hardcode replaced with fraction-of-max formula + `--batna-fraction` CLI + post-hoc `validate_batna_pressure()`
  - Production `_attach_reconciler` in `main.py`
  - Optional `game.total_rounds` in `pipeline.yaml`, read by `Orchestrator.__init__`
  - `CLI_REFERENCE.md` (project root) — every CLI entry point with flags/defaults/examples
  - `SMOKE_RUNBOOK.md` (project root) — operator-side Pi smoke procedure
  - `tools/inspect_ledger.py` rewritten with CLI args (`--selfplay`, `--path`, `--show`) and bug fix
- **Blocked/Broken** — None.
- **Reference docs** — `NEXT_STEPS.md` (forward-looking backlog + Run 8 review TODOs), `SMOKE_RUNBOOK.md` (Pi smoke procedure), `CLI_REFERENCE.md` (every flag), `TUNING.md` (operator tuning manual with BATNA + Google sections), `TUNING_LOG.md` (run-by-run record through Run 8), `ARCH_conversation_model.md` (Stage 1/2/3 migration), `RUN_PROTOCOL.md` (pre-flight for self-play live runs).

## Next Steps: Modularization Roadmap

The system is functional for the diplomacy game. The following levels of modularization would make it reusable across domains (customer service, contract negotiation, sales, etc.). See `ARCH_reconciliation.md` for reconciliation design.

### Level 1: Config-Driven Prompts and Examples (recommended next)

Move all entity-type-specific content out of Python code into config files that sit alongside the schema. The code reads the schema to discover entity types and loads corresponding examples and prompt fragments dynamically.

**What changes:**
- Extraction few-shot examples (`_EXTRACTION_EXAMPLES`) → `config/examples/extraction_examples.json`
- Reconciliation prompt entity references → derived from schema keys
- Analysis tool entity iteration → reads schema instead of hardcoding "promises", "coalitions"
- Persona library structure: `config/personas/styles/` for reusable behavioral templates, overlaid with domain-specific scoring by the scenario compiler

**Result:** Switching domains = replace `config/` directory. No code changes.

**Effort:** 1-2 hours.

### Level 2: Schema-Driven State Manager (needed for true reuse)

The state manager generates SQLite tables from `state_patch.json` at startup. Each entity type in the schema becomes a table. Upsert/delete/query methods derive field names and primary keys from the schema rather than hardcoding them.

**What changes:**
- `_create_tables()` reads schema and generates `CREATE TABLE` statements
- `_upsert_promise()` / `_upsert_coalition()` etc. → generic `_upsert_entity(table, item)`
- Table-to-ID-column mapping derived from schema `required` fields

**Result:** `state_patch.json` is the single source of truth for both validation and storage.

**Effort:** Half a day. Wait until you actually try a second domain to feel the pain first.

### Level 3: Domain-Agnostic Orchestrator (future)

Remove game-specific flow assumptions (round boundaries, direct-address triggers). Replace with configurable triggers and a flow definition.

**What changes:**
- Orchestrator becomes a state machine configured by a flow YAML
- Round detection → generic "boundary condition" pattern matching
- Direct-address → generic "response trigger" rules

**Effort:** Multiple days. Only if you have a concrete non-game use case.

## Open Items and Future Plans

### Immediate (before deployment)
- [ ] **Live Telegram re-smoke.** Phase 18 changes (debounce fix, structured_call, cost wiring, reconciliation) have only been validated in self-play. Need a manual Telegram smoke test on the Pi covering multi-message burst, review gate, and cost ledger.
- [ ] **Switch to TelegramReviewGate.** Production `pipeline.yaml` uses `AutoApproveReviewGate` (safe default). Change to `TelegramReviewGate` on the Pi when deploying with real credentials.
- [ ] **Run scored Three-Party Coalition.** The last attempt failed on a UNC path issue (now fixed). Validates post-game scoring + reconciliation end-to-end.

### Self-Play / Multi-Provider Experimentation
- [ ] **Run 9 — rotated provider assignments.** Water Rights scenario, rotate provider→faction mapping to control for position-vs-provider confound (Alpha won Run 8 by tiebreak with the highest BATNA — coincidence?). Same plumbing as Run 8.
- [ ] **Persona payment rigidity (recurring across Run 7 + Run 8).** Agents anchor on extreme outcomes on their priority issue and refuse to propose Pareto compromises that beat all BATNAs. The persona-prompt rule "don't accept the first reasonable framework" may be over-anchoring. A/B test a softened variant.
- [ ] **Google free-tier rate limiting.** Gemini-2.5-flash hit 429 on Run 8 R4. Add retry-with-backoff to toolkit's `llm_client`, OR switch gamma to a paid Gemini tier.
- [ ] **Compiler BATNA anchor.** `tools/scenario_compiler.py` hardcodes BATNA range guidance regardless of narrative. Add a `--batna-fraction` override, OR relax the range guidance, OR accept the hand-patch workflow (currently using `--analysis-json` to preserve hand-edits).
- [ ] **`LoggingLLMClient` doesn't see SCORE or RECON calls (Run 7).** Both unwrap the wrapper to call the inner client. Fix the unwrap so all calls go through one observable client.

### Extraction Quality
- [ ] **Promise dedup via reconciliation.** Reconciler is built but untested with live LLM. Run 4 showed 5 duplicates of the same $2M commitment.
- [ ] **Fulfillment detection.** Only 1/21 promises ever marked "kept". Reconciler should fix this — needs live validation.
- [ ] **Inconsistency detection.** Zero inconsistencies detected across 7 runs despite clear position shifts. Reconciler prompt specifically targets this.
- [ ] **Under-extraction in coalition games.** Run 6 (Three-Party Coalition) tracked only 1 promise out of 12 concrete proposals. Broadened extraction prompt may help; needs re-test.

### Prompt Tuning
- [ ] **Persona drift over 8+ rounds.** All runs were 4 rounds. Longer games may show persona drift — agents gradually losing their distinctive voice.
- [ ] **Provider-native structured output.** OpenAI's `response_format: json_schema` would give near-100% schema compliance at the token level. Requires toolkit `llm_client` changes to pass the parameter through.
- [ ] **Add more extraction few-shot examples.** Current 5 examples cover promise/coalition/fulfillment/broken/empty. Could add: conditional offer, demand with deadline, position shift, multi-issue proposal.

### Infrastructure
- [ ] **Persona library.** Separate behavioral styles from domain-specific scoring. Reusable templates in `config/personas/styles/`.
- [ ] **Game-mode runtime override.** `--game-mode` flag on the runner to override the compiler's classification without regenerating personas.
- [ ] **Level 1 modularization.** Config-driven prompts and examples (see roadmap above).
- [ ] **Dated model pricing in toolkit.** OpenAI returns `gpt-4.1-mini-2025-04-14` but pricing table has `gpt-4.1-mini`. Fallback pricing works but overestimates cost.

### Game-Specific
- [ ] **Real game rules.** Game rules are still being finalized. When available, compile them through the scenario compiler to generate the real faction persona.
- [ ] **ClankmatesTransport.** If the game moves to Clankmates platform, build a polling-based transport (no webhooks). Keep Telegram for operator coaching.
- [ ] **Multi-game support.** Run multiple instances with different faction prompts and databases for parallel games.

## Phase 19: Next Steps (Execute, ad-hoc)

Regime: Execute, driven by `NEXT_STEPS.md` rather than a formal step list. Each completed item has its own `DEVLOG.md` Phase 19 entry. No formal step boundaries between items; phase closes when sequencing position #1 (currently: live TG re-smoke on Pi) is done and we decide whether to formalize Phase 20.

**Currently active (sequencing position #1):** live Telegram re-smoke on Pi per `SMOKE_RUNBOOK.md`. Operator-driven, manual checklist. Outcomes get logged in DEVLOG when complete.

**Shipped so far in Phase 19** (each has a dedicated DEVLOG entry):
- toolkit `complete_with_retry` (exponential backoff on 429/5xx/empty)
- toolkit `normalize_model_name` + refreshed pricing table (closed ~41× cost-ledger overestimate)
- LoggingLLMClient SCORE/RECON visibility via `_TaggedLLMClient` wrapper
- scenario_compiler BATNA fraction-of-max formula + `--batna-fraction` CLI + validator
- production `_attach_reconciler` in `src/main.py`
- optional `game.total_rounds` in `pipeline.yaml`, read by `Orchestrator.__init__`
- `CLI_REFERENCE.md`, `SMOKE_RUNBOOK.md` (both at project root)
- `tools/inspect_ledger.py` rewritten with CLI args + bug fix

**Queued after sequencing #1 closes** (per `NEXT_STEPS.md`):
1. Coaching test loop on Pi (validates the operator-coaching workflow end-to-end)
2. OpenRouter integration + Run 9 (multi-provider rotated assignments)
3. Divorce / pressure-mechanism scenario design
4. Stage 2a (K=2 conversation model) + per-round events
5. Clankmates discovery → mock → transport

Dedicated investigations tracked separately in `NEXT_STEPS.md` (§6 pricing audit, §7 per-role model strategy, §8 reverse scenario builder, §9 voice/style templates).

## Phase 18: Layer 4 — Multi-Agent Self-Play + Tuning

Complete. Regime shifted Build → Explore mid-phase (planned 6 steps grew to 16 actual + Run 7 Prep + Run 8 multi-provider). Built complete self-play infrastructure (GameEnvironment, scenario compiler, post-game scoring, state reconciliation, game-mode system), fixed critical pipeline bugs (debounce, cost wiring, budget gate), built reusable `structured_call` toolkit function, tuned all 4 LLM prompts empirically. Ran 8 simulations across 4 scenario types (~$5–6 total spend). Decisions D-20 through D-24 added. Phase Close entry in `DEVLOG.md` Phase 18 Close section documents the regime shift and includes the compressed 16-step list. Run-by-run analysis in `TUNING_LOG.md`.

## Phase 17: Layer 2 — Prompt Regression Infrastructure

Complete. Built `tests/prompt_regression/` package: scenario/result dataclasses, JSON-path helpers, LLM-as-judge, module-builder scenario runner with CLI, 4 free Extraction scenarios, 2 LLM-backed Generation scenarios. Phase Review applied 1 must-fix (safe path extraction in judge) and added 4 edge-case tests. 211 tests pass. Generation scenarios require live injected client on the Pi. See `DEVLOG_archive.md` Phase 17.

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

Complete. Implemented `GenerationResult`, `LLMGenerator`, review-gate JSON parsing (`response`, `reasoning`), plain-text mode, `config/prompts/generation.txt`, and 11 focused tests. Phase Review fixed one must-fix: Context Assembler was instructing LLM with `draft_message`/`rationale` keys while Generation expected `response`/`reasoning`. Full regression: 98 passed. See `DEVLOG_archive.md` Phase 8.

## Phase 7: Context Assembler

Complete. Implemented `CoachingEntry`, `DecisionContext`, `DefaultContextAssembler` (pure composition, no external deps), 7-test coverage with 87 total regression tests passing. Phase Review passed with no must-fix or should-fix items. See `DEVLOG.md`.

## Phase 6: Analyst + Divergence

Complete. Implemented shared intelligence result types, `LLMAnalyst`, pure divergence comparison, analyst prompt/schema, and 12-test coverage with 80 total regression tests passing. See `DEVLOG.md`.

## Phase 5: Persona

Complete. Implemented `CoachingContext`, `FileBasedPersona` (hot-reload via mtime), section stripping at `## CURRENT ROUND CONTEXT` marker, dynamic round-context formatting, and sample `config/faction_prompt.txt`. 68 tests passed. See `DEVLOG_archive.md` Module 5.

## Phase 1: Event Store + State Manager

Complete. Implemented shared storage types, SQLiteEventStore, SQLiteStateManager, state patch schema validation, audit logging, and Phase 1 test coverage. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 2: Extraction

Complete. Implemented `ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, rule-based promise/coalition/inconsistency fallback, `config/prompts/state_updater.txt`, and 18-test coverage with fake toolkit client. 27 tests pass (including Phase 1 regression). See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 3: Coaching

Complete. Implemented `config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, config validation, tagged/free coaching parsing, slash command parsing, and 11-test coverage with 38 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

## Phase 4: Transport

Complete. Implemented shared Transport API exports, `CLITransport`, dependency-injected `TelegramBotTransport` send/listen paths, and 21 focused Transport tests with 59 total regression tests passing. See `DEVLOG_archive.md` and the 2026-05-25 phase completion entry in `DEVLOG.md`.

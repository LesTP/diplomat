---
phase: 20
blocked: false
state: execute
steps_remaining: 4
---

# Diplomat — Development Plan

<!-- This file is the primary state document for cold-start sessions.
     Workers read it on every cold start to determine what to do next.
     Keep it concise — the DEVPLAN should get SHORTER as work progresses.

     For autonomous projects, the frontmatter includes a `state` field:
       state: plan | execute | review | close
     See WORKER_SPEC.md for state-machine semantics.

     `steps_remaining` is managed by the state machine at runtime — do NOT
     pre-populate. -->

## Cold Start Summary

<!-- Stable section — update on major shifts, not every step.
     Gotchas: operational knowledge learned through trial-and-error.
     Prescriptive one-liners only. Historical narrative belongs in
     DEVLOG_archive.md, not here. -->

- **What this is** — AI faction agent for a multiplayer diplomacy game, with human coaching via Telegram review gate.
- **Key constraints** — Raspberry Pi deployment, all LLM calls via toolkit/llm_client, all Telegram I/O via toolkit/telegram_client, cost governance via toolkit/cost_accountant, SQLite persistence.
- **Gotchas** —
  - `toolkit` lives at `../toolkit` and must be installed editable per host (`<venv>/bin/python3 -m pip install -e ../toolkit`). Not declared in `pyproject.toml` (would be a misleading install contract — can't resolve from PyPI). Module-level tests use dependency-injected fakes; integration paths must exercise real `toolkit` imports.
  - Toolkit Phase 19 surface must import on the Pi: `from toolkit.llm_client import complete_with_retry` and `from toolkit.cost_accountant import normalize_model_name`. If ImportError, reinstall editable. See `SMOKE_RUNBOOK.md` §1.
  - **Pi deployment mechanism:** `incus exec claude-code -- sudo -u claude tmux new-window -t bot -n diplomat ...` (adds a window to the long-lived `bot` tmux session that already supervises codexbot). `tools/service.sh start` does NOT work via `incus exec` — the transient cgroup scope is torn down and kills the process even with `nohup`+`setsid`+`</dev/null`. See `CLI_REFERENCE.md` `tools/service.sh` section and `diplomat-testing-doc.md` §5b.
  - Bot vs. user account: must be resolved with game moderator before deployment. Implement `TelethonUserTransport` only if bot-to-bot is blocked.
  - Round structure (signal vs. time-based): confirm with moderator before deploying; set in `pipeline.yaml`.
  - **Telegram bot-to-bot platform limitation:** Telegram does NOT deliver bot-sent messages to other bots in groups, regardless of privacy mode. Non-operator faction-traffic in any Telegram-side test requires either a 2nd human Telegram account on another device, or a temporary de-op cycle (remove operator's user ID from `DIPLOMAT_OPERATOR_USER_IDS`).
  - **Debounce strategy:** per-event task set (each game message gets its own extraction task; no cancellation between different messages). The original cancel-and-replace design silently dropped messages in multi-message bursts.
  - **Cost governance:** CostAccountant wired through `ToolkitLLMAdapter` — every LLM call routes through `accountant.complete()` for budget-check + ledger write. `DiplomatCostGate` provides the check-before-call pattern for round-level budget control. Both share the same accountant instance.
  - All four LLM modules (extraction, analyst, adversarial, generation) use `toolkit.structured_llm.structured_call()` for schema-enforced JSON with retry-on-validation-failure.
  - Self-play cost ledger uses a local temp path (`%TEMP%/diplomat_selfplay/`) to avoid UNC path issues on network shares.
  - **Cross-provider JSON formatting:** Anthropic and Google wrap JSON in ` ```json ... ``` ` Markdown fences regardless of explicit "raw JSON" instructions. OpenAI returns raw. Toolkit's `parse_json_response` strips a single surrounding code fence; without this, structured_call's retries silently exhaust.
  - **Self-play env loading:** `tests/self_play/run_simulation.py` calls `load_dotenv()` at module top. Subprocess SDKs (Anthropic, Google) need this — only `OPENAI_API_KEY` was reliable from parent shell otherwise.
  - **Probe before live multi-provider runs:** `python -m tests.self_play.probe_providers --providers '<same JSON as --per-faction-providers>'` hits each provider once with a trivial request (~$0.001 total). Catches API keys, fence wrapping, model-name typos that `DryRunLLMClient` can't catch (DryRun replaces the LLM client entirely with canned responses).
  - For **Gemini 2.5 flash / pro**, set `--max-tokens 500` or higher on probes — thinking-mode consumes output tokens before producing visible content. `gemini-2.5-flash-lite` has no thinking mode and is the tuning default.
  - **Per-faction provider routing:** `--per-faction-providers '{"alpha":{"provider":"openai","model":"gpt-4.1-mini"},...}'` varies only the Generator per faction; other modules stay on shared primary/secondary. Verify with `verify_dryrun --expect-providers '{"alpha":"openai",...}'`.
  - **Pre-compiled analysis loader:** `--analysis-json <path>` skips live LLM compilation and loads a pre-edited analysis JSON (preserves hand-tuned BATNAs, scoring, deception tactics). Requires `--scenario` for the seed-message text.
  - **Prompt regression runner:** `_judge_response_text()` JSON path extraction must be wrapped in try-catch — if a scenario's `path` doesn't exist in module output, raw KeyError crashes the runner.
  - **Production reconciler is wired** in `src/main.py` via `_attach_reconciler` using primary provider's commodity tier; fires at every round boundary before analysts. Self-play harness has its own per-faction wiring that overrides.
  - **`game.total_rounds` optional config** in `pipeline.yaml` — when set, `Orchestrator.__init__` reads it and the persona's PENULTIMATE / FINAL ROUND markers fire. Unset = production stays endgame-blind (correct default when round count is unknown).
  - **Follow `RUN_PROTOCOL.md` for any live multi-agent run** (define inputs → verify scenario → probe providers → dry-run plumbing → run live → verify output → document). Skip rules and abort conditions are spelled out.
  - **Canonical docs at project root:** `ASSESSMENT.md` (skill framework + 4 scoring lenses + 3 workstream blocks A/B/C; tagged in NEXT_STEPS), `CLI_REFERENCE.md` (every CLI entry point), `SMOKE_RUNBOOK.md` (Telegram coaching/review smoke procedure), `RUN_PROTOCOL.md` (self-play pre-flight), `TUNING.md` (BATNA + provider defaults + prompt-tuning practice), `TUNING_LOG.md` (run-by-run record), `NEXT_STEPS.md` (forward backlog + 🔨/🔀/👁 loop-readiness classification).
  - **Reference docs to keep in sync** — see CLAUDE.md / CODEX.md "Reference Docs to Keep in Sync" section. Each Build phase's step list includes an explicit "doc update" step before phase-review naming the affected docs.

## Current Status

- **Phase** — Phase 20 (Build). Five-phase Build cycle queued: Phase 20 → 21 → 22 → 23 → 24, all pure-build (no operator judgment mid-loop).
- **Focus** — Phase 20.5: update ASSESSMENT.md and diplomat-testing-doc.md for Phase 20 coverage.
- **Blocked/Broken** — None.

## Phase 20: Layer 3 integration tests for Phase 18 paths (Build)

Regime: Build. Safety-net phase. Adds deterministic fake-LLM integration tests for the Phase 18 production-code paths that haven't fired in self-play (debounce burst, reconciler fulfillment/inconsistency/missed-proposal). Establishes regression coverage *before* the refactor phases (21 + 22) touch overlapping code.

Why first: refactoring without these tests means relying on self-play runs (expensive, non-deterministic) to catch regressions. With them, every refactor step can run `pytest tests/ -q` for fast confirmation.

Steps:
- [x] **20.1** Add `tests/integration/test_phase18_paths.py` skeleton with shared fixtures (FakeLLMClient with reconciler-shaped canned responses, transcript-burst helper)
- [x] **20.2** Implement `test_burst_extraction_no_drops` — inject 5 game events in rapid succession, settle, assert all 5 events stored + all 5 produce state_change_log entries (validates per-event task set from Phase 18.6)
- [x] **20.3** Implement `test_reconciler_dedup` + `test_reconciler_fulfillment` — extractor produces N duplicate promises → reconciler merges; extractor produces promise then kept-signal → reconciler transitions pending→kept
- [x] **20.4** Implement `test_reconciler_inconsistency` + `test_reconciler_missed_proposal` — extractor produces position then contradiction → reconciler flags inconsistency; reconciler catches proposals the per-message extractor missed
- **20.5** Doc update: `ASSESSMENT.md` (Block A tech-debt: reconciliation path coverage → ✓ covered by Layer 3 tests); `diplomat-testing-doc.md` (Layer 3 section: mention `test_phase18_paths.py` and the four new tests).
- **20.6** Phase review + commit + close. Definition of done: 288+ tests passing (284 current + 4-5 new); each new test runs <2s; deterministic with fake LLM; named docs updated.

Expected outcome: regression coverage that hardens the Phase 21 + 22 refactors.

## Phase 21: Module boundary cleanup (Build)

Regime: Build. Targeted cleanups from the audit. Two themes packaged together (§1.7 orchestration + §1.8 LLM adapter + config dedup) because they overlap on the LLM-call attribution surface and benefit from shared review.

Prerequisite: Phase 20 (Layer 3 tests) must pass — those tests are the safety net for these refactors.

Steps:
- **21.1** Add public `Orchestrator.advance_to_round(n)` that sets `current_round` and resets the per-round budget. Update `GameEnvironment.run_round` to call it instead of poking `current_round` directly and calling `_reset_round_budget()` (§1.7 fix #1).
- **21.2** Extract `OrchestrationOptions` dataclass holding `auto_response_enabled` and `total_rounds`. Pass at construction; remove these attributes from `Orchestrator.__init__`'s top-level signature. Update `main.py` and `GameEnvironment` call sites (§1.7 fix #2).
- **21.3** Resolve `StubAnalyst` registry leak. Either move `StubAnalyst` to `src/modules/analyst/stub.py` or drop the entry from `src/registry.py` and use `module_overrides` exclusively (already works in `tests/integration/conftest.py`). Update `pipeline_test.yaml` accordingly (§1.7 fix #3).
- **21.4** Replace the four bare `try/except Exception: pass` blocks in `Orchestrator._reconcile_state` with logged exceptions (§1.7 fix #4).
- **21.5** Add `attribution: str | None = None` and `purpose: str | None = None` kwargs to LLM adapter `complete()` interface. Update `ToolkitLLMAdapter`, `DiplomatCostGate`, and the toolkit's `complete_with_retry` to thread them through (§1.8 fix #1, prep for the cleanup that follows).
- **21.6** Delete `_TaggedLLMClient` entirely; reduce `LoggingLLMClient` to ~30 lines that read the new `attribution` kwarg. Remove all three `getattr(client, "_inner", client)` peeks (§1.8 fix #1, completion).
- **21.7** Switch `DryRunLLMClient.classify_call()` to read the new `purpose` kwarg instead of regex-matching the prompt body (§1.8 fix #2).
- **21.8** Extract `build_reconciler(llm_client, llm_providers_config, tier)` factory in `src/modules/reconciliation/__init__.py`. Both `src/main.py` (`_attach_reconciler`) and `tests/self_play/game_environment.py` call it; neither has its own copy. Single helper `subsystem_llm_config(primary, tier="commodity")` for the dict currently duplicated four times (§1.8 fix #3 + #4).
- **21.9** Doc update: `ARCHITECTURE.md` (coupling notes — remove references to private-API access from self-play; reconciler factory mention); `ARCH_orchestrator.md` (public `advance_to_round`; `OrchestrationOptions` dataclass; `auto_response_enabled`/`total_rounds` move out of `__init__`); `ARCH_reconciliation.md` (new `build_reconciler` factory); `ASSESSMENT.md` (Block A tech-debt: orchestration cleanup → ✓, LLM adapter cleanup → ✓); `diplomat-testing-doc.md` (§2.3 if `StubAnalyst` location changed).
- **21.10** Phase review + commit + close. Definition of done: 288+ tests passing; no `_<private>` calls from `tests/self_play/`; `auto_response_enabled` / `total_rounds` no longer attributes on `Orchestrator`; `_TaggedLLMClient` deleted; `getattr(..., "_inner", ...)` no longer appears anywhere; provider-config dict literal defined once; `DryRunLLMClient` no longer reads prompt text for classification; named docs updated.

Expected outcome: code surface cleaner; private-attribute pokes from self-play eliminated; one factory for reconciler wiring; one source of truth for the subsystem LLM config dict.

## Phase 22: Pipeline / Flow split (Build)

Regime: Build. The architectural payoff. Separates per-agent capability (`Pipeline`) from scheduling strategy (`Flow`). Two concrete Flows extracted from existing code: `EventDrivenFlow` (production, from `Orchestrator`'s event loop) and `RoundSteppedFlow` (self-play, from `GameEnvironment`'s round-stepping). Makes adding a third Flow (Clankmates polling, customer service, contract negotiation, batch summary) additive instead of a new hand-rolled driver.

Prerequisite: Phase 21 — specifically §21.1's public `advance_to_round` is the first method that needs to live on `Pipeline`.

Steps:
- **22.1** Define `Pipeline` interface. Methods: `start`/`shutdown`, `store_event(event)`, `extract_from(event)`, `dispatch_operator(content)`, `advance_to_round(n)`, `reconcile_and_analyze()`, `run_response(trigger_event=None)`, plus query methods (`get_state`, `get_intelligence`, `get_ledger`). New file `src/pipeline.py`; methods initially delegate to existing `Orchestrator` internals.
- **22.2** Implement `EventDrivenFlow` in `src/flows/event_driven.py`. Owns the async event loop reading `Transport.listen()`, the `_extraction_tasks` debounce, the `_check_round_boundary` signal regex, the `_is_direct_address` detector. Constructor takes `pipeline: Pipeline`, `transport: Transport`, optional `round_detector` and `address_detector`.
- **22.3** Compat shim: `Orchestrator` becomes a thin factory `def Orchestrator(...) -> EventDrivenFlow` returning `EventDrivenFlow(pipeline=Pipeline(...), transport=...)`. Existing `main.py` keeps working without changes.
- **22.4** Implement `RoundSteppedFlow` in `src/flows/round_stepped.py`. Replaces `GameEnvironment`'s round-stepping logic. Constructor takes `pipelines: list[Pipeline]`, `moderator: Moderator`, `total_rounds: int`. Update `GameEnvironment` to compose `RoundSteppedFlow` (no more `current_round` pokes, no more `[ROUND END]` re-entry trick).
- **22.5** Add Pipeline-contract tests (`tests/test_pipeline.py`) and Flow-contract tests (`tests/test_flows.py`). Ensure `EventDrivenFlow` reproduces all current production behavior; `RoundSteppedFlow` reproduces all current self-play behavior.
- **22.6** Verify production smoke (coaching scope, per `SMOKE_RUNBOOK.md`) reproduces. Verify self-play reproduces one known scenario byte-for-byte (or close to it given LLM nondeterminism — use seeded fake LLM for the comparison test).
- **22.7** Write `ARCH_flow.md` documenting the Flow contract. Include a worked example: "writing a new Flow for a new application" sketching `StreamFlow` (customer service) or `TurnBasedFlow` (negotiation). Update `ARCHITECTURE.md` Component Map to add Pipeline and Flow rows.
- **22.8** Doc update: `ASSESSMENT.md` (Block A tech-debt: Pipeline/Flow separation → ✓); `ARCH_orchestrator.md` (rewrite as compat shim pointing at `ARCH_flow.md`); `diplomat-testing-doc.md` (any Layer 3 references to `Orchestrator` that should now read `Pipeline` or `EventDrivenFlow`); update `CLAUDE.md` + `CODEX.md` "Load for Current Module" tables with Pipeline + Flow if they become standalone modules. (`ARCH_flow.md` itself is created in 22.7, so it's already a doc deliverable of this phase.)
- **22.9** Phase review + commit + close. Definition of done: 288+ tests passing including new Pipeline/Flow contract tests; `Orchestrator` is a compat shim; `GameEnvironment` is a thin wrapper over `RoundSteppedFlow`; `ARCH_flow.md` exists with the contract + worked example; production smoke reproduces; named docs updated.

Expected outcome: third-application work (Clankmates `HybridFlow`, customer service `StreamFlow`, etc.) becomes additive — write a new Flow class against a stable Pipeline interface.

## Phase 23: Scoring expansion — Pareto efficiency + process signatures (Build)

Regime: Build. Implements two of the four scoring lenses defined in `ASSESSMENT.md` §3 that don't need operator judgment to define. Output is more diagnostic per-run reporting; no behavioral change to agents.

Prerequisite: None code-wise, but easier after Phase 22 (post-game scoring path becomes cleaner with `Pipeline` abstraction).

Steps:
- **23.1** Implement `pareto_efficiency` field in `GameEnvironment.score_game()`. Formula: `sum(achieved_scores) / max_pareto_sum`. Compute `max_pareto_sum` by reading the precomputed scenario analysis (`verify_scenario_optimum.py` already enumerates deals; if its result isn't cached, recompute inline at scoring time). Add to the per-run scoring JSON output.
- **23.2** Add unit tests for the `pareto_efficiency` calculation: (a) a deal at the Pareto-optimum returns 1.0, (b) a deal at BATNA sum returns the BATNA/max ratio, (c) no-deal case handled. Add an integration test that runs a tiny scenario through `score_game()` end-to-end with fake LLM and asserts the field is present and numeric.
- **23.3** Implement process signatures aggregator in `tests/self_play/analysis.py`. Four deterministic signatures: `broken_promise_rate` (`broken / total_promises`), `coalition_stability` (`survived_to_final / formed`), `time_to_deal` (round number when reached or `null`), `opening_gap` per faction (|round-1 position score − reached-deal score| / max_possible). Add to the post-game report output.
- **23.4** Tests for process signatures: build a synthetic transcript fixture with known broken-promise count, known coalition trajectory, known opening positions; assert each signature computes to the expected value. ~4 tests.
- **23.5** Doc update: `ASSESSMENT.md` (§3.2 Pareto efficiency → ✓ implemented with file:line ref to `score_game`; §3.4 process signatures → partial-to-✓-for-4-of-7 deterministic ones; update Block C tech-debt list). Optional: mention in `diplomat-testing-doc.md` if post-game report format is documented there.
- **23.6** Phase review + commit + close. Every self-play run now produces per-faction `pareto_efficiency` field + process signatures; named docs updated.

Expected outcome: every self-play run produces per-faction Pareto efficiency + process signatures alongside the existing BATNA-relative WIN/LOSE verdict. Diagnostic quality of `TUNING_LOG.md` entries improves significantly.

## Phase 24: Small builds + Level 1 modularization (Build)

Regime: Build. Cluster of small standalone improvements that each take 30 min – 2 hr. Pure code, no judgment calls, no live API.

Prerequisite: None.

Steps:
- **24.1** Add toolkit unit tests for `OpenAIProvider.call` model-prefix dispatch. Two tests in `toolkit/tests/llm_client/`: (a) gpt-5.x / o-series get `max_completion_tokens` in the SDK call kwargs; (b) gpt-4.x / 3.5 keep `max_tokens`. Use a stub `OpenAI` client that records kwargs. Closes the TODO from commit `5763897`.
- **24.2** Add per-faction asymmetric `--batna-fractions` JSON flag to `tools/scenario_compiler.py` and `tests/self_play/run_simulation.py`. Same parsing pattern as `--per-faction-providers` (JSON map: `{"alpha":0.65,"beta":0.35,"gamma":0.50}`). Falls back to `--batna-fraction` scalar if not provided. Update `validate_batna_pressure()` to validate per-faction targets if asymmetric.
- **24.3** Add `--force-batna-fraction` post-clamp option to scenario compiler. After LLM produces the analysis JSON, post-process each faction's BATNA to clamp to `target × max_possible_score`. Default off (preserve current behavior); when set, narrative-explicit BATNAs are overridden.
- **24.4** Add `--game-mode` runtime override flag to `tests/self_play/run_simulation.py`. Allows operator to override the compiler's `game_mode` classification (cooperative/competitive/mixed) at run time without regenerating personas. Persona text gets the override applied as a runtime layer.
- **24.5** Level 1 modularization, part 1: extract `_EXTRACTION_EXAMPLES` constant from `src/modules/extraction/__init__.py` into `config/examples/extraction_examples.json`. Update `OpenAIStructuredExtractor` to load from JSON at construction time, with path configurable via `pipeline.yaml` `paths.examples.extraction`. Default path: `config/examples/extraction_examples.json`. Add the path to `pipeline.yaml` and `pipeline_smoke.yaml`. Update existing tests.
- **24.6** Level 1 modularization, part 2: derive entity-type references in reconciliation prompt and analysis tool iteration from `state_patch.json` schema keys instead of hardcoded strings. Both modules currently hardcode "promises", "coalitions", "inconsistencies" — replace with `list(schema['properties'].keys())` or equivalent. Test that adding a new entity type to the schema is visible to both modules without code changes.
- **24.7** Doc update: **`CLI_REFERENCE.md`** (three new flags — `--batna-fractions`, `--force-batna-fraction`, `--game-mode` — with examples and defaults; one updated section for `--batna-fraction` to note interaction with the new asymmetric flag); `TUNING.md` §1 BATNA section (asymmetric fractions + force-clamp semantics + when to use each); `diplomat-testing-doc.md` (Layer 2: extraction examples location moved to `config/examples/extraction_examples.json`); `ARCH_extraction.md` (examples now loaded from config path); `ARCH_reconciliation.md` (entity types now derived from schema). Toolkit-side: `toolkit/API.md` or `toolkit/ARCH_llm_client.md` (`OpenAIProvider.call` parameter dispatch).
- **24.8** Phase review + commit + close. Definition of done: 290+ tests passing; `--batna-fractions` + `--force-batna-fraction` + `--game-mode` all visible in `CLI_REFERENCE.md`; `_EXTRACTION_EXAMPLES` no longer in Python; entity types derived from schema in 2 places; named docs updated.

Expected outcome: tooling debt cluster closed; modularization Level 1 done (Level 2 + Level 3 deferred until a concrete second-domain use case forces them).

## Phase 19: Execute, ad-hoc — Complete

Closed 2026-05-31. Shipped toolkit `complete_with_retry` / `normalize_model_name` / `max_completion_tokens` dispatch; production `_attach_reconciler` + `game.total_rounds`; CLI_REFERENCE.md; SMOKE_RUNBOOK.md (coaching scope); ASSESSMENT.md (skill framework + scoring lenses + workstream blocks); module boundary audit → Phases 20-24 queued. See `DEVLOG_archive.md` "Archived 2026-05-31 — Phase 18 + Phase 19" section.

## Phase 18: Multi-Agent Self-Play + Tuning — Complete

Closed 2026-05-30. Regime shifted Build → Explore mid-phase. Built complete self-play infrastructure (GameEnvironment, scenario compiler, post-game scoring, state reconciliation, game-mode), reusable `structured_call` toolkit, 8 simulations across 4 scenario types (~$5-6 spend). Decisions D-20 through D-24. See `DEVLOG_archive.md` Phase 18 Close section.

## Phase 17: Layer 2 — Prompt Regression Infrastructure — Complete

`tests/prompt_regression/` package: scenario/result dataclasses, JSON-path helpers, LLM-as-judge, runner with CLI, 4 free Extraction + 2 LLM-backed Generation scenarios. 211 tests pass. See `DEVLOG_archive.md` Phase 17.

## Phase 16: Deployment Readiness — Complete

Live-smoke fix regression coverage, two-channel Telegram docs, `config/diplomat.service` unit (later found broken via incus exec — see Pi deployment gotcha), CostAccountant adapter construction fix. 193 tests passing. See `DEVLOG_archive.md`.

## Phase 15: Live Smoke Test — Environment Setup — Complete

`.env.template` + `config/pipeline_smoke.yaml`; manual Pi smoke confirmed Telegram transport, operator commands, `/preview`, review gate. Five integration fixes applied. See `DEVLOG_archive.md`.

## Phase 14: Layer 3 — Transcript Replay Tests — Complete

Two JSON transcript fixtures + 5 replay tests verifying multi-round promise/coalition/inconsistency/intelligence persistence. 187 tests passing. See `DEVLOG_archive.md`.

## Phase 13: Layer 3 — Pipeline Integration Tests — Complete

Fake-backed Layer 3 infrastructure + 12 tests (fixture startup, core Orchestrator flow, failure handling). 182 tests passing. See `DEVLOG_archive.md`.

## Phase 12: Orchestrator Refactor — Complete

Extracted `ToolkitLLMAdapter` + `DiplomatCostGate` to `src/adapters.py`; expanded State Manager (5 persistence APIs); typed `InboundEvent`; 170 tests passing. See `DEVLOG_archive.md`.

## Phase 11: Orchestrator — Complete

`pipeline.yaml`, registry lookup, full Orchestrator wiring, `src/main.py`, 44 focused Orchestrator tests + 165 total. Post-phase toolkit integration probes found 3 mismatches; adapters applied and verified on Pi. See `DEVLOG_archive.md`.

## Phase 10: Adversarial — Complete

`AdversarialResult`, `LLMAdversarialReader`, local schema validation, 9 tests + 121 total. See `DEVLOG_archive.md`.

## Phase 9: Review Gate — Complete

Review decisions, auto-approve mode, Telegram approve/edit/block workflow, optional timeout auto-block, 14 tests + 112 total. See `DEVLOG_archive.md`.

## Phase 8: Generation — Complete

`GenerationResult`, `LLMGenerator`, review-gate JSON parsing (`response`, `reasoning`), `config/prompts/generation.txt`, 11 tests + 98 total. See `DEVLOG_archive.md`.

## Phase 7: Context Assembler — Complete

`CoachingEntry`, `DecisionContext`, `DefaultContextAssembler` (pure composition), 7 tests + 87 total. See `DEVLOG_archive.md`.

## Phase 6: Analyst + Divergence — Complete

`LLMAnalyst`, pure divergence comparison, analyst prompt/schema, 12 tests + 80 total. See `DEVLOG_archive.md`.

## Phase 5: Persona — Complete

`CoachingContext`, `FileBasedPersona` (hot-reload via mtime), section stripping at `## CURRENT ROUND CONTEXT`, dynamic round-context formatting, sample `config/faction_prompt.txt`. 68 tests passing. See `DEVLOG_archive.md`.

## Phase 4: Transport — Complete

Shared Transport API exports, `CLITransport`, dependency-injected `TelegramBotTransport`, 21 tests + 59 total. See `DEVLOG_archive.md`.

## Phase 3: Coaching — Complete

`config/coaching_routes.yaml`, `CoachingEvent`, `Command`, `RouteRule`, `TaggedCoachingParser`, tagged/free coaching parsing, slash command parsing, 11 tests + 38 total. See `DEVLOG_archive.md`.

## Phase 2: Extraction — Complete

`ExtractionResult`, `OpenAIStructuredExtractor`, `RuleBasedExtractor`, local JSON/schema enforcement, `config/prompts/state_updater.txt`, 18 tests + 27 total. See `DEVLOG_archive.md`.

## Phase 1: Event Store + State Manager — Complete

Shared storage types, `SQLiteEventStore`, `SQLiteStateManager`, state patch schema validation, audit logging. See `DEVLOG_archive.md`.

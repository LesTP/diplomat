---
phase: 35
blocked: false
state: execute
steps_remaining: 0
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
  - **Pi deployment mechanism:** `incus exec claude-code -- bash /home/claude/workspace/diplomat/tools/service.sh start` is the canonical bot start command. `tools/service.sh` uses a `diplomat` window in the long-lived `bot` tmux session under the hood; override the session with `BOT_TMUX_SESSION` for tests or parallel deployments. See `CLI_REFERENCE.md` and `diplomat-testing-doc.md` §5b.
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

- **Phase** — Phase 35 queued — Reverse Scenario Builder (`tools/scenario_builder.py`). Phase 34 closed 2026-06-08; see `DEVLOG.md` Phase 34 close for that build summary.
- **Focus** — Build a programmatic constraint-driven scenario generator that targets outcome-shape properties (multi-Pareto frontier, distribution spread, BATNA gap, logrolling, asymmetric BATNAs) and emits the existing `scenario_analysis.json` + persona `.txt` shape. Phase A (tool build) is pure 🔨 build, fully loop-suitable. Phase B (proof-of-concept `multi_pareto_v1/` scenario) is operator-driven post-close work, parallel to Run 14a-14f.
- **Why now** — Run 14 confirmed scenarios behave **binary** (no-deal floor or single Pareto deal, alpha 16 / beta 18 / gamma 20 on every closing run). `RESEARCH_NOTES.md` Note 1 traces this to Water Rights being "scale-1" on every harness-relevant axis. The reverse builder is the cheapest validation path for the scaling thesis and the prerequisite for spectrum-producing scenarios that can discriminate individual agents.
- **Blocked/Broken** — none. `blocked: false`.

## Phase 35: Reverse Scenario Builder — In Progress

**Goal.** Ship `src/tools/scenario_builder.py`: a constraint-driven reverse scenario generator. Operator writes a `ScenarioSpec` (target Pareto count, distribution spread, BATNA-clearing count, BATNA-to-Pareto gap, logrolling requirement, priority collision, asymmetric BATNAs); tool searches scoring-table space via random-restart hill-climb; validates each candidate via the existing `tests/self_play/verify_scenario_optimum.py` library (pure functions, no refactor needed); emits the same `scenario_analysis.json` + per-faction `.txt` persona shape produced by `src/tools/scenario_compiler.py`. Phase scope = tool + tests only. Using the tool to produce the first proof-of-concept scenario is operator follow-up.

**Out of scope (operator follow-up after close).**
- Authoring `multi_pareto_v1/` proof-of-concept scenario (B.1 spec authorship is a design-judgment call).
- LLM narrative wrap for `logrolling` / `deception_tactics` text — emitted as stubs by Phase 35.
- §2 pressure mechanisms (round-cost decay etc.) — separate phase; needs compiler + `PERSONA_TEMPLATE` extension, not just scoring-table design.
- Live self-play smoke on a generated scenario.

**Steps.**

- [x] **35.1 — `ScenarioSpec` dataclass + JSON loader.** Add `src/tools/scenario_spec.py` with `ScenarioSpec`, `IssueSpec`, and `load_spec(path)` / `dump_spec(spec, path)`. Fields: `factions`, `issues`, `score_range` (default `(1, 10)`), `pareto_count_target` (int or `(min, max)` tuple), `pareto_distribution_spread` (float, min stdev of per-faction max-min across Pareto deals), `batna_clearing_count_target`, `batna_to_pareto_gap_pct`, `requires_logrolling` (bool), `priority_collision` (`"none" | "soft" | "hard"`), `asymmetric_batna_fractions` (per-faction floats, default symmetric 0.50), `game_mode` (`"cooperative" | "competitive" | "mixed"`), `seed` (int). Add unit tests covering spec validation, JSON round-trip, default-value handling.

- [x] **35.2 — Fitness function on top of existing verifier.** Add `src/tools/scenario_fitness.py` with `compute_fitness(analysis, spec) -> FitnessResult` returning per-target L1 distances. Reuse `enumerate_deals`, `find_pareto_frontier`, `faction_score`, `beats_batna`, `find_priority_issues` from `tests/self_play/verify_scenario_optimum.py` (`:26-105`) — pure functions, just import. `FitnessResult` exposes `total_distance`, `per_target_distance`, and `satisfies(tolerance)` boolean. Unit tests on hand-built scoring tables with known Pareto counts (use Water Rights β-squeezed as a known-1-Pareto fixture; build a known-multi-Pareto fixture inline).

- [ ] **35.3 — Hill-climb sampler with random restarts.** Add `_search_loop(spec, max_restarts=1000, max_local_moves=200, seed=None)` to `src/tools/scenario_builder.py`. Each restart: initialize random scoring table in `spec.score_range`; loop local single-cell flips that reduce `total_distance`; restart on plateau (10 moves without improvement). Accept first analysis where `satisfies(tolerance=0.10)` AND `verify_scenario_optimum.find_pareto_frontier` returns the expected count. BATNAs computed deterministically via `max_possible_score` + `asymmetric_batna_fractions` (reuse `src/tools/scenario_compiler.py:343, :404`). Unit test: deterministic seed → identical output across runs; convergence on a known-feasible spec within budget.

- [ ] **35.4 — Output emission via existing compiler helpers.** Wire the search output through `save_analysis` (`src/tools/scenario_compiler.py:501`) for `scenario_analysis.json` and `generate_persona` + `save_persona` (`:431, :511`) for per-faction `.txt` files. `logrolling` and `deception_tactics` emitted as empty / stub strings — operator can hand-author or run the LLM compiler over the generated tables to fill them. Unit test: emitted JSON loads cleanly into the existing `FileBasedPersona` + `verify_scenario_optimum` pipeline.

- [ ] **35.5 — CLI entry point with `--verify` integration.** Add `main()` + `_run(args)` to `src/tools/scenario_builder.py` mirroring `scenario_compiler.py:586`. Flags: `--spec` (path to JSON spec), `--output-dir`, `--title`, `--seed`, `--max-iterations`, `--verify` (re-runs `verify_scenario_optimum.main(...)` on the emitted JSON and exits non-zero on FAIL). Add to `pyproject.toml` console_scripts if needed. Smoke test: `python -m tools.scenario_builder --spec test_specs/multi_pareto.json --output-dir /tmp/test_scenario --verify` produces a passing scenario directory.

- [ ] **35.6 — Doc updates.** Update `CLI_REFERENCE.md` with a new `tools.scenario_builder` section (flags, working example, links to spec schema). Add a "Phase 35 → tool built" note to `NEXT_STEPS.md` §8 (collapse the TODO; move the §8 detail into closed-tier or appendix). Add a one-line entry under "What this is" in this file's Cold Start Summary if a new always-loaded gotcha emerges. Update `ARCHITECTURE.md` Implementation Sequence table if the tool warrants a row.

- [ ] **35.7 — Phase close.** Append Phase 35 close entry to `DEVLOG.md` summarizing what shipped (file list, test count delta, design decisions worth promoting). Update `ARCHITECTURE.md` status if applicable. Move Phase 34's `## Phase 34:` heading down under the `<!-- history -->` divider per the established pattern (newest-closed-first above the divider).

**Files to create.**
- `p:\shared\diplomat\src\tools\scenario_spec.py`
- `p:\shared\diplomat\src\tools\scenario_fitness.py`
- `p:\shared\diplomat\src\tools\scenario_builder.py`
- `p:\shared\diplomat\tests\test_scenario_spec.py`
- `p:\shared\diplomat\tests\test_scenario_fitness.py`
- `p:\shared\diplomat\tests\test_scenario_builder.py`

**Files to update.**
- `p:\shared\diplomat\CLI_REFERENCE.md` (step 35.6)
- `p:\shared\diplomat\NEXT_STEPS.md` §8 (step 35.6)
- `p:\shared\diplomat\ARCHITECTURE.md` (step 35.6 / 35.7 — Implementation Sequence row + status)
- `p:\shared\diplomat\DEVLOG.md` (step 35.7)

**Files reused without modification.**
- `p:\shared\diplomat\tests\self_play\verify_scenario_optimum.py` — `enumerate_deals`, `find_pareto_frontier`, `faction_score`, `beats_batna`, `find_priority_issues`, `is_pareto_dominated` (`:26-105`).
- `p:\shared\diplomat\src\tools\scenario_compiler.py` — `max_possible_score` (`:343`), `force_batna_targets` (`:404`), `generate_persona` (`:431`), `save_persona` (`:511`), `save_analysis` (`:501`), `PERSONA_TEMPLATE` (`:199`), `SCENARIO_ANALYSIS_SCHEMA` (`:36`).

**Validation criteria for phase close.**
1. All new unit tests pass (deterministic seed reproducibility, fitness convergence on known-feasible specs, JSON round-trip).
2. Full diplomat test suite remains green (current baseline: 414 tests post-Phase 34).
3. Smoke run: `python -m tools.scenario_builder --spec <known-feasible spec> --verify` succeeds end-to-end and `verify_scenario_optimum.py` reports PASS on the emitted JSON with Pareto count matching the spec target within tolerance.
4. CLI_REFERENCE.md documents the new tool with at least one working example.

**Loop-readiness:** 🔨 PURE BUILD per `NEXT_STEPS.md` taxonomy. Search algorithm is deterministic, validator is an existing pure-function library, interface is fully specified, test signal is binary (tests pass = step done). No operator judgment required mid-loop.

<!-- Closed phases only: newest first. -->

<!-- history -->

## Phase 34: Bare-prompt mode — Complete

Closed 2026-06-08. Bare-prompt ablation mode shipped as a self-play-only toggle: `tests/self_play/bare_mode.py`, `DefaultContextAssembler.assemble(bare_mode=True)`, `GameEnvironment(bare_mode=True)`, and `run_simulation.py --bare-prompt`. The mode disables Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching while preserving Persona + raw transcript + Generation, was smoke-tested live, and is documented in `DEVLOG.md` and the architecture/reference docs. See `DEVLOG.md` Phase 34 close and `NEXT_STEPS.md` §10 for the queued Run 14a-14f ablation series.

<!-- history -->

## Phase 32: Toolkit-level TG chunking + Diplomat cleanup + queue-drain + /intel trim — Complete

Closed 2026-06-04. Pushed Telegram message chunking down to `toolkit/telegram_client` — `TelegramClient.send_message` auto-chunks oversized text via the upgraded paragraph-first `split_message` (with `[continued ...]` markers); `CONTINUATION_PREFIX` constant exported. Diplomat's local `chunk_text` helper removed; `OperatorReviewGate._send_draft` / `_send_section` simplified to single-send compose. `CoachedGameEnvironment._listen_for_operator` now drains pending TG updates on startup (1s window) so stale `/approve`-style commands from previously-killed sessions can't auto-resolve R1. `/intel` operator command trimmed to the latest intelligence row (compact summary: faction, round, threat level, leverage, risks) instead of dumping every row's full JSON. Decisions D-46 (toolkit-level auto-chunking) and D-47 (coached-game startup drain window). Steps 32.1 + 32.2 (operator-driven shared toolkit changes) + 32.3-32.6 (autonomous loop, Diplomat cleanup + tests + docs) + 32.7 (cross-project NEXT_STEPS notes skipped — operator clarified NEXT_STEPS.md is a Diplomat-specific convention, knowledge preserved in toolkit docs + Diplomat DEVLOG/DECISIONS). See `DEVLOG.md` "Phase 32 close" + `TUNING_LOG.md` Run 13 (the run that surfaced the queue-staleness + /intel issues).

## Phase 31: Transport-routed OperatorReviewGate — Complete

Closed 2026-06-04. Shipped `OperatorReviewGate` (transport-based, chunked, lazy `/reasoning` + `/adversarial` fetch, command pass-through via `Pipeline.dispatch_operator` → `handle_command`). Hard rename from `TelegramReviewGate`. `chunk_text` helper added to `src/modules/review_gate/chunking.py`. Decisions D-39 through D-43. 370 tests passing on Linux Pi.

**Phase 31a hotfix (same session):** `CoachedGameEnvironment` operator-input bridge — `RoundSteppedFlow` lacked the `EventDrivenFlow.process_event` routing that the new passive gate relies on, so coached games hung at the first review prompt. Added `_listen_for_operator(tg_transport, pipeline)` that consumes the wrapped `TelegramBotTransport.listen()` and forwards operator-tagged events to `dispatch_operator`. Decision D-44.

Validated end-to-end via Run 13 (first coached game with new gate, all-Gemini-flash on Water Rights symmetric). Run 13 surfaced two follow-up items now queued as Phase 32: (a) operator command responses also need chunking (`/intel` silently dropped at oversize), and (b) the listener should drain stale TG-queue updates on startup so a previously-killed session can't poison R1 of the next session. See `DEVLOG.md` "Phase 31 Close" + "Phase 31a hotfix" + `TUNING_LOG.md` Run 13 for details.


## Phase 30: OpenRouter provider connector — Complete

Closed 2026-06-03. Added `OpenRouterProvider` to `toolkit/llm_client/providers.py` (subclasses `OpenAIProvider` with `base_url="https://openrouter.ai/api/v1"`), wired factory dispatch, added `OPENROUTER_API_KEY` env mapping in `tests/self_play/run_simulation.py`, added OpenRouter pricing entries in `cost_accountant/types.py`, 6 unit tests, probe/dry-run integration verified. Use `--per-faction-providers '{"alpha":{"provider":"openrouter","model":"<model-id>"}}'` in any self-play run with `OPENROUTER_API_KEY` set. See DEVLOG.md "Phase 30 close" section.

## Phase 29: vs-Naive baseline scorers (equal-split, BATNA-clearing, Nash bargaining) — Complete

Closed 2026-06-03. Added equal-split, BATNA-clearing, and Nash bargaining baseline scorers to the self-play scoring pipeline, rendered them in report output, backfilled historical metrics, and closed D-33. See `DEVLOG.md` "Phase 29 close".

<!-- history -->

## Phase 28: Coached self-play harness + Near-miss diagnostic — Complete

Closed 2026-06-02. Added `tests/self_play/coached_game.py` with `TelegramReviewGate`/`DryRunTelegramReviewGate` injection via `module_overrides`, `compute_near_miss()` to `tests/self_play/analysis.py` with four-field near-miss diagnostic, dry-run wiring tests, and fixture-backed near-miss tests for Run 9/10 scenarios. 346 tests passing. See `DEVLOG.md` "Phase 28 close" section.

## Phase 27: No-deal-aware scoring metrics — Complete

Closed 2026-06-01. Added baseline-normalized scoring fields to `_pareto_efficiency_metrics()` (`negotiated_surplus_share`, `faction_deltas`, `delta_above_batna_sum`, `min_faction_delta`, `surplus_distribution_stdev`), NO-DEAL-AWARE SCORING report section, `tools/backfill_scoring_metrics.py` CLI, and docs (`ASSESSMENT.md`, `diplomat-testing-doc.md`, `TUNING_LOG.md`). 340 tests passing. See `DEVLOG.md` "Phase 27 close" section.

## Phase 26: Structured per-event logging — Complete

Closed 2026-06-01. Added stream-based `diplomat.*` logging config, `DIPLOMAT_LOG_LEVEL`, Telegram inbound/outbound/tagging records, flow/pipeline/orchestrator event lifecycle records, caplog unit + integration coverage, and logging docs. 337 tests passing. See `DEVLOG.md` "Phase 26 close" section.

## Phase 25: `tools/service.sh` tmux rewrite — Complete

Closed 2026-06-01. Rewrote `tools/service.sh` to supervise the bot in a `diplomat` tmux window inside the long-lived `bot` session, with `BOT_TMUX_SESSION` override, tmux-backed `start`/`stop`/`status`/`restart`, and a shell smoke test. 331 tests passing. See `DEVLOG_archive.md` "Archived 2026-06-01 — Phase 25 service tmux rewrite" section.

## Phase 24: Small builds + Level 1 modularization — Complete

Closed 2026-06-01. Asymmetric BATNA flags (`--batna-fractions`, `--force-batna-fraction`), game-mode runtime override (`--game-mode`), extraction examples moved to `config/examples/extraction_examples.json`, entity types derived from `state_patch.json` schema in reconciler and self-play analysis. 330 tests passing. See `DEVLOG.md` "Phase 24 close" section.

## Phase 23: Scoring expansion — Pareto efficiency + process signatures — Complete

Closed 2026-05-31. Added `pareto_efficiency` field to `GameEnvironment.score_game()` and `compute_process_signatures()` to `tests/self_play/analysis.py`. Four deterministic process signatures (broken-promise rate, coalition stability, time-to-deal, opening gap). 316 tests passing. See `DEVLOG.md` "Phase 23 close" section.

## Phase 22: Pipeline / Flow split — Complete

Closed 2026-05-31. Added `Pipeline`, `EventDrivenFlow`, and `RoundSteppedFlow`; converted `Orchestrator` to a compatibility factory returning `EventDrivenFlow(Pipeline(core))`; made `GameEnvironment` a thin `RoundSteppedFlow` wrapper; documented `ARCH_flow.md`. 308 tests passing. See `DEVLOG.md` "Phase 22 close" section.

## Phase 21: Module boundary cleanup — Complete

Closed 2026-05-31. `OrchestrationOptions` dataclass; public `advance_to_round(n)`; deleted `_TaggedLLMClient`; `attribution`/`purpose` kwargs threaded through adapter stack; `build_reconciler` + `subsystem_llm_config` factories; `StubAnalyst` out of production registry; reconciler exceptions logged. 296 tests passing. See `DEVLOG_archive.md` "Phase 21 close" section.

## Phase 20: Layer 3 integration tests for Phase 18 paths — Complete

Closed 2026-05-31. Added `tests/integration/test_phase18_paths.py` (6 tests, 290 total): burst extraction no-drops, reconciler dedup/fulfillment/inconsistency/missed-proposal. Deterministic fake LLM. `ASSESSMENT.md` Block A reconciliation path coverage → closed debt. `diplomat-testing-doc.md` Layer 3 counts updated. See `DEVLOG_archive.md` "Phase 20 close" section.

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

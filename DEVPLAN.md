---
phase: 34
blocked: false
state: close
steps_remaining: 1
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

- **Phase** — Phase 34 queued 2026-06-07. **Bare-prompt mode for ablation experiments.** Adds a `bare_mode` config flag that disables Extraction, Analyst, Divergence, Reconciliation, Adversarial, and Coaching modules, leaving only Transport + Persona + Generation (+ optional Review Gate). Cleanly toggleable via existing `module_overrides` pattern. Build phase is small (~6 steps); the experimental payoff lives in the queued Run 14a-14f series in `NEXT_STEPS.md` (~36 self-play runs, ~$60-100, headline question: "does the harness contribute, or is it theater?").
- **Focus** — 6 steps, all 🔨 pure build except 34.4 smoke. Bare mode is all-or-none per game; mixed-mode is out of scope. No live LLM spend during build (DryRun + fakes throughout). Step 34.4 smoke is one live Water Rights run at ~$1 to validate end-to-end. Run 14a-14f series queued separately in NEXT_STEPS for after phase close.
- **Blocked/Broken** — `blocked: false`. Worker may begin execution.

<!-- Closed phases only: newest first. -->

<!-- history -->

## Phase 34: Bare-prompt mode — Plan

**Goal.** Add a `bare_mode` configuration flag that produces a stripped-down Diplomat agent with Persona + raw transcript + Generation only (no Extraction, Analyst, Divergence, Reconciliation, Adversarial, or Coaching). The flag enables an ablation experiment: **does Diplomat's harness actually contribute to negotiation outcomes, or could a bare-prompt agent perform comparably?**

The build is the small-but-load-bearing prerequisite for the Run 14a-14f experimental series queued in `NEXT_STEPS.md`, which uses the bare/full comparison across model tiers and scenarios to answer the foundational design-bet question.

**Mechanism.** Diplomat's self-play harness already supports per-game module substitution via `GameEnvironment(extra_module_overrides=...)` (used by `coached_game.py` to inject `TelegramReviewGate` for one faction). Bare mode extends the same pattern: a single new helper `bare_module_overrides()` produces a dict of no-op / minimal implementations for the modules being ablated, suitable to pass as `extra_module_overrides`. No fork of the orchestrator; the existing module-injection seam handles it cleanly.

**Design decisions pinned 2026-06-07:**
- **What stays in bare mode:** Transport (must — agent sends/receives), Persona (must — agent knows its role; narrative + BATNA + scoring table preserved, since these are scenario inputs not "harness output"), Generation (the LLM call itself), Event Store (read-only — needed to source the raw transcript), Review Gate (auto-approve in self-play; kept for parity with full mode so the comparison isn't confounded by review-gate effects).
- **What gets disabled:** Extraction, Analyst (primary + secondary), Divergence, Reconciliation, Adversarial Reader, Coaching parser. State Manager's *write* path is mostly idle in bare mode (no patches arrive, no coaching stored, no adversarial reads stored) but the table schema stays — simpler than building a state-managerless variant.
- **Bare context shape:** `DefaultContextAssembler` learns a `bare_mode` flag. When true, the assembled `DecisionContext` contains only persona prompt + raw transcript of all rounds-to-date. Skip the intel report, divergences list, coaching notes, recent-events filtering, and round-context structuring that full mode produces.
- **Per-game, not per-faction.** Bare mode applies to all factions in a game (all-bare game) or none (all-full game). The Run 14a-14f experimental matrix uses all-bare vs all-full per game — cleanest signal for "does the harness help."  Per-faction mixed-mode games are out of scope for this phase (potential follow-up if the all-bare-vs-all-full result is interesting).
- **No new module.** Bare mode is a configuration flag + a helper that produces no-op stand-ins for existing module slots. No new `src/modules/bare/` package. The stand-ins live in `tests/self_play/bare_mode.py` since they're experimental-harness concerns, not production runtime modules.
- **No production-pipeline change.** Bare mode is reachable only via the self-play `--bare-prompt` flag or `extra_module_overrides`. `src/main.py` and `pipeline.yaml`'s production defaults are untouched. Out of scope for Phase 34 to wire bare mode into the live Telegram bot.

**Out of scope (deliberate):**
- Per-faction mixed bare/full games (interesting follow-up if all-vs-all results warrant)
- "Medium" harness ablation (full vs medium vs bare). v1 is binary: bare or full. If results show harness helps, a future phase can ablate per-module to find the elbow.
- Wiring bare mode into the production live-game path. Self-play / ablation-only for v1.
- The experimental runs themselves — those live in `NEXT_STEPS.md` as Run 14a-14f, executed operator-driven after phase close.

### Part A — Bare-mode plumbing

- [x] **Step 34.1 — Bare module set helper.** New `tests/self_play/bare_mode.py` module exposing `bare_module_overrides(state_manager) -> dict[str, Any]` that produces no-op / minimal implementations for the modules being ablated. Stand-ins: `_BareExtractor` (returns `ExtractionResult(success=True, patch={}, error=None)` for every input — pipeline-compatible no-op), `_BareAnalyst` (returns `AnalysisResult(success=False, report=None, error="bare_mode")` from `analyze()` — orchestrator already handles secondary-analyst-failed gracefully and the primary-failed early-return is fine here too since bare mode skips intelligence storage entirely), `_BareReconciler` (no-op `reconcile()`), `_BareAdversarial` (returns `AdversarialResult(success=True, analysis=None, error=None)`), `_BareCoaching` (no-op parser that ignores all input). State Manager passes through unchanged (it's read-only for bare-mode purposes; the write path is exercised by orchestrator's intelligence/coaching/adversarial storage which now go through no-op modules). Tests: unit tests verify each stand-in returns the right no-op shape and doesn't blow up under normal pipeline call patterns.
- [x] **Step 34.2 — Bare context-assembler path.** Modify `DefaultContextAssembler.assemble()` to accept a `bare_mode: bool = False` parameter. When `True`, return a `DecisionContext` with only `system_prompt=persona_prompt` and `user_prompt=<raw transcript of recent_events joined as readable text>`. Skip the intel report, divergences, coaching, round-context structuring. The persona prompt itself stays full (includes BATNA, scoring table, strategic notes — these come from the scenario compiler, are part of "the agent's setup," not part of the harness being ablated). Tests: assert that bare context omits intel/divergences/coaching sections; assert that persona + transcript are present and well-formed; assert that switching to `bare_mode=False` produces the existing full-context shape.
- [x] **Step 34.3 — Self-play `--bare-prompt` flag.** Add `--bare-prompt` flag to `tests/self_play/run_simulation.py`. When set, the runner calls `bare_module_overrides(state_manager)` and passes the result as `extra_module_overrides` to `GameEnvironment`, and sets a `bare_mode=True` flag that the orchestrator threads through to its context-assembler call. The flag is stored in the run results JSON so the ablation analysis can group runs by mode. Tests: dry-run with `--bare-prompt` should complete without errors; verify the produced run JSON includes `"bare_mode": true` in metadata; verify the same scenario produces shorter prompts (raw transcript) than full mode.
- [x] **Step 34.4 — Smoke validation.** One dry-run + one live Water Rights run with `gpt-4.1-mini` + `--bare-prompt` to validate the path works end-to-end (no exceptions, valid run JSON produced, scoring metrics populated, agent produces coherent messages). Per `RUN_PROTOCOL.md` (probe providers → dry-run → live). Live run ~$1. Documents the bare-mode prompt size + per-round token use for cost projections of the Run 14a-14f series.

### Part B — Tests

- [x] **Step 34.5 — Integration tests.** Add `tests/integration/test_bare_mode.py` with: (a) bare-mode orchestrator processes a round-end event without raising (no analyst-call, no intelligence row written); (b) bare-mode context-assembler produces correct shape under fake LLM client; (c) `bare_module_overrides()` integrates with `GameEnvironment` and produces a complete game (4 rounds, all factions act). Use existing fixtures from `tests/integration/conftest.py` + `tests/self_play/fake_llm_client.py`. ~5-8 new tests.

### Part C — Docs

- [x] **Step 34.6 — Documentation update.** Files to update before phase-review:
  - `ARCH_context_assembler.md` — document the `bare_mode` parameter and the resulting context shape (persona + raw transcript only).
  - `ARCH_orchestrator.md` (or `ARCH_flow.md` if the bare-mode flag lives at the flow layer) — note the `bare_module_overrides` injection pattern as an experimental-harness mechanism, similar to how `coached_game.py` injects `TelegramReviewGate`.
  - `ARCHITECTURE.md` — add a one-line note in the Extension Points section: "Bare-prompt ablation mode: pass `bare_module_overrides()` as `extra_module_overrides` to disable Extraction/Analyst/Divergence/Reconciliation/Adversarial/Coaching for ablation experiments. See `tests/self_play/bare_mode.py`."
  - `CLI_REFERENCE.md` — add the `--bare-prompt` flag to the `run_simulation` entry.
  - `diplomat-testing-doc.md` — add bare-mode as an experimental harness configuration alongside the existing self-play / coached-self-play modes.
  - `NEXT_STEPS.md` — add the Run 14a-14f experimental series under §10 (new section: "Ablation: bare-prompt vs full-harness"); flag that Run 14 (the original coached re-test queued from Phase 33) is **renamed Run 13b** to avoid number collision with the ablation series.
  - `DEVLOG.md` — Phase 34 close entry following the standard pattern.
  - `DEVPLAN.md` — collapse Phase 34 to a closed-phase summary block at close.

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
